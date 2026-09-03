"""
Optional alert delivery — the Phase 2C "stretch goal" from docs/phase2-plan.md
section 5: push a newly-firing alert to a Slack/Discord webhook.

Fully inert unless ALERT_WEBHOOK_URL is set. The payload includes both `text`
(the field Slack incoming webhooks read) and `content` (the field Discord
webhooks read), so the same URL works for either service without extra config.
Delivery is best-effort: a failed webhook call is logged and swallowed, never
raised, since it must not affect the API response already sent to the caller.
"""

import os
import logging
import requests

import storage

logger = logging.getLogger("environmental_api")

WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")
WEBHOOK_TIMEOUT = 5


def notify_alert(alert, location):
    """Best-effort webhook push for one triggered alert. No-op if unconfigured."""
    if not WEBHOOK_URL:
        return
    loc_name = (location or {}).get("name", "Unknown location")
    severity = (alert.get("severity") or "info").upper()
    message = f"[{severity}] {loc_name}: {alert.get('message')}"
    try:
        requests.post(WEBHOOK_URL, json={"text": message, "content": message}, timeout=WEBHOOK_TIMEOUT)
    except Exception as e:
        logger.warning(f"Alert webhook delivery failed: {e}")


def log_and_notify(lat, lon, alert, location):
    """Log the alert (storage.log_alert's cooldown dedupe applies) and only push
    a webhook notification when it's newly logged — never for a repeat within
    the cooldown window, so a 5-minute-cached endpoint hit repeatedly doesn't
    spam the channel with the same event.
    """
    newly_logged = storage.log_alert(lat, lon, alert)
    if newly_logged:
        notify_alert(alert, location)
    return newly_logged
