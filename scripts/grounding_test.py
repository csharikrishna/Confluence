"""
Model Grounding Comparison Test:
Testing NVIDIA Nemotron reasoning model (nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
With vs Without Grounded Unified Environmental Intelligence JSON.

Run from anywhere: python scripts/grounding_test.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from environmental_data import get_environmental_snapshot, LOCATION

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
API_KEY = os.getenv("NVIDIA_API_KEY")
MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}

QUESTION = (
    "What are the environmental, marine, and air quality conditions along the "
    "Chennai coastline right now, and what specific advice should be given to "
    "local artisanal fishermen, coastal residents, and outdoor workers today?"
)

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_grounding_comparison.json")


def call_nvidia_model(messages, max_tokens=1024, retries=5):
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.5,
        "top_p": 0.95,
    }

    for attempt in range(1, retries + 1):
        try:
            r = requests.post(INVOKE_URL, headers=HEADERS, json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            elif r.status_code == 503:
                print(f"Attempt {attempt}: 503 Service Unavailable (worker capacity). Retrying in {attempt * 3}s...")
                time.sleep(attempt * 3)
            else:
                print(f"Attempt {attempt}: Error {r.status_code} - {r.text[:200]}")
                time.sleep(attempt * 2)
        except Exception as e:
            print(f"Attempt {attempt}: Request error {e}")
            time.sleep(attempt * 2)

    raise RuntimeError(f"Failed to get response from {MODEL} after {retries} attempts.")


def main():
    print("=" * 70)
    print("STEP 1: Fetching Live Unified Environmental Snapshot for Chennai Coast...")
    print("=" * 70)
    snapshot = get_environmental_snapshot(LOCATION["lat"], LOCATION["lon"], LOCATION["name"])
    snapshot_json = json.dumps(snapshot, indent=2)
    print("Snapshot fetched successfully!\n")

    print("=" * 70)
    print("STEP 2: Querying Nemotron Model WITHOUT Data (Ungrounded Baseline)...")
    print("=" * 70)
    ungrounded_messages = [
        {
            "role": "user",
            "content": (
                "You are an environmental assistant.\n\n"
                f"Question: {QUESTION}"
            ),
        }
    ]
    ungrounded_response = call_nvidia_model(ungrounded_messages)
    print("Ungrounded Response received!\n")

    print("=" * 70)
    print("STEP 3: Querying Nemotron Model WITH Unified Data (Grounded)...")
    print("=" * 70)
    grounded_messages = [
        {
            "role": "user",
            "content": (
                "You are an environmental intelligence assistant.\n"
                "Here is the verified real-time environmental snapshot from our unified data endpoint:\n\n"
                f"```json\n{snapshot_json}\n```\n\n"
                f"Question: {QUESTION}\n\n"
                "Please synthesize the multi-domain conditions (weather, ocean, air, and climate baseline) "
                "and provide concrete, actionable guidance grounded directly in these verified observations."
            ),
        }
    ]
    grounded_response = call_nvidia_model(grounded_messages)
    print("Grounded Response received!\n")

    # Save to a structured JSON file for records
    results = {
        "model": MODEL,
        "question": QUESTION,
        "snapshot": snapshot,
        "ungrounded_response": ungrounded_response,
        "grounded_response": grounded_response,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Full test comparison saved to {OUTPUT_PATH}\n")

    print("=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)
    print("\n--- [A] UNGROUNDED RESPONSE (WITHOUT DATA) ---\n")
    print(ungrounded_response)
    print("\n--- [B] GROUNDED RESPONSE (WITH UNIFIED ENDPOINT DATA) ---\n")
    print(grounded_response)


if __name__ == "__main__":
    main()
