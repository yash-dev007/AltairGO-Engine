import math

def _is_truthy(value) -> bool:
    """Parse a boolean-ish value from env vars or config."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _extract_destination_names(payload: dict) -> list[str]:
    names = []
    for item in payload.get("selected_destinations", []) or []:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = item
        if name:
            names.append(name)
    return names

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Calculate the great-circle distance between two points on Earth (in km)."""
    R = 6371  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
