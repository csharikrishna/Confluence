"""
Confluence — Phase 3: Minimal Chatbot CLI Client

Usage:
  python chat.py "is it safe to fish near Chennai right now"
  python chat.py --debug "What are wave conditions in Kochi?"
  python chat.py  (enters interactive conversational loop)
"""

import sys
import os
import json
import argparse
from chatbot import ask_coastal_assistant, get_all_locations

# Windows console UTF-8 fix
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_response(result: dict, show_grounding: bool = False):
    print("\n" + "=" * 70)
    matched = result.get("location_matched")
    if matched:
        coords = result.get("coordinates") or {}
        lat_lon = f" ({coords.get('lat')}, {coords.get('lon')})" if coords else ""
        print(f"{GREEN}{BOLD}Location Matched:{RESET} {matched}{lat_lon}")
    else:
        print(f"{YELLOW}{BOLD}Location:{RESET} Unregistered / General Query")

    alerts = result.get("active_alerts") or []
    if alerts:
        print(f"{RED}{BOLD}Active Alerts Detected ({len(alerts)}):{RESET}")
        for alert in alerts:
            severity = alert.get("severity", "warning").upper()
            title = alert.get("title", alert.get("id", "Hazard"))
            msg = alert.get("message", alert.get("description", ""))
            print(f"  {RED}[{severity}] {title}:{RESET} {msg}")

    print("-" * 70)
    print(f"{BOLD}Answer:{RESET}\n")
    print(result.get("answer", ""))
    print("=" * 70)

    if show_grounding and result.get("grounding_data"):
        print(f"\n{CYAN}{BOLD}[DEBUG] Raw Grounding Data Snapshot:{RESET}")
        print(json.dumps(result["grounding_data"], indent=2, ensure_ascii=False))
        print("=" * 70 + "\n")


def interactive_mode(show_grounding: bool = False, bypass_cache: bool = False):
    registered = [loc["name"] for loc in get_all_locations()]
    print(f"\n{CYAN}{BOLD}=== Confluence Coastal AI CLI (Phase 3) ==={RESET}")
    print(f"Grounded in live environmental telemetry across 5 stations:")
    for name in registered:
        print(f"  • {name}")
    print(f"\nType your question, or type {BOLD}'exit'{RESET} or {BOLD}'quit'{RESET} to leave.\n")

    while True:
        try:
            query = input(f"{BOLD}Ask Confluence > {RESET}").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("\nGoodbye.")
                break

            print("\nSynthesizing observations and querying grounded assistant...")
            res = ask_coastal_assistant(query, bypass_cache=bypass_cache)
            print_response(res, show_grounding=show_grounding)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\n{RED}Error:{RESET} {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Confluence Phase 3 Coastal Chatbot CLI")
    parser.add_argument("question", nargs="*", help="Plain-language coastal question")
    parser.add_argument("--debug", "--grounding", action="store_true", help="Print raw grounding data snapshot JSON")
    parser.add_argument("--bypass-cache", action="store_true", help="Force fresh fetch of environmental telemetry")

    args = parser.parse_args()

    if args.question:
        full_query = " ".join(args.question)
        print(f"\nProcessing query: '{full_query}'...")
        try:
            res = ask_coastal_assistant(full_query, bypass_cache=args.bypass_cache)
            print_response(res, show_grounding=args.debug)
        except Exception as e:
            print(f"\n{RED}Error:{RESET} {e}\n")
            sys.exit(1)
    else:
        interactive_mode(show_grounding=args.debug, bypass_cache=args.bypass_cache)


if __name__ == "__main__":
    main()
