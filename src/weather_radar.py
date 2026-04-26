"""
Weather Radar with OpenStreetMap Tile Base
Uses OSM tiles (stitched) as base layer with transparent radar overlay.
"""
import os
import math
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import datetime

US_STATES = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC'
}

def get_lat_lon(location):
    """Resolve location to lat/lon using Nominatim (OSM)."""
    try:
        headers = {"User-Agent": "OffGridAgent/1.0", "Accept": "application/json"}
        if location.isdigit() and len(location) == 5:
            url = f"https://nominatim.openstreetmap.org/search?postalcode={location}&country=us&format=json&limit=1&addressdetails=1"
        else:
            url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1&addressdetails=1"
            
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        
        if not data:
            return None, None, None
            
        lat = float(data[0]['lat'])
        lon = float(data[0]['lon'])
        
        # Extract State
        state_abbr = ""
        address = data[0].get('address', {})
        state_name = address.get('state')
        if state_name:
            state_abbr = US_STATES.get(state_name, state_name[:2].upper())
            
        return lat, lon, state_abbr
    except Exception as e:
        print(f"[Radar] Geo lookup failed: {e}")
        return None, None, None

def get_timezone_offset(lat, lon):
    """Get timezone offset in seconds and abbreviation using Open-Meteo."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m&timezone=auto"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        offset = data.get("utc_offset_seconds", 0)
        iana_tz = data.get("timezone", "UTC")
        raw_abbrev = data.get("timezone_abbreviation", "UTC")
        
        # Friendly US Mappings
        friendly_abbrev = raw_abbrev
        if "America/New_York" in iana_tz or "America/Detroit" in iana_tz or "America/Indiana" in iana_tz:
            friendly_abbrev = "EDT" if "Daylight" in raw_abbrev or offset == -14400 else "EST"
        elif "America/Chicago" in iana_tz:
            friendly_abbrev = "CDT" if "Daylight" in raw_abbrev or offset == -18000 else "CST"
        elif "America/Denver" in iana_tz:
            friendly_abbrev = "MDT" if "Daylight" in raw_abbrev or offset == -21600 else "MST"
        elif "America/Los_Angeles" in iana_tz or "America/Phoenix" in iana_tz:
            friendly_abbrev = "PDT" if "Daylight" in raw_abbrev or offset == -25200 else "PST"
            
        # Refine logic: Open-Meteo abbreviation for GMT-5 is just "GMT-5" usually.
        # Check offset directly for standard times?
        # EST = -5h (-18000), EDT = -4h (-14400)
        # CST = -6h (-21600), CDT = -5h (-18000)
        # So offset alone is ambiguous (-18000 can be EST or CDT).
        # Use IANA string.
        
        if "New_York" in iana_tz or "Detroit" in iana_tz: friendly_abbrev = "ET"
        elif "Chicago" in iana_tz: friendly_abbrev = "CT" 
        elif "Denver" in iana_tz: friendly_abbrev = "MT"
        elif "Los_Angeles" in iana_tz or "Vancouver" in iana_tz: friendly_abbrev = "PT"
        
        # Refinement: Add S or D based on offset
        # ET: Standard -5, Daylight -4
        if friendly_abbrev == "ET": friendly_abbrev = "EDT" if offset == -14400 else "EST"
        elif friendly_abbrev == "CT": friendly_abbrev = "CDT" if offset == -18000 else "CST"
        elif friendly_abbrev == "MT": friendly_abbrev = "MDT" if offset == -21600 else "MST"
        elif friendly_abbrev == "PT": friendly_abbrev = "PDT" if offset == -25200 else "PST"
            
        print(f"[Radar] Timezone Info: {friendly_abbrev} (Offset: {offset}, Zone: {iana_tz})") # Debug
        return offset, friendly_abbrev
    except Exception as e:
        print(f"[Radar] Timezone lookup failed: {e}")
        return 0, "UTC"

def deg2num(lat_deg, lon_deg, zoom):
    """Convert lat/lon to OSM tile coordinates"""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    """Convert OSM tile to lat/lon"""
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def fetch_osm_tile(x, y,zoom):
    """Fetch a single OSM tile (256x256)"""
    subdomain = ['a', 'b', 'c'][hash(f"{x}{y}") % 3]
    url = f"https://{subdomain}.tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    
    headers = {'User-Agent': 'OffGridWeatherRadar/1.0'}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return Image.open(BytesIO(res.content))
    except:
        pass
    
    return None

def build_osm_base(lat, lon, miles, output_size=800):
    """Build OSM base map by stitching tiles, centered on exact lat/lon"""
    # Logic adjusted for 3x3 tile grid coverage at ~40deg Lat
    # Zoom 3 covers ~7000mi width -> Radius ~3500mi
    # Zoom 4 covers ~3500mi width -> Radius ~1750mi
    # Zoom 5 covers ~1750mi width -> Radius ~875mi
    # Zoom 6 covers ~875mi width  -> Radius ~430mi
    # Zoom 7 covers ~430mi width  -> Radius ~215mi
    # Zoom 8 covers ~215mi width  -> Radius ~100mi
    
    if miles > 1750:
        zoom = 3  # Continent view
    elif miles > 850:
        zoom = 4  # Large Region
    elif miles > 425:
        zoom = 5  # Multi-state
    elif miles > 200:
        zoom = 6
    elif miles > 100:
        zoom = 7
    elif miles > 50:
        zoom = 8
    elif miles > 25:
        zoom = 9
    elif miles > 12:
        zoom = 10
    else:
        zoom = 11
    
    print(f"  Using zoom level: {zoom}")
    
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile_f = (lon + 180.0) / 360.0 * n
    ytile_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    
    center_tile_x = int(xtile_f)
    center_tile_y = int(ytile_f)
    
    offset_x = xtile_f - center_tile_x
    offset_y = ytile_f - center_tile_y
    
    tiles_needed = 3
    
    tiles = {}
    for dy in range(-tiles_needed, tiles_needed + 1):
        for dx in range(-tiles_needed, tiles_needed + 1):
            tile_x = center_tile_x + dx
            tile_y = center_tile_y + dy
            
            tile = fetch_osm_tile(tile_x, tile_y, zoom)
            if tile:
                tiles[(dx, dy)] = tile
    
    if not tiles:
        print("  [WARN] No OSM tiles fetched, using fallback")
        return None
    
    print(f"  Fetched {len(tiles)} tiles")
    
    tile_size = 256
    grid_size = tiles_needed * 2 + 1
    full_size = grid_size * tile_size
    
    canvas = Image.new('RGB', (full_size, full_size), (200, 200, 200))
    
    for (dx, dy), tile in tiles.items():
        x_offset = (dx + tiles_needed) * tile_size
        y_offset = (dy + tiles_needed) * tile_size
        canvas.paste(tile, (x_offset, y_offset))
    
    center_pixel_x = (tiles_needed + offset_x) * tile_size
    center_pixel_y = (tiles_needed + offset_y) * tile_size
    
    half_output = output_size // 2
    
    left = int(center_pixel_x - half_output)
    top = int(center_pixel_y - half_output)
    right = left + output_size
    bottom = top + output_size
    
    if left < 0 or top < 0 or right > full_size or bottom > full_size:
        left = max(0, left)
        top = max(0, top)
        right = min(full_size, right)
        bottom = min(full_size, bottom)
    
    cropped = canvas.crop((left, top, right, bottom))
    
    if cropped.size != (output_size, output_size):
        cropped = cropped.resize((output_size, output_size), Image.Resampling.LANCZOS)
    
    return cropped.convert('RGBA')

def lonlat_to_3857(lon, lat):
    """Convert Lat/Lon to Web Mercator (EPSG:3857)"""
    r_major = 6378137.0
    x = r_major * math.radians(lon)
    lat = max(min(lat, 89.5), -89.5)
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180.0)
    y = y * r_major * math.pi / 180.0
    return x, y

def fetch_wms_layer_at_time(lat, lon, miles, layers, timestamp, srs="EPSG:3857"):
    """Fetch WMS layer at a specific time (for animations)"""
    center_x, center_y = lonlat_to_3857(lon, lat)
    radius_m = miles * 1609.34
    
    bbox_str = f"{center_x - radius_m},{center_y - radius_m},{center_x + radius_m},{center_y + radius_m}"
    
    # Use time-enabled WMS endpoint
    # Determine which WMS script to use based on layers
    if "n0r" in layers:
        base_url = "https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r-t.cgi"
    else:
        base_url = "https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q-t.cgi"
    
    # Format timestamp for WMS TIME parameter (ISO 8601)
    time_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layers,
        "SRS": srs,
        "BBOX": bbox_str,
        "WIDTH": "800",
        "HEIGHT": "800",
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "BGCOLOR": "0x000000",
        "TIME": time_str
    }
    
    res = requests.get(base_url, params=params, timeout=20)
    
    if res.status_code == 200 and res.headers.get('content-type', '').startswith('image'):
        return Image.open(BytesIO(res.content)).convert("RGBA")
    
    return None

def fetch_wms_layer(lat, lon, miles, layers, srs="EPSG:3857"):
    """Fetch a single WMS layer as PIL Image."""
    center_x, center_y = lonlat_to_3857(lon, lat)
    radius_m = miles * 1609.34
    
    bbox_str = f"{center_x - radius_m},{center_y - radius_m},{center_x + radius_m},{center_y + radius_m}"
    
    if "n0r" in layers:
        base_url = "https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0r.cgi"
    else:
        base_url = "https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q.cgi"
    
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.1.1",
        "REQUEST": "GetMap",
        "LAYERS": layers,
        "SRS": srs,
        "BBOX": bbox_str,
        "WIDTH": "800",
        "HEIGHT": "800",
        "FORMAT": "image/png",
        "TRANSPARENT": "TRUE",
        "BGCOLOR": "0x000000"
    }
    
    res = requests.get(base_url, params=params, timeout=20)
    
    if res.status_code == 200 and res.headers.get('content-type', '').startswith('image'):
        return Image.open(BytesIO(res.content)).convert("RGBA")
    
    return None

def make_transparent(img, threshold=4):
    """Convert dark pixels to transparent (lower threshold = more sensitive to dim radar)"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    data = img.getdata()
    new_data = []
    
    for item in data:
        # Check if pixel is effectively black/empty
        if item[0] < threshold and item[1] < threshold and item[2] < threshold:
            new_data.append((0, 0, 0, 0))
        else:
            # Keep the pixel, but we will boost it later
            new_data.append(item)
    
    img.putdata(new_data)
    return img

def boost_saturation(img, factor=1.5):
    """Increase color saturation and ensure radar is opaque."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    data = img.getdata()
    new_data = []
    
    for r, g, b, a in data:
        if a > 0:
            # Convert to float for math
            rf, gf, bf = float(r), float(g), float(b)
            avg = (rf + gf + bf) / 3.0
            
            # More aggressive saturation: push colors further from gray
            rn = int(min(255, max(0, avg + (rf - avg) * factor)))
            gn = int(min(255, max(0, avg + (gf - avg) * factor)))
            bn = int(min(255, max(0, avg + (bf - avg) * factor)))
            
            # For radar, we want to ensure these colors POP
            # If it's a "dim" color, boost its brightness too
            max_v = max(rn, gn, bn)
            if max_v < 100:
                 scale = 100.0 / max_v if max_v > 0 else 1.0
                 rn = int(min(255, rn * scale))
                 gn = int(min(255, gn * scale))
                 bn = int(min(255, bn * scale))
            
            # Force high opacity for detected radar so it's not "noisy transparency"
            new_data.append((rn, gn, bn, 255))
        else:
            new_data.append((r, g, b, a))
    
    img.putdata(new_data)
    return img

def adjust_opacity(img, opacity=0.7):
    """Adjust overall image opacity (0.0 to 1.0)"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    data = img.getdata()
    new_data = []
    
    for r, g, b, a in data:
        new_alpha = int(a * opacity)
        new_data.append((r, g, b, new_alpha))
    
    img.putdata(new_data)
    return img

def generate_radar_images(location, miles=30):
    """Generate radar with OSM base map."""
    output_dir = "weather"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[Radar] Locating '{location}'...")
    lat, lon, state = get_lat_lon(location)
    
    if lat is None or lon is None:
        print(f"[Radar] Could not locate '{location}'")
        return []
        
    print(f"[Radar] Coordinates: {lat}, {lon}, State: {state}")
    
    print("[Radar] Building OpenStreetMap base...")
    canvas = build_osm_base(lat, lon, miles)
    
    if canvas is None:
        canvas = Image.new("RGBA", (800, 800), (50, 50, 50, 255))
    else:
        # Reduce map opacity to make weather stand out
        canvas = adjust_opacity(canvas, opacity=0.7)
    
    active_layers = ["OpenStreetMap"]
    
    print("[Radar] Fetching precipitation layer...")
    # Use Base Reflectivity (n0r) for better standard radar appearance
    radar = fetch_wms_layer(lat, lon, miles, "nexrad-n0r-900913") 
    if not radar:
        print("  [WARN] n0r failed, trying n0q...")
        radar = fetch_wms_layer(lat, lon, miles, "nexrad-n0q-900913")
        
    if radar:
        radar = make_transparent(radar, threshold=4)
        radar = boost_saturation(radar, factor=1.2)
        # Smooth the "noise" and "blocky" look
        radar = radar.filter(ImageFilter.BoxBlur(1))
        # User requested less see-through -> 45% opacity
        radar = adjust_opacity(radar, opacity=0.45)
        canvas = Image.alpha_composite(canvas, radar)
        active_layers.append("Precipitation")
    
    print("[Radar] Checking warnings...")
    sbw = fetch_wms_layer(lat, lon, miles, "sbw")
    if sbw:
        sbw = make_transparent(sbw, threshold=8)
        sbw = boost_saturation(sbw, factor=1.3)
        canvas = Image.alpha_composite(canvas, sbw)
        active_layers.append("Warnings")
        print("  [ALERT] Warnings active")
    
    print("[Radar] Checking watches...")
    watches = fetch_wms_layer(lat, lon, miles, "watches")
    if watches:
        watches = make_transparent(watches, threshold=8)
        watches = boost_saturation(watches, factor=1.3)
        canvas = Image.alpha_composite(canvas, watches)
        active_layers.append("Watches")
        print("  [NOTICE] Watches active")
    
    draw = ImageDraw.Draw(canvas)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 16)
        tiny_font = ImageFont.truetype("arial.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        tiny_font = ImageFont.load_default()
    
    # --- Top Header ---
    draw.rectangle([(0, 0), (800, 70)], fill=(0, 0, 0, 180))
    # Add State if available, force Title Case for location
    loc_title = location.strip().title()
    title_text = f"{loc_title}, {state} - {miles}mi" if state else f"{loc_title} - {miles}mi"
    
    draw.text((10, 10), title_text, fill=(255, 255, 255, 255), font=title_font)
    
    # Get Local Time
    tz_offset, tz_abbrev = get_timezone_offset(lat, lon)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    local_now = utc_now + datetime.timedelta(seconds=tz_offset)
    
    timestamp_str = local_now.strftime(f"%Y-%m-%d %H:%M {tz_abbrev}")
    draw.text((10, 45), timestamp_str, fill=(200, 200, 200, 255), font=small_font)
    
    # --- Bottom Bar ---
    draw.rectangle([(0, 730), (800, 800)], fill=(0, 0, 0, 160))
    
    # Layers (Bottom Left)
    draw.text((10, 775), f"Layers: {', '.join(active_layers)}", fill=(150, 150, 150, 255), font=tiny_font)
    
    # Alerts Legend (Bottom Right-ish / Center)
    if "Warnings" in active_layers or "Watches" in active_layers:
        legend_x = 680
        draw.text((legend_x, 740), "Alerts:", fill=(255, 255, 255, 255), font=tiny_font)
        if "Warnings" in active_layers:
            draw.rectangle([(legend_x, 755), (legend_x + 20, 770)], fill=(255, 0, 0, 200))
            draw.text((legend_x + 25, 755), "Warning", fill=(255, 100, 100, 255), font=tiny_font)
    
    # Precipitation Legend (Bottom Right)
    if "Precipitation" in active_layers:
        leg_start_x = 360
        leg_y = 750
        bar_width = 400
        bar_height = 15
        
        draw.text((leg_start_x, leg_y - 15), "Precipitation (dBZ):", fill=(255, 255, 255, 255), font=tiny_font)
        
        color_stops = [
            (100, 200, 255), (0, 255, 0), (255, 255, 0), 
            (255, 140, 0), (255, 0, 0), (255, 0, 255)
        ]
        labels = ["Light", "Mod", "Heavy", "V.Hv", "Sev", "Ext"]
        
        for x in range(bar_width):
            position = x / bar_width
            segment_index = min(int(position * (len(color_stops) - 1)), len(color_stops) - 2)
            segment_position = (position * (len(color_stops) - 1)) - segment_index
            
            c1 = color_stops[segment_index]
            c2 = color_stops[segment_index + 1]
            
            r = int(c1[0] + (c2[0] - c1[0]) * segment_position)
            g = int(c1[1] + (c2[1] - c1[1]) * segment_position)
            b = int(c1[2] + (c2[2] - c1[2]) * segment_position)
            
            draw.line([(leg_start_x + x, leg_y), (leg_start_x + x, leg_y + bar_height)], fill=(r, g, b, 255))
        
        draw.rectangle([(leg_start_x, leg_y), (leg_start_x + bar_width, leg_y + bar_height)], outline=(200, 200, 200, 255), width=1)
        
        label_spacing = bar_width // len(labels)
        for i, label in enumerate(labels):
            x_pos = leg_start_x + (i * label_spacing) + (label_spacing // 2)
            draw.line([(x_pos, leg_y + bar_height), (x_pos, leg_y + bar_height + 3)], fill=(200, 200, 200, 255), width=1)
            bbox = draw.textbbox((0, 0), label, font=tiny_font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_pos - text_width // 2, leg_y + bar_height + 4), label, fill=(220, 220, 220, 255), font=tiny_font)
    
    safe_loc = "".join([c for c in location if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
    filename = f"radar_map_{safe_loc}_{miles}mi.png"
    output_path = os.path.join(output_dir, filename)
    
    canvas.save(output_path)
    print(f"[Radar] Saved: {output_path}")
    
    return [output_path]

def generate_radar_image(location, miles=30):
    paths = generate_radar_images(location, miles)
    return paths[0] if paths else None

def generate_radar_animation(location, miles=30, duration_minutes=30):
    """
    Generate animated GIF of radar loop.
    """
    output_dir = "weather"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"[Radar Animation] Locating '{location}'...")
    lat, lon, state = get_lat_lon(location)
    
    if lat is None or lon is None:
        print(f"[Radar Animation] Could not locate '{location}'")
        return None
    
    print(f"[Radar Animation] Generating {duration_minutes}-minute loop...")
    
    # Get Timezone Info once
    tz_offset, tz_abbrev = get_timezone_offset(lat, lon)
    
    # 1. Create Brighter Dark Base Map
    # User requested to "go halfway brighter" from previous 0.5 -> 0.75
    raw_map = build_osm_base(lat, lon, miles)
    
    # Solid black background
    base_bg = Image.new("RGBA", (800, 800), (0, 0, 0, 255))
    
    if raw_map:
        # Make map 75% transparent (more visible than 0.5)
        osm_layer = adjust_opacity(raw_map, opacity=0.75)
        # Composite map onto black background
        base_frame = Image.alpha_composite(base_bg, osm_layer)
    else:
        # Fallback if map fails
        base_frame = base_bg
        
    active_layers = ["OpenStreetMap", "Precipitation"]
    
    # Fetch Warnings and Watches ONCE
    print("[Radar Animation] Fetching overlays...")
    sbw_layer = None
    sbw = fetch_wms_layer(lat, lon, miles, "sbw")
    if sbw:
        sbw = make_transparent(sbw, threshold=8)
        sbw = boost_saturation(sbw, factor=1.3)
        sbw_layer = sbw
        active_layers.append("Warnings")
        print("  [ALERT] Warnings active")
        
    watches_layer = None
    watches = fetch_wms_layer(lat, lon, miles, "watches")
    if watches:
        watches = make_transparent(watches, threshold=8)
        watches = boost_saturation(watches, factor=1.3)
        watches_layer = watches
        active_layers.append("Watches")
        print("  [NOTICE] Watches active")
    
    # Calculate time intervals
    # Calculate time intervals based on duration (User Requested)
    # <= 80 mins: 5 min intervals
    # 80-150 mins: 10 min intervals
    # > 150 mins: 15 min intervals
    interval_minutes = 5
    if duration_minutes > 150:
        interval_minutes = 15
    elif duration_minutes > 80:
        interval_minutes = 10
        
    print(f"[Radar Animation] Interval set to {interval_minutes} minutes")
    
    frames = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Check fonts once
    try:
        title_font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 16)
        tiny_font = ImageFont.truetype("arial.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
        tiny_font = ImageFont.load_default()
    
    # Generate frames going backwards in time
    for i in range(0, duration_minutes, interval_minutes):
        # Calculate offset and round to nearest 5 minutes
        time_offset = now - datetime.timedelta(minutes=i)
        # Round the timestamp down to the nearest 5-minute mark
        # Most reliable way to hit a valid WMS snapshot
        rounded_minutes = (time_offset.minute // 5) * 5
        timestamp = time_offset.replace(minute=rounded_minutes, second=0, microsecond=0)
        
        print(f"  Fetching frame: -{i} min (Actual WMS Time: {timestamp.strftime('%H:%M')} UTC)")
        
        # Start with the pre-composed base map
        frame = base_frame.copy()
        
        # 1. Add Precipitation (Historical)
        # Using nexrad-n0q-wmst for time-enabled reflectivity
        radar = fetch_wms_layer_at_time(lat, lon, miles, "nexrad-n0q-wmst", timestamp)
        
        if not radar:
             # Retry with n0r-wmst if n0q fails
             radar = fetch_wms_layer_at_time(lat, lon, miles, "nexrad-n0r-wmst", timestamp)
             
        if radar:
            radar = make_transparent(radar, threshold=4)
            radar = boost_saturation(radar, factor=1.2)
            # Smooth the "noise" and "blocky" look
            radar = radar.filter(ImageFilter.BoxBlur(1))
            # User requested less see-through -> 45% opacity
            radar = adjust_opacity(radar, opacity=0.45)
            frame = Image.alpha_composite(frame, radar)
            
        # 2. Add Warnings (Static/Current)
        if sbw_layer:
            frame = Image.alpha_composite(frame, sbw_layer)
            
        # 3. Add Watches (Static/Current)
        if watches_layer:
            frame = Image.alpha_composite(frame, watches_layer)
        
        # Draw UI
        draw = ImageDraw.Draw(frame)
        
        # --- Top Bar ---
        draw.rectangle([(0, 0), (800, 70)], fill=(0, 0, 0, 180))
        # Add State if available, force Title Case
        loc_title = location.strip().title()
        title_text = f"{loc_title}, {state} - {miles}mi" if state else f"{loc_title} - {miles}mi"
        
        draw.text((10, 10), title_text, fill=(255, 255, 255, 255), font=title_font)
        
        # Time at Top (Adjust to Local)
        local_ts = timestamp + datetime.timedelta(seconds=tz_offset)
        time_label = f"{local_ts.strftime('%Y-%m-%d %H:%M')} {tz_abbrev} (-{i} min)"
        draw.text((10, 45), time_label, fill=(200, 200, 200, 255), font=small_font)
        
        # --- Bottom Bar ---
        draw.rectangle([(0, 730), (800, 800)], fill=(0, 0, 0, 160))
        
        # Layers List (Bottom Left)
        draw.text((10, 775), f"Layers: {', '.join(active_layers)}", fill=(150, 150, 150, 255), font=tiny_font)
        
        # Legends (Center/Right)
        if "Precipitation" in active_layers:
            # Horizontal gradient legend
            leg_start_x = 360
            leg_y = 750
            bar_width = 400
            bar_height = 15
            
            draw.text((leg_start_x, leg_y - 15), "Precipitation (dBZ):", fill=(255, 255, 255, 255), font=tiny_font)
            
            color_stops = [
                (100, 200, 255), (0, 255, 0), (255, 255, 0), 
                (255, 140, 0), (255, 0, 0), (255, 0, 255)
            ]
            labels = ["Light", "Mod", "Heavy", "V.Hv", "Sev", "Ext"]
            
            for x in range(bar_width):
                position = x / bar_width
                segment_index = min(int(position * (len(color_stops) - 1)), len(color_stops) - 2)
                segment_position = (position * (len(color_stops) - 1)) - segment_index
                
                c1 = color_stops[segment_index]
                c2 = color_stops[segment_index + 1]
                
                r = int(c1[0] + (c2[0] - c1[0]) * segment_position)
                g = int(c1[1] + (c2[1] - c1[1]) * segment_position)
                b = int(c1[2] + (c2[2] - c1[2]) * segment_position)
                
                draw.line([(leg_start_x + x, leg_y), (leg_start_x + x, leg_y + bar_height)], fill=(r, g, b, 255))
            
            draw.rectangle([(leg_start_x, leg_y), (leg_start_x + bar_width, leg_y + bar_height)], outline=(200, 200, 200, 255), width=1)
            
            label_spacing = bar_width // len(labels)
            for j, label in enumerate(labels):
                x_pos = leg_start_x + (j * label_spacing) + (label_spacing // 2)
                draw.line([(x_pos, leg_y + bar_height), (x_pos, leg_y + bar_height + 3)], fill=(200, 200, 200, 255), width=1)
                bbox = draw.textbbox((0, 0), label, font=tiny_font)
                text_width = bbox[2] - bbox[0]
                draw.text((x_pos - text_width // 2, leg_y + bar_height + 4), label, fill=(220, 220, 220, 255), font=tiny_font)

        if "Warnings" in active_layers or "Watches" in active_layers:
            legend_x = 680
            draw.text((legend_x, 740), "Alerts:", fill=(255, 255, 255, 255), font=tiny_font)
            if "Warnings" in active_layers:
                draw.rectangle([(legend_x, 755), (legend_x + 20, 770)], fill=(255, 0, 0, 200))
                draw.text((legend_x + 25, 755), "Warning", fill=(255, 100, 100, 255), font=tiny_font)
        
        frames.append(frame)
    
    # Reverse so animation plays forward in time
    frames.reverse()
    
    # Save as animated GIF
    safe_loc = "".join([c for c in location if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
    filename = f"radar_loop_{safe_loc}_{miles}mi_{duration_minutes}min.gif"
    output_path = os.path.join(output_dir, filename)
    
    # Save with PIL
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=500,  # 500ms per frame
        loop=0
    )
    
    print(f"[Radar Animation] Saved: {output_path}")
    return output_path


