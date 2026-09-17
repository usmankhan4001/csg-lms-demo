"""AI image generation (OpenRouter, OpenAI & Google multimodal image generation).

Supports:
- OpenRouter image generation models (e.g. ``bytedance-seed/seedream-4.5``, ``recraft/recraft-v3``)
- OpenAI DALL-E 3 / DALL-E 2
- Google GenAI (Gemini 2.5 Flash Image / Imagen 3)

Supports two modes:
- text-to-image (``prompt`` only)
- image editing / iterative refinement (``prompt`` + one or more ``input_images``)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Optional

from config.config import get_learnhouse_config
from src.services.ai.llm import AINotConfiguredError
from src.services.ai.llm.provider import _GOOGLE_ALIASES, _OPENAI_ALIASES

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_OPENROUTER_IMAGE_MODEL = "bytedance-seed/seedream-4.5"
DEFAULT_OPENAI_IMAGE_MODEL = "dall-e-3"

OUTPUT_MIME = "image/png"
OUTPUT_EXT = "png"

MAX_PROMPT_CHARS = 4000

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _sniff_mime(data: bytes) -> str:
    """Best-effort image MIME detection so edit/refine inputs aren't mislabeled."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return OUTPUT_MIME


def _is_retryable(exc: Exception) -> bool:
    """True for transient API errors worth retrying."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _RETRYABLE_STATUS:
        return True
    name = type(exc).__name__
    return name in ("ServerError", "ServiceUnavailable", "ResourceExhausted")


def _resolve_image_config() -> tuple[str, str, str]:
    """Return ``(provider, api_key, model)`` for image generation or raise if unconfigured."""
    cfg = get_learnhouse_config().ai_config
    provider_id = (getattr(cfg, "provider", None) or "").strip().lower()
    api_key = getattr(cfg, "api_key", None)
    gemini_key = getattr(cfg, "gemini_api_key", None)
    configured_model = (getattr(cfg, "image_model", None) or "").strip()

    # 1. OpenRouter
    if provider_id == "openrouter" or (api_key and api_key.startswith("sk-or-")):
        key = api_key or getattr(cfg, "openrouter_api_key", None)
        if not key:
            raise AINotConfiguredError("OpenRouter API key not configured (set OPENROUTER_API_KEY)")
        model = configured_model or DEFAULT_OPENROUTER_IMAGE_MODEL
        return "openrouter", key, model

    # 2. OpenAI
    if provider_id in _OPENAI_ALIASES or (api_key and api_key.startswith("sk-") and not api_key.startswith("sk-or-")):
        key = api_key
        if not key:
            raise AINotConfiguredError("OpenAI API key not configured (set OPENAI_API_KEY)")
        model = configured_model or DEFAULT_OPENAI_IMAGE_MODEL
        return "openai", key, model

    # 3. Google GenAI
    if provider_id in _GOOGLE_ALIASES or gemini_key or (api_key and api_key.startswith("AIza")):
        key = gemini_key or api_key
        if not key:
            raise AINotConfiguredError(
                "AI image generation requires a Google/Gemini API key "
                "(set LEARNHOUSE_GEMINI_API_KEY, or LEARNHOUSE_AI_API_KEY when "
                "LEARNHOUSE_AI_PROVIDER=google)."
            )
        model = configured_model or DEFAULT_IMAGE_MODEL
        return "google", key, model

    # 4. Fallback to OpenRouter or Google if any key is present
    if api_key:
        if api_key.startswith("sk-or-"):
            return "openrouter", api_key, configured_model or DEFAULT_OPENROUTER_IMAGE_MODEL
        if api_key.startswith("sk-"):
            return "openai", api_key, configured_model or DEFAULT_OPENAI_IMAGE_MODEL
        return "google", api_key, configured_model or DEFAULT_IMAGE_MODEL

    raise AINotConfiguredError(
        "AI image generation requires an API key (set OPENROUTER_API_KEY, OPENAI_API_KEY, or LEARNHOUSE_GEMINI_API_KEY)."
    )


def _extract_image_bytes(response) -> Optional[bytes]:
    """Pull the first inline image payload out of a GenAI response."""
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline else None
            if data:
                return data
    return None


async def _generate_openrouter_image(
    prompt: str,
    api_key: str,
    model: str,
    input_images: Optional[list[bytes]] = None,
) -> bytes:
    """Generate image using OpenRouter API."""
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://csginfotech.co",
        "X-Title": "CSG LMS",
    }

    payload_prompt = prompt
    if input_images:
        payload_prompt = f"Edit the reference image: {prompt}"

    async with httpx.AsyncClient(timeout=90.0) as client:
        # First attempt: /api/v1/images endpoint
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/images",
                json={"model": model, "prompt": payload_prompt},
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items:
                    b64 = items[0].get("b64_json")
                    if b64:
                        return base64.b64decode(b64)
                    url = items[0].get("url")
                    if url:
                        img_resp = await client.get(url)
                        if img_resp.status_code == 200:
                            return img_resp.content
        except Exception as e:
            logger.warning("OpenRouter /images endpoint call failed: %s, trying chat completions", e)

        # Fallback: /api/v1/chat/completions endpoint
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": payload_prompt}],
                "modalities": ["image", "text"],
            },
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                images = msg.get("images", [])
                for img in images:
                    url = img.get("image_url", {}).get("url") or img.get("url")
                    if url:
                        if url.startswith("data:") and ";base64," in url:
                            b64 = url.split(";base64,")[1]
                            return base64.b64decode(b64)
                        img_resp = await client.get(url)
                        if img_resp.status_code == 200:
                            return img_resp.content
                content = msg.get("content", "")
                if "data:image/" in content and ";base64," in content:
                    m = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
                    if m:
                        return base64.b64decode(m.group(1))

        try:
            err_data = resp.json()
            err_msg = err_data.get("error", {}).get("message") or resp.text
        except Exception:
            err_msg = resp.text
        raise RuntimeError(f"OpenRouter image generation failed: {err_msg}")


async def _generate_openai_image(
    prompt: str,
    api_key: str,
    model: str,
) -> bytes:
    """Generate image using OpenAI DALL-E."""
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
        "size": "1024x1024",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            json=payload,
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            if items and items[0].get("b64_json"):
                return base64.b64decode(items[0]["b64_json"])
        try:
            err_msg = resp.json().get("error", {}).get("message") or resp.text
        except Exception:
            err_msg = resp.text
        raise RuntimeError(f"OpenAI image generation failed: {err_msg}")


async def generate_image(
    prompt: str,
    *,
    input_images: Optional[list[bytes]] = None,
) -> bytes:
    """Generate (or edit) an image with OpenRouter, OpenAI, or Google GenAI. Returns PNG/JPEG bytes."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("A non-empty prompt is required for image generation.")
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS]

    provider, api_key, model = _resolve_image_config()

    if provider == "openrouter":
        return await _generate_openrouter_image(
            prompt, api_key, model, input_images=input_images
        )

    if provider == "openai":
        return await _generate_openai_image(prompt, api_key, model)

    # Google GenAI path
    from google import genai
    from google.genai import types

    imgs = [img for img in (input_images or []) if img]
    contents: list = []
    if imgs:
        for img in imgs:
            contents.append(types.Part.from_bytes(data=img, mime_type=_sniff_mime(img)))
        contents.append(
            f"Using the provided image as the starting point, edit it as follows: {prompt}"
        )
    else:
        contents.append(prompt)

    config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    client = genai.Client(api_key=api_key)
    response = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            break
        except Exception as e:
            if _is_retryable(e) and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "Image generation transient error (%s), retry %d/%d",
                    type(e).__name__, attempt, _MAX_ATTEMPTS,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                logger.error("Image generation quota exhausted on Google API key")
                raise RuntimeError(
                    "Google Gemini image generation quota exceeded. Please configure OPENROUTER_API_KEY for image generation."
                ) from e
            logger.error("Image generation call failed: %s", type(e).__name__)
            raise RuntimeError("Image generation failed. Please try again or rephrase your prompt.") from e

    image_bytes = _extract_image_bytes(response)
    if not image_bytes:
        logger.warning("Image generation returned no image")
        raise RuntimeError("The model did not return an image. Try rephrasing your prompt.")
    return image_bytes
