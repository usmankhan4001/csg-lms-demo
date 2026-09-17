import urllib.request
import urllib.error
import json

API_BASE = "https://api-demo.csginfotech.co"
TOKEN = "lh_THA4348Ly7yLBh0NqCzPx70ZDaBxWNzHhs2l31P9I8g"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://lms-demo.csginfotech.co"
}

def api_call(method, path, body=None):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers=HEADERS, method=method)
    if body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            try:
                parsed = json.loads(data)
                return resp.status, parsed
            except Exception:
                return resp.status, data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body
    except Exception as exc:
        return 0, str(exc)

print("=" * 70)
print(f"AUTOMATED API KEY PERMISSION & MUTATION TEST SUITE")
print(f"Token: {TOKEN[:12]}...")
print("=" * 70)

# 1. Inspect token authority & identity
print("\n--- 1. Testing Identity & Setup Endpoints ---")
for path in ["/api/v1/sms/me", "/api/v1/campuses", "/api/v1/ems/roles"]:
    status, res = api_call("GET", path)
    print(f"GET {path} -> HTTP {status}")
    if status == 200:
        if isinstance(res, list):
            print(f"  Returned {len(res)} items. First item: {json.dumps(res[0] if res else {}, indent=2)[:200]}")
        else:
            print(f"  Response: {json.dumps(res, indent=2)[:200]}")
    else:
        print(f"  Error: {res}")

# 2. Test Academic & Curricular reading
print("\n--- 2. Testing Academic & Gradebook Endpoints ---")
for path in ["/api/v1/campuses/academic-years", "/api/v1/campuses/sections", "/api/v1/sms/gradebook/scales", "/api/v1/sms/cognia/ami"]:
    status, res = api_call("GET", path)
    print(f"GET {path} -> HTTP {status}")
    if status == 200:
        if isinstance(res, list):
            print(f"  Returned {len(res)} items.")
        else:
            print(f"  Response: {json.dumps(res, indent=2)[:150]}")
    else:
        print(f"  Error: {res}")

# 3. Test Admissions / CRM Lead Mutation (Create & Update)
print("\n--- 3. Testing Lead Mutation (Record Alteration via API Token) ---")
lead_payload = {
    "first_name": "API",
    "last_name": "Automated Student",
    "email": "api.student.test@csginfotech.co",
    "phone": "+96891234567",
    "stage": "inquiry",
    "grade_level": "Grade 9",
    "notes": "Created via API Token Automated Permission Test"
}
status, create_res = api_call("POST", "/api/v1/sms/revops/leads", lead_payload)
print(f"POST /api/v1/sms/revops/leads -> HTTP {status}")
print(f"  Response: {create_res}")

if status in (200, 201) and isinstance(create_res, dict) and "id" in create_res:
    created_id = create_res["id"]
    print(f"  Created Lead ID: {created_id}")
    
    # Update the lead
    update_payload = {
        "stage": "tour_scheduled",
        "notes": "Updated stage via API token PATCH mutation test"
    }
    up_status, up_res = api_call("PATCH", f"/api/v1/sms/revops/leads/{created_id}", update_payload)
    print(f"PATCH /api/v1/sms/revops/leads/{created_id} -> HTTP {up_status}")
    print(f"  Update Response: {up_res}")

print("\n" + "=" * 70)
print("TEST SUITE RUN COMPLETED")
print("=" * 70)
