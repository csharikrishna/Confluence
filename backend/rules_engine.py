"""
Phase 2C — Alerting / Reasoning Layer

A config-driven rules engine (no ML — see docs/phase2-plan.md section 7). Rules live
in alert_rules.json so thresholds can be tuned without a code change. Two rule
shapes are supported:

  - "threshold": evaluate a single field (raw or derived) against a static threshold.
  - "trend" / "trend_ratio": compare the current value against a reading from
    `window_hours` ago (via an injected `history_lookup` callable), for absolute-
    change and ratio-based conditions respectively. These need Phase 2A's stored
    history to exist yet — if none is available, the rule is silently skipped
    rather than raising, since a brand-new location simply has no history.
"""

import json
import os
from datetime import datetime, timezone

from utils import get_path

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert_rules.json")

_RULES_CACHE = None

_OPERATORS = {
    "gt": lambda v, t: v is not None and v > t,
    "gte": lambda v, t: v is not None and v >= t,
    "lt": lambda v, t: v is not None and v < t,
    "lte": lambda v, t: v is not None and v <= t,
    "eq": lambda v, t: v is not None and v == t,
    "in": lambda v, t: v is not None and v in t,
}


def load_rules(path=None, force_reload=False):
    global _RULES_CACHE
    if _RULES_CACHE is None or force_reload or path is not None:
        p = path or RULES_PATH
        with open(p, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if path is None:
            _RULES_CACHE = loaded
        return loaded
    return _RULES_CACHE


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_alert(rule, value, triggered_at, extra_ctx=None):
    ctx = {"value": value, "window_hours": rule.get("window_hours")}
    if extra_ctx:
        ctx.update(extra_ctx)
    try:
        message = rule["message"].format(**ctx)
    except Exception:
        message = rule.get("message", rule["id"])

    return {
        "id": rule["id"],
        "description": rule.get("description"),
        "severity": rule.get("severity", "info"),
        "message": message,
        "field": rule.get("field"),
        "value": value,
        "threshold": rule.get("threshold"),
        "triggered_at": triggered_at,
    }


def _resolve_context_fields(rule, context):
    extra = {}
    for key, path in rule.get("context_fields", {}).items():
        extra[key] = get_path(context, path)
    return extra


def evaluate_alerts(data, derived, lat=None, lon=None, history_lookup=None, rules=None):
    """Evaluate every rule against one snapshot's `data` + `derived` insights.

    history_lookup, if given, must be callable(lat, lon, hours_ago) -> data dict|None
    (storage.get_reading_hours_ago matches this signature).
    """
    rules = rules if rules is not None else load_rules()
    context = {"data": data or {}, "derived": derived or {}}
    now = _now_iso()
    alerts = []

    for rule in rules:
        op = _OPERATORS.get(rule.get("operator"))
        if op is None:
            continue

        rtype = rule.get("type", "threshold")

        if rtype == "threshold":
            value = get_path(context, rule["field"])
            if op(value, rule["threshold"]):
                extra_ctx = _resolve_context_fields(rule, context)
                alerts.append(_build_alert(rule, value, now, extra_ctx))

        elif rtype in ("trend", "trend_ratio"):
            if history_lookup is None or lat is None or lon is None:
                continue
            window_hours = rule.get("window_hours", 3)
            try:
                past_data = history_lookup(lat, lon, window_hours)
            except Exception:
                past_data = None
            if not past_data:
                continue

            current_val = get_path(context, rule["field"])
            past_val = get_path({"data": past_data}, rule["field"])
            if current_val is None or past_val is None:
                continue

            if rtype == "trend":
                metric = round(current_val - past_val, 2)
            else:
                if past_val == 0:
                    continue
                metric = round(current_val / past_val, 2)

            if op(metric, rule["threshold"]):
                alerts.append(_build_alert(rule, metric, now))

    return alerts
