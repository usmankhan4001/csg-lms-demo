#!/usr/bin/env python3
"""
==============================================================================
CSG-LMS Deployment Healthcheck & Infrastructure Probe
==============================================================================
Comprehensive validation script for PostgreSQL 16 (pgvector), Redis 7.2,
Keycloak 24/26 OIDC/JWKS, FastAPI backend, Hocuspocus Collab, Next.js 15 Web,
and SSL/TLS endpoints.

Usage:
    python deploy/scripts/healthcheck.py
    python deploy/scripts/healthcheck.py --env-file .env.production --json
    python deploy/scripts/healthcheck.py --timeout 10 --verbose
==============================================================================
"""

import sys
import os
import time
import socket
import ssl
import json
import argparse
import urllib.request
import urllib.error
from urllib.parse import urlparse
from typing import Dict, Any, Tuple, Optional, List


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_info(msg: str) -> None:
    print(f"{Color.CYAN}ℹ [INFO]{Color.RESET} {msg}")


def log_ok(msg: str) -> None:
    print(f"{Color.GREEN}✔ [OK]{Color.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{Color.YELLOW}⚠ [WARN]{Color.RESET} {msg}")


def log_err(msg: str) -> None:
    print(f"{Color.RED}✖ [FAIL]{Color.RESET} {msg}")


def load_env_file(filepath: str) -> Dict[str, str]:
    """Parse key-value pairs from .env or .env.production file."""
    env_vars: Dict[str, str] = {}
    if not os.path.exists(filepath):
        return env_vars

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> Tuple[bool, float, Optional[str]]:
    """Probe raw TCP port connectivity and measure handshake latency."""
    start = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        latency = (time.perf_counter() - start) * 1000
        return True, latency, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return False, latency, str(e)


def check_http_endpoint(
    url: str,
    timeout: float = 5.0,
    expected_statuses: Tuple[int, ...] = (200, 204, 301, 302, 307, 308),
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[bool, int, float, Optional[str], Optional[Dict[str, Any]]]:
    """Perform HTTP/HTTPS probe and parse JSON response when present."""
    start = time.perf_counter()
    req_headers = {"User-Agent": "CSG-LMS-HealthCheck/1.3.6"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            latency = (time.perf_counter() - start) * 1000
            status_code = resp.status
            body_bytes = resp.read()
            parsed_json = None
            try:
                parsed_json = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                pass

            is_ok = status_code in expected_statuses
            return is_ok, status_code, latency, None, parsed_json
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - start) * 1000
        is_ok = e.code in expected_statuses
        return is_ok, e.code, latency, str(e), None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return False, 0, latency, str(e), None


def check_ssl_certificate(hostname: str, port: int = 443, timeout: float = 5.0) -> Tuple[bool, Optional[str], Optional[str]]:
    """Verify SSL/TLS certificate validity for production domain."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return False, "No certificate received", None
                not_after = cert.get("notAfter", "")
                issuer_tuple = cert.get("issuer", ())
                issuer_str = ", ".join([f"{x[0][0]}={x[0][1]}" for x in issuer_tuple if x])
                return True, not_after, issuer_str
    except Exception as e:
        return False, None, str(e)


def check_redis_ping(host: str, port: int = 6379, password: Optional[str] = None, timeout: float = 3.0) -> Tuple[bool, float, Optional[str]]:
    """Send Redis RESP PING command directly over socket."""
    start = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # If password is set, send AUTH
        if password:
            auth_cmd = f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n"
            sock.sendall(auth_cmd.encode("utf-8"))
            resp = sock.recv(1024).decode("utf-8")
            if not resp.startswith("+OK"):
                sock.close()
                return False, (time.perf_counter() - start) * 1000, f"AUTH failed: {resp.strip()}"

        # Send PING
        sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        resp = sock.recv(1024).decode("utf-8")
        sock.close()

        latency = (time.perf_counter() - start) * 1000
        if "+PONG" in resp:
            return True, latency, None
        return False, latency, f"Unexpected response: {resp.strip()}"
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return False, latency, str(e)


def main():
    parser = argparse.ArgumentParser(description="CSG-LMS Production Stack Health Check")
    parser.add_argument("--env-file", default=".env.production", help="Path to environment file")
    parser.add_argument("--timeout", type=float, default=5.0, help="Socket and HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose diagnostics")
    args = parser.parse_args()

    # Load configuration
    env_config = load_env_file(args.env_file)
    if not env_config and os.path.exists(".env"):
        env_config = load_env_file(".env")

    # Resolve variables with defaults
    app_url = env_config.get("LEARNHOUSE_URL", "https://app.csginfotech.com")
    api_url = env_config.get("LEARNHOUSE_API_URL", "https://api.csginfotech.com")
    auth_url = env_config.get("KEYCLOAK_URL", "https://auth.csginfotech.com")
    collab_url = env_config.get("LEARNHOUSE_COLLAB_URL", "https://collab.csginfotech.com")
    realm = env_config.get("KEYCLOAK_REALM", "csg-lms")
    redis_pass = env_config.get("REDIS_PASSWORD", "")

    db_str = env_config.get("LEARNHOUSE_SQL_CONNECTION_STRING", "")
    db_host = "127.0.0.1"
    db_port = 5432
    if db_str:
        try:
            parsed = urlparse(db_str.replace("postgresql+asyncpg://", "postgresql://"))
            db_host = parsed.hostname or "127.0.0.1"
            db_port = parsed.port or 5432
        except Exception:
            pass

    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_status": "PENDING",
        "checks": {},
    }

    if not args.json:
        print(f"\n{Color.BOLD}=================================================================={Color.RESET}")
        print(f"{Color.BOLD}🔎 CSG-LMS PRODUCTION INFRASTRUCTURE HEALTH PROBE{Color.RESET}")
        print(f"{Color.BOLD}=================================================================={Color.RESET}\n")

    all_passed = True

    # 1. PostgreSQL TCP Probe
    db_ok, db_lat, db_err = check_tcp_port(db_host, db_port, timeout=args.timeout)
    results["checks"]["postgres"] = {
        "host": db_host,
        "port": db_port,
        "status": "HEALTHY" if db_ok else "UNHEALTHY",
        "latency_ms": round(db_lat, 2),
        "error": db_err,
    }
    if not db_ok:
        all_passed = False

    # 2. Redis RESP Ping Probe
    redis_ok, redis_lat, redis_err = check_redis_ping("127.0.0.1", 6379, password=redis_pass if redis_pass else None, timeout=args.timeout)
    results["checks"]["redis"] = {
        "host": "127.0.0.1",
        "port": 6379,
        "status": "HEALTHY" if redis_ok else "UNHEALTHY",
        "latency_ms": round(redis_lat, 2),
        "error": redis_err,
    }
    if not redis_ok:
        all_passed = False

    # 3. Keycloak OIDC Discovery & JWKS
    kc_disc_url = f"{auth_url}/realms/{realm}/.well-known/openid-configuration"
    kc_disc_ok, kc_disc_code, kc_disc_lat, kc_disc_err, kc_disc_data = check_http_endpoint(kc_disc_url, timeout=args.timeout)

    kc_jwks_url = f"{auth_url}/realms/{realm}/protocol/openid-connect/certs"
    kc_jwks_ok, kc_jwks_code, kc_jwks_lat, kc_jwks_err, kc_jwks_data = check_http_endpoint(kc_jwks_url, timeout=args.timeout)

    key_count = len(kc_jwks_data.get("keys", [])) if (kc_jwks_data and isinstance(kc_jwks_data, dict)) else 0
    kc_healthy = kc_disc_ok and kc_jwks_ok and key_count > 0

    results["checks"]["keycloak"] = {
        "realm": realm,
        "discovery_url": kc_disc_url,
        "discovery_status": kc_disc_code,
        "jwks_url": kc_jwks_url,
        "jwks_status": kc_jwks_code,
        "active_signing_keys": key_count,
        "status": "HEALTHY" if kc_healthy else "UNHEALTHY",
        "latency_ms": round(kc_disc_lat + kc_jwks_lat, 2),
        "error": kc_disc_err or kc_jwks_err,
    }
    if not kc_healthy:
        all_passed = False

    # 4. FastAPI Backend Routes
    api_health_url = f"{api_url}/api/v1/health"
    api_ok, api_code, api_lat, api_err, api_data = check_http_endpoint(api_health_url, timeout=args.timeout, expected_statuses=(200, 204))
    if not api_ok:
        # Fallback to root route
        api_root_url = f"{api_url}/"
        api_ok, api_code, api_lat, api_err, api_data = check_http_endpoint(api_root_url, timeout=args.timeout, expected_statuses=(200, 204))

    results["checks"]["api"] = {
        "url": api_url,
        "status_code": api_code,
        "status": "HEALTHY" if api_ok else "UNHEALTHY",
        "latency_ms": round(api_lat, 2),
        "error": api_err,
        "response": api_data,
    }
    if not api_ok:
        all_passed = False

    # 5. Collab Service (Hocuspocus)
    collab_health_url = f"{collab_url}/health"
    collab_ok, collab_code, collab_lat, collab_err, collab_data = check_http_endpoint(collab_health_url, timeout=args.timeout, expected_statuses=(200, 204))
    results["checks"]["collab"] = {
        "url": collab_health_url,
        "status_code": collab_code,
        "status": "HEALTHY" if collab_ok else "UNHEALTHY",
        "latency_ms": round(collab_lat, 2),
        "error": collab_err,
    }
    if not collab_ok:
        all_passed = False

    # 6. Web Application (Next.js 15 Standalone)
    web_ok, web_code, web_lat, web_err, _ = check_http_endpoint(app_url, timeout=args.timeout, expected_statuses=(200, 301, 302, 307, 308))
    results["checks"]["web"] = {
        "url": app_url,
        "status_code": web_code,
        "status": "HEALTHY" if web_ok else "UNHEALTHY",
        "latency_ms": round(web_lat, 2),
        "error": web_err,
    }
    if not web_ok:
        all_passed = False

    # 7. SSL / TLS Verification for Production Hostnames
    ssl_results = {}
    for domain in ["app.csginfotech.com", "api.csginfotech.com", "auth.csginfotech.com", "collab.csginfotech.com"]:
        ssl_ok, exp_date, ssl_info = check_ssl_certificate(domain, timeout=args.timeout)
        ssl_results[domain] = {
            "valid": ssl_ok,
            "expires": exp_date,
            "issuer_or_error": ssl_info,
        }
    results["checks"]["ssl_certificates"] = ssl_results

    results["overall_status"] = "ALL_SYSTEMS_OPERATIONAL" if all_passed else "DEGRADED"

    # Terminal output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # PostgreSQL
        if db_ok:
            log_ok(f"PostgreSQL 16 (pgvector) : Online at {db_host}:{db_port} ({db_lat:.1f}ms)")
        else:
            log_err(f"PostgreSQL 16 (pgvector) : FAILED at {db_host}:{db_port} -> {db_err}")

        # Redis
        if redis_ok:
            log_ok(f"Redis 7.2 Alpine         : PING responded PONG ({redis_lat:.1f}ms)")
        else:
            log_err(f"Redis 7.2 Alpine         : FAILED -> {redis_err}")

        # Keycloak
        if kc_healthy:
            log_ok(f"Keycloak 24/26 OIDC      : Realm '{realm}' active ({key_count} JWKS signing keys, {kc_disc_lat + kc_jwks_lat:.1f}ms)")
        else:
            log_err(f"Keycloak 24/26 OIDC      : Discovery/JWKS error -> {kc_disc_err or kc_jwks_err}")

        # FastAPI Backend
        if api_ok:
            log_ok(f"FastAPI Backend API      : HTTP {api_code} at {api_url} ({api_lat:.1f}ms)")
        else:
            log_err(f"FastAPI Backend API      : FAILED at {api_url} (HTTP {api_code}) -> {api_err}")

        # Collab Hocuspocus
        if collab_ok:
            log_ok(f"Collab Service (Yjs)     : HTTP {collab_code} at {collab_health_url} ({collab_lat:.1f}ms)")
        else:
            log_err(f"Collab Service (Yjs)     : FAILED at {collab_health_url} -> {collab_err}")

        # Next.js Web
        if web_ok:
            log_ok(f"Next.js 15 Web App       : HTTP {web_code} at {app_url} ({web_lat:.1f}ms)")
        else:
            log_err(f"Next.js 15 Web App       : FAILED at {app_url} (HTTP {web_code}) -> {web_err}")

        # SSL Certificates summary
        print(f"\n{Color.BOLD}🔒 SSL / TLS Certificates Status:{Color.RESET}")
        for dom, sinfo in ssl_results.items():
            if sinfo["valid"]:
                print(f"   {Color.GREEN}✔{Color.RESET} {dom:25} -> Valid until: {sinfo['expires']}")
            else:
                print(f"   {Color.YELLOW}⚠{Color.RESET} {dom:25} -> {sinfo['issuer_or_error']}")

        print(f"\n{Color.BOLD}------------------------------------------------------------------{Color.RESET}")
        if all_passed:
            print(f"{Color.GREEN}{Color.BOLD}🎉 OVERALL STATUS: ALL SYSTEMS OPERATIONAL (HEALTHY){Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}{Color.BOLD}❌ OVERALL STATUS: DEGRADED / UNHEALTHY COMPONENTS DETECTED{Color.RESET}\n")
            sys.exit(1)


if __name__ == "__main__":
    main()
