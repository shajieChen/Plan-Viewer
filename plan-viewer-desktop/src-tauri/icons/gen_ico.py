"""Regenerate icon.ico with proper multi-size embedding."""
from PIL import Image
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
img = Image.open(os.path.join(script_dir, "icon.png"))

# Save ICO with multiple sizes embedded
img.save(
    os.path.join(script_dir, "icon.ico"),
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (256, 256)]
)

size = os.path.getsize(os.path.join(script_dir, "icon.ico"))
print(f"icon.ico regenerated: {size} bytes")
