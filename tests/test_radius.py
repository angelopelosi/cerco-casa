from scraper.radius import haversine_km, within_radius

def test_haversine_same_point_is_zero():
    assert haversine_km(43.5, 13.2, 43.5, 13.2) == 0

def test_haversine_one_degree_longitude_at_equator_is_about_111km():
    distance = haversine_km(0, 0, 0, 1)
    assert 110 < distance < 112

def test_within_radius_true_when_inside():
    assert within_radius(43.5, 13.2, 43.5, 13.21, 20) is True

def test_within_radius_false_when_outside():
    assert within_radius(43.5, 13.2, 44.5, 14.2, 20) is False

def test_within_radius_false_when_coords_missing():
    assert within_radius(43.5, 13.2, None, None, 20) is False
