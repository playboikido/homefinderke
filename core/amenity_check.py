import requests


def check_nearby_amenities(lat, lng, claimed_school='', claimed_hospital='', claimed_stage='', radius_m=2000):
    """
    Queries OpenStreetMap for real schools/hospitals/bus stations near the given
    GPS point, and checks whether the landlord's claimed nearby places roughly
    match anything actually found nearby. Returns a dict for admin review only —
    never shown to the person who submitted the listing.
    """
    if not lat or not lng:
        return {'checked': False, 'reason': 'No GPS coordinates available'}

    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lng});
      node["amenity"="hospital"](around:{radius_m},{lat},{lng});
      node["amenity"="clinic"](around:{radius_m},{lat},{lng});
      node["highway"="bus_stop"](around:{radius_m},{lat},{lng});
      node["amenity"="bus_station"](around:{radius_m},{lat},{lng});
    );
    out body;
    """

    try:
        response = requests.post(
            'https://overpass-api.de/api/interpreter',
            data={'data': query},
            timeout=15,
            headers={'User-Agent': 'HomeFinderKE/1.0 (homefinder.ke.help@gmail.com)'}
        )
        response.raise_for_status()
        elements = response.json().get('elements', [])
    except Exception as e:
        return {'checked': False, 'reason': f'Lookup failed: {e}'}

    found_schools = [e['tags'].get('name', 'Unnamed school') for e in elements if e.get('tags', {}).get('amenity') == 'school']
    found_hospitals = [e['tags'].get('name', 'Unnamed hospital') for e in elements if e.get('tags', {}).get('amenity') in ('hospital', 'clinic')]
    found_stages = [e['tags'].get('name', 'Unnamed stage') for e in elements if e.get('tags', {}).get('amenity') == 'bus_station' or e.get('tags', {}).get('highway') == 'bus_stop']

    def fuzzy_match(claim, found_list):
        if not claim:
            return None  # nothing claimed, nothing to check
        claim_lower = claim.lower().strip()
        for f in found_list:
            if claim_lower in f.lower() or f.lower() in claim_lower:
                return True
        return False if found_list else None  # None = couldn't verify either way (OSM has no data there)

    return {
        'checked': True,
        'school_match': fuzzy_match(claimed_school, found_schools),
        'hospital_match': fuzzy_match(claimed_hospital, found_hospitals),
        'stage_match': fuzzy_match(claimed_stage, found_stages),
        'found_schools': found_schools[:5],
        'found_hospitals': found_hospitals[:5],
        'found_stages': found_stages[:5],
    }