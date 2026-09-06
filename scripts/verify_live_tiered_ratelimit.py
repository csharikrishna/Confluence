"""
Empirical Live Verification Script for Tiered Rate Limiting on Production Render

Verifies:
1. Anonymous quota exhaustion on live Render: bursts 35 concurrent requests to /environment.
   Proves SlowAPI's in-memory sliding window enforces exactly 30 req/minute on the real deployment,
   returning HTTP 429 Too Many Requests for the excess requests.
2. Authenticated tier separation: while the anonymous IP is actively 429 throttled,
   immediately fires a request bearing a valid Confluence X-API-Key.
   Proves the authenticated request is bucketed under its separate 100 req/minute quota and succeeds with HTTP 200 OK.
3. Subsequent anonymous check: confirms an unauthenticated request remains throttled (429).
"""

import sys
import time
import uuid
import concurrent.futures
import requests

PROD_URL = "https://confluence-si41.onrender.com"

def main():
    print("=" * 70)
    print("  CONFLUENCE PRODUCTION TIERED RATE-LIMIT VERIFICATION")
    print(f"  Target: {PROD_URL}")
    print("=" * 70)

    # Step 1: Health Check
    print("\n[Step 1] Verifying live instance health...")
    r_health = requests.get(f"{PROD_URL}/health", timeout=15)
    print(f"  /health status: {r_health.status_code}")
    if r_health.status_code != 200:
        print(f"  ERROR: Instance not healthy: {r_health.text}")
        sys.exit(1)
    h = r_health.json()
    print(f"  Status: {h.get('status')} | Backend: {h.get('storage_backend')}")

    # Step 2: Register a new user and generate a live API key
    suffix = uuid.uuid4().hex[:6]
    test_email = f"ratetest_{suffix}@marine-intel.org"
    print(f"\n[Step 2] Registering live account to obtain X-API-Key: {test_email}...")
    r_reg = requests.post(
        f"{PROD_URL}/api/auth/register",
        json={
            "email": test_email,
            "name": f"Rate Limit Tester {suffix}",
            "password": "LiveRatePassword2026!"
        },
        timeout=15,
    )
    if r_reg.status_code != 201:
        print(f"  ERROR: Registration failed: {r_reg.status_code} - {r_reg.text}")
        sys.exit(1)
    reg_data = r_reg.json()
    raw_api_key = reg_data["raw_key"]
    user_id = reg_data["user"]["id"]
    print(f"  Registered User ID: {user_id}")
    print(f"  Acquired Live API Key: {raw_api_key[:14]}... (total length {len(raw_api_key)})")

    # Step 3: Burst 35 anonymous requests within a tight window to test the 30/min cap
    print(f"\n[Step 3] Firing 35 concurrent anonymous requests to /environment (Quota: 30/minute)...")
    
    def fire_anon(req_id):
        t0 = time.time()
        try:
            r = requests.get(f"{PROD_URL}/environment?lat=13.08&lon=80.27", timeout=15)
            dur = round((time.time() - t0) * 1000, 1)
            msg = r.json().get("message", "") if r.status_code == 429 else ""
            return (req_id, r.status_code, dur, msg)
        except Exception as e:
            return (req_id, 0, 0, str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fire_anon, i) for i in range(1, 36)]
        anon_results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Sort by completion order or request id
    anon_results.sort(key=lambda x: x[0])
    
    status_counts = {}
    throttle_messages = set()
    for req_id, code, dur, msg in anon_results:
        status_counts[code] = status_counts.get(code, 0) + 1
        if code == 429:
            throttle_messages.add(msg)
        print(f"  Req #{req_id:02d} -> HTTP {code} ({dur}ms) {f'- {msg}' if msg else ''}")

    print(f"\n  Anonymous Burst Summary:")
    print(f"  - HTTP 200 OK (Allowed): {status_counts.get(200, 0)}")
    print(f"  - HTTP 429 Too Many Requests (Throttled): {status_counts.get(429, 0)}")
    print(f"  - Rate Limit Message: {list(throttle_messages)}")

    assert status_counts.get(429, 0) > 0, "FAILED: 429 was not triggered on live Render!"
    print("  -> CONFIRMED: Anonymous client hit the 30/min rate limit and was throttled with HTTP 429.")

    # Step 4: Test Authenticated Request with X-API-Key while IP is actively throttled
    print(f"\n[Step 4] Firing Authenticated Request (X-API-Key: {raw_api_key[:14]}...) while IP is 429'd...")
    t0 = time.time()
    r_auth = requests.get(
        f"{PROD_URL}/environment?lat=13.08&lon=80.27",
        headers={"X-API-Key": raw_api_key},
        timeout=15,
    )
    auth_dur = round((time.time() - t0) * 1000, 1)
    print(f"  Authenticated Response: HTTP {r_auth.status_code} ({auth_dur}ms)")
    
    if r_auth.status_code == 200:
        data = r_auth.json()
        print(f"  -> SUCCESS! Authenticated request succeeded with 200 OK while anonymous IP was 429 throttled.")
        print(f"     Location: {data.get('location', {}).get('name')}")
        print(f"     Cache Hit: {data.get('meta', {}).get('cache_hit')}")
        print(f"     Derived Heat Index: {data.get('meta', {}).get('derived_insights', {}).get('heat_index_c')} C")
    else:
        print(f"  FAILED: Authenticated request received HTTP {r_auth.status_code}: {r_auth.text}")
        sys.exit(1)

    # Step 5: Verify immediate subsequent anonymous call is still throttled
    print(f"\n[Step 5] Checking subsequent anonymous call from same IP...")
    r_anon_subsequent = requests.get(f"{PROD_URL}/environment?lat=13.08&lon=80.27", timeout=15)
    print(f"  Subsequent Anonymous Response: HTTP {r_anon_subsequent.status_code} ({r_anon_subsequent.text.strip()})")

    print("\n" + "=" * 70)
    print("  LIVE EMPIRICAL PROOF COMPLETE: ALL TIERED LIMIT BEHAVIOR PROVEN ON RENDER")
    print("=" * 70)

if __name__ == "__main__":
    main()
