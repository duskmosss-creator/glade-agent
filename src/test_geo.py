from weather_radar import get_lat_lon
lat, lon, state = get_lat_lon("Cincinnati")
print(f"Lat: {lat}, Lon: {lon}, State: {state}")
