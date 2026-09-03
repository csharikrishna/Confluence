"""Small shared helpers used across the Phase 2 modules."""


def get_path(obj, dotted):
    """Resolve a dotted path like 'data.weather.temperature_c' against nested dicts.

    Returns None if any segment is missing or the object isn't a dict at that point,
    instead of raising — snapshots frequently have partial/failed domains.
    """
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur
