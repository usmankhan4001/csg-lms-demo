import urllib.request
import urllib.error
import json

API_BASE = "https://api-demo.csginfotech.co"
TOKEN = "lh_THA4348Ly7yLBh0NqCzPx70ZDaBxWNzHhs2l31P9I8g"

endpoints_to_test = [
    ("GET", "/api/v1/users/me", None),
    ("GET", "/api/v1/sms/me", None),
    ("GET", "/api/v1/orgs/1", None),
    ("GET", "/api/v1/orgs/slug/default", None),
    ("GET", "/api/v1/sms/academic/campuses", None),
    ("GET", "/api/v1/sms/academic/years", None),
    ("GET", "/api/v1/sms/academic/sections", None),
    ("GET", "/api/v1/sms/identity/students", None),
    ("GET", "/api/v1/sms/attendance/daily", None),
    ("GET", "/api/v1/sms/gradebook/scales", None),
    ("GET", "/api/v1/sms/revops/leads", None),
    ("GET", "/api/v1/sms/financials/chart-of-accounts", None),
    ("GET", "/api/v1/sms/payroll/runs", None),
    ("GET", "/api/v1/sms/cognia/ami", None),
    ("GET", "/api/v1/ems/roles", None),
    ("GET", "/api/v1/ems/roles/templates", None),
]

print("================================================================")
print(f"Testing API Token: {TOKEN[:12]}... against {API_BASE}")
print("================================================================")

for method, path, body in endpoints_to_test:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://lms-demo.csginfotech.co"
    }
    req = urllib.request.Request(url, headers=headers, method=method)
    if body:
        req.data = json.dumps(body).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            data = resp.read().decode("utf-8")
            try:
                parsed = json.loads(data)
                sample = json.dumps(parsed, indent=2)[:400]
            except Exception:
                sample = data[:400]
            print(f"[{method}] {path} -> HTTP {status_code} SUCCESS\nPreview:\n{sample}\n")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[{method}] {path} -> HTTP {e.code} ({e.reason}):\n{err_body[:400]}\n")
    except Exception as exc:
        print(f"[{method}] {path} -> Exception: {exc}\n")
