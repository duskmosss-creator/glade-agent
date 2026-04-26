import os
import shutil
from weather_radar import generate_radar_images, generate_radar_animation

# Create documentation directory if it doesn't exist
doc_dir = "doc_assets"
os.makedirs(doc_dir, exist_ok=True)

print("--- Generating Documentation Assets ---")

# 1. Static Radar (PNG)
print("Generating static radar example...")
static_paths = generate_radar_images('Seattle, WA', 30)
if static_paths:
    shutil.copy(static_paths[-1], os.path.join(doc_dir, "radar_static.png"))
    print(f"Saved: {os.path.join(doc_dir, 'radar_static.png')}")

# 2. Animated Radar (30m GIF)
print("Generating 30m animation example...")
gif_30 = generate_radar_animation('Seattle, WA', 30, duration_minutes=30)
if gif_30:
    shutil.copy(gif_30, os.path.join(doc_dir, "radar_30m.gif"))
    print(f"Saved: {os.path.join(doc_dir, 'radar_30m.gif')}")

# 3. Animated Radar (60m GIF)
print("Generating 60m animation example...")
gif_60 = generate_radar_animation('Seattle, WA', 30, duration_minutes=60)
if gif_60:
    shutil.copy(gif_60, os.path.join(doc_dir, "radar_60m.gif"))
    print(f"Saved: {os.path.join(doc_dir, 'radar_60m.gif')}")

print("\n--- Done ---")
