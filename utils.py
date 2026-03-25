import math


def fmt_time(seconds):
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def fmt_pace(min_per_km):
    """Format decimal minutes/km as MM:SS."""
    if min_per_km is None or not math.isfinite(min_per_km) or min_per_km <= 0:
        return '—'
    m = int(min_per_km)
    s = int((min_per_km - m) * 60)
    return f'{m}:{s:02d}'


def haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in metres between two GPS coordinates."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
