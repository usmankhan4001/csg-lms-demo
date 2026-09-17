"""Tests for src/services/ai/image/generator.py (multi-provider image gen).

OpenRouter, OpenAI, and Google GenAI SDKs are fully mocked.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.ai.image.generator as gen
from src.services.ai.llm import AINotConfiguredError

pytestmark = pytest.mark.asyncio


def _cfg(provider="google", api_key="k", gemini_api_key=None, image_model=None):
    return SimpleNamespace(
        ai_config=SimpleNamespace(
            provider=provider,
            api_key=api_key,
            gemini_api_key=gemini_api_key,
            image_model=image_model,
        )
    )


def _image_response(data=b"PNGBYTES"):
    part = SimpleNamespace(inline_data=SimpleNamespace(data=data))
    content = SimpleNamespace(parts=[part])
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


# --- _resolve_image_config ---

def test_resolve_config_google_uses_api_key():
    with patch.object(gen, "get_learnhouse_config", return_value=_cfg(provider="google", api_key="gk")):
        provider, key, model = gen._resolve_image_config()
    assert provider == "google" and key == "gk" and model == gen.DEFAULT_IMAGE_MODEL


def test_resolve_config_openrouter_uses_openrouter_model():
    cfg = _cfg(provider="openrouter", api_key="sk-or-v1-abc")
    with patch.object(gen, "get_learnhouse_config", return_value=cfg):
        provider, key, model = gen._resolve_image_config()
    assert provider == "openrouter" and key == "sk-or-v1-abc" and model == gen.DEFAULT_OPENROUTER_IMAGE_MODEL


def test_resolve_config_custom_model():
    cfg = _cfg(provider="google", api_key="gk", image_model="my-image-model")
    with patch.object(gen, "get_learnhouse_config", return_value=cfg):
        _, _, model = gen._resolve_image_config()
    assert model == "my-image-model"


def test_resolve_config_missing_key_raises():
    cfg = _cfg(provider="anthropic", api_key=None, gemini_api_key=None)
    with patch.object(gen, "get_learnhouse_config", return_value=cfg):
        with pytest.raises(AINotConfiguredError):
            gen._resolve_image_config()


# --- _extract_image_bytes ---

def test_extract_image_bytes_found():
    assert gen._extract_image_bytes(_image_response(b"abc")) == b"abc"


def test_extract_image_bytes_none_when_no_inline():
    resp = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(inline_data=None)]))])
    assert gen._extract_image_bytes(resp) is None


def test_extract_image_bytes_empty_candidates():
    assert gen._extract_image_bytes(SimpleNamespace(candidates=[])) is None


# --- generate_image ---

async def test_generate_image_empty_prompt_raises():
    with pytest.raises(ValueError):
        await gen.generate_image("   ")


async def test_generate_image_google_success():
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=_image_response(b"IMG"))
    with patch.object(gen, "get_learnhouse_config", return_value=_cfg(provider="google", api_key="gk")), patch(
        "google.genai.Client", return_value=client
    ):
        out = await gen.generate_image("a cat")
    assert out == b"IMG"


async def test_generate_image_openrouter_success():
    with patch.object(gen, "get_learnhouse_config", return_value=_cfg(provider="openrouter", api_key="sk-or-test")), patch(
        "src.services.ai.image.generator._generate_openrouter_image", new_callable=AsyncMock, return_value=b"OR_IMG"
    ):
        out = await gen.generate_image("a futuristic classroom")
    assert out == b"OR_IMG"


def test_sniff_mime():
    assert gen._sniff_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert gen._sniff_mime(b"\xff\xd8\xff\xe0xxxx") == "image/jpeg"
    assert gen._sniff_mime(b"RIFF\x00\x00\x00\x00WEBPxxxx") == "image/webp"
    assert gen._sniff_mime(b"unknownbytes") == "image/png"  # safe fallback
