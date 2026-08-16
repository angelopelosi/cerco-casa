import math

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def within_radius(center_lat: float, center_lon: float, lat: float | None, lon: float | None, radius_km: float) -> bool:
    if lat is None or lon is None:
        return False
    return haversine_km(center_lat, center_lon, lat, lon) <= radius_km
