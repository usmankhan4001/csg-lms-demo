/**
 * Backend base URL configuration.
 * =================================
 *
 * Mirrors `apps/web/lib/api/api-client.ts`'s `NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL`
 * pattern — one env var, sane dev default, trailing slash stripped.
 *
 * IMPORTANT (device networking, unlike a browser): `localhost` on a physical
 * phone or a simulator/emulator refers to *the device itself*, not your dev
 * machine running `uv run uvicorn` / the FastAPI dev server. To reach a
 * locally-running backend from:
 *   - iOS Simulator: `http://localhost:1338` works (it shares the Mac's
 *     network namespace) — the default below is fine.
 *   - Android Emulator: use `http://10.0.2.2:1338` (Android's documented
 *     alias for the host machine's loopback).
 *   - A physical device (Expo Go or a dev client) on the same Wi-Fi: use
 *     your machine's LAN IP, e.g. `http://192.168.1.23:1338`.
 * Set `EXPO_PUBLIC_API_BASE_URL` in `.env` (or your shell) to override the
 * default per-target — see `.env.example`. `EXPO_PUBLIC_*` vars are inlined
 * by Metro at bundle time (see https://docs.expo.dev/guides/environment-variables/).
 */

const DEFAULT_DEV_BASE_URL = 'http://localhost:1338';

export const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || DEFAULT_DEV_BASE_URL).replace(/\/+$/, '');

/** `true` when running against a backend that is realistically a local dev server (see src/auth for how this gates the dev token-paste login flow). */
export const IS_DEV_BACKEND = __DEV__;
