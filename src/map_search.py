import logging
from geopy.geocoders import Nominatim
import overpy
import math

logger = logging.getLogger(__name__)

# Initialize singletons
geolocator = Nominatim(user_agent="off_grid_sms_agent_v2")
api = overpy.Overpass()

def geo_locate(place_name):
    """
    Returns (lat, lon, address) for a given place name.
    """
    logger.info(f"Geolocating: {place_name}")
    try:
        location = geolocator.geocode(place_name)
        if location:
            return location.latitude, location.longitude, location.address
        return None
    except Exception as e:
        logger.error(f"Geocoding failed: {e}")
        return None

def find_poi(lat, lon, category, radius=20000):
    """
    Finds points of interest near a location using Overpass API.
    Common categories: 'hot_spring', 'swimming_hole', 'cave', 'camp_site'
    """
    logger.info(f"Finding POI: {category} near {lat},{lon} (r={radius})")
    
    # Map common terms to OSM tags
    queries = {
        "hot_spring": f"""
            (
             node["natural"="hot_spring"](around:{radius},{lat},{lon});
             node["spring:type"="hot"](around:{radius},{lat},{lon});
             way["natural"="hot_spring"](around:{radius},{lat},{lon});
            );
        """,
        "swimming_hole": f"""
            (
             node["sport"="swimming"](around:{radius},{lat},{lon});
             node["natural"="water"]["swimming"="yes"](around:{radius},{lat},{lon});
             way["natural"="water"]["swimming"="yes"](around:{radius},{lat},{lon});
            );
        """,
        "campsite": f"""
            (
             node["tourism"="camp_site"](around:{radius},{lat},{lon});
             way["tourism"="camp_site"](around:{radius},{lat},{lon});
            );
        """
    }
    
    query_body = queries.get(category)
    if not query_body:
        # Generic fallback? Or error.
        return []
        
    full_query = f"[out:json];{query_body}out center 10;" # Limit to 10
    
    try:
        result = api.query(full_query)
        pois = []
        for node in result.nodes:
            name = node.tags.get("name", "Unnamed")
            pois.append({"name": name, "lat": float(node.lat), "lon": float(node.lon), "tags": node.tags, "type": "node"})
        
        for way in result.ways:
            name = way.tags.get("name", "Unnamed")
            # Use center if available (OverPy 'out center' populates center_lat/lon?)
            # Actually OverPy might not parse center easily without extra logic, 
            # but usually result.ways have .center_lat if 'out center' is used.
            # Let's trust OverPy's center handling or just use first node.
            lat_w = float(way.center_lat) if hasattr(way, 'center_lat') and way.center_lat else lat
            lon_w = float(way.center_lon) if hasattr(way, 'center_lon') and way.center_lon else lon
            pois.append({"name": name, "lat": lat_w, "lon": lon_w, "tags": way.tags, "type": "way"})
            
        return pois
    except Exception as e:
        logger.error(f"Overpass query failed: {e}")
        return []

def find_trails(lat, lon, radius=5000):
    """
    Finds hiking trails near a location.
    """
    query = f"""
        [out:json];
        (
          way["highway"="path"]["sac_scale"](around:{radius},{lat},{lon});
          way["highway"="path"]["route"="hiking"](around:{radius},{lat},{lon});
          relation["route"="hiking"](around:{radius},{lat},{lon});
        );
        out tags center 10;
    """
    try:
        result = api.query(query)
        trails = []
        for way in result.ways:
            name = way.tags.get("name", "Unnamed Trail")
            length = "Unknown" # Calculating length requires geometry, complex.
            trails.append({"name": name, "tags": way.tags, "type": "trail"})
        return trails
    except Exception as e:
        logger.error(f"Trail search failed: {e}")
        return []

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    loc = geo_locate("Gatlinburg, TN")
    if loc:
        print(f"Location: {loc}")
        pois = find_poi(loc[0], loc[1], "swimming_hole")
        print("\nSwimming Holes:", json.dumps(pois, indent=2))
        
        trails = find_trails(loc[0], loc[1])
        print("\nTrails:", json.dumps(trails, indent=2))
