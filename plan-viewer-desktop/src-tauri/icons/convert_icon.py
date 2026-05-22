"""Generate husky cartoon icon using Pillow (no Cairo dependency)."""
from PIL import Image, ImageDraw, ImageFont
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

def draw_husky(size=512):
    """Draw a cartoon husky face icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Scale factor
    s = size / 512.0
    
    # Background circle - blue
    draw.ellipse([int(16*s), int(16*s), int(496*s), int(496*s)], fill=(74, 144, 217, 255))
    
    # Main face shape - light gray
    draw.ellipse([int(96*s), int(110*s), int(416*s), int(450*s)], fill=(232, 232, 232, 255))
    
    # Left ear - dark gray
    draw.polygon([
        (int(130*s), int(180*s)),
        (int(115*s), int(80*s)),
        (int(155*s), int(60*s)),
        (int(195*s), int(120*s)),
        (int(175*s), int(180*s)),
    ], fill=(61, 61, 61, 255))
    
    # Right ear - dark gray
    draw.polygon([
        (int(382*s), int(180*s)),
        (int(397*s), int(80*s)),
        (int(357*s), int(60*s)),
        (int(317*s), int(120*s)),
        (int(337*s), int(180*s)),
    ], fill=(61, 61, 61, 255))
    
    # Inner left ear - pink
    draw.polygon([
        (int(140*s), int(170*s)),
        (int(130*s), int(105*s)),
        (int(160*s), int(80*s)),
        (int(185*s), int(130*s)),
        (int(170*s), int(170*s)),
    ], fill=(255, 182, 193, 255))
    
    # Inner right ear - pink
    draw.polygon([
        (int(372*s), int(170*s)),
        (int(382*s), int(105*s)),
        (int(352*s), int(80*s)),
        (int(327*s), int(130*s)),
        (int(342*s), int(170*s)),
    ], fill=(255, 182, 193, 255))
    
    # Forehead dark patch
    draw.polygon([
        (int(195*s), int(130*s)),
        (int(230*s), int(110*s)),
        (int(256*s), int(100*s)),
        (int(282*s), int(110*s)),
        (int(317*s), int(130*s)),
        (int(300*s), int(210*s)),
        (int(256*s), int(190*s)),
        (int(212*s), int(210*s)),
    ], fill=(74, 74, 74, 255))
    
    # White face mask (diamond/arrow shape)
    draw.polygon([
        (int(256*s), int(130*s)),
        (int(280*s), int(170*s)),
        (int(310*s), int(220*s)),
        (int(310*s), int(300*s)),
        (int(256*s), int(320*s)),
        (int(202*s), int(300*s)),
        (int(202*s), int(220*s)),
        (int(232*s), int(170*s)),
    ], fill=(255, 255, 255, 255))
    
    # Eyes - white background
    draw.ellipse([int(185*s), int(215*s), int(235*s), int(270*s)], fill=(255, 255, 255, 255))
    draw.ellipse([int(277*s), int(215*s), int(327*s), int(270*s)], fill=(255, 255, 255, 255))
    
    # Eyes - blue iris
    draw.ellipse([int(196*s), int(226*s), int(228*s), int(260*s)], fill=(33, 150, 243, 255))
    draw.ellipse([int(284*s), int(226*s), int(316*s), int(260*s)], fill=(33, 150, 243, 255))
    
    # Eyes - pupil
    draw.ellipse([int(205*s), int(235*s), int(219*s), int(251*s)], fill=(26, 26, 26, 255))
    draw.ellipse([int(293*s), int(235*s), int(307*s), int(251*s)], fill=(26, 26, 26, 255))
    
    # Eyes - highlight
    draw.ellipse([int(210*s), int(230*s), int(218*s), int(238*s)], fill=(255, 255, 255, 255))
    draw.ellipse([int(298*s), int(230*s), int(306*s), int(238*s)], fill=(255, 255, 255, 255))
    
    # Nose
    draw.ellipse([int(236*s), int(295*s), int(276*s), int(325*s)], fill=(45, 45, 45, 255))
    # Nose highlight
    draw.ellipse([int(249*s), int(298*s), int(263*s), int(308*s)], fill=(100, 100, 100, 255))
    
    # Mouth lines
    draw.arc([int(230*s), int(315*s), int(256*s), int(345*s)], 0, 180, fill=(61, 61, 61, 255), width=int(3*s))
    draw.arc([int(256*s), int(315*s), int(282*s), int(345*s)], 0, 180, fill=(61, 61, 61, 255), width=int(3*s))
    
    # Tongue
    draw.ellipse([int(244*s), int(338*s), int(268*s), int(375*s)], fill=(255, 107, 138, 255))
    draw.line([(int(256*s), int(340*s)), (int(256*s), int(370*s))], fill=(232, 85, 119, 255), width=int(2*s))
    
    return img


# Generate main icon
print("Generating husky icon...")
icon_512 = draw_husky(512)
icon_512.save(os.path.join(script_dir, "icon.png"))
print("Created icon.png (512x512)")

# Generate ICO with multiple sizes
sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
ico_images = []
for size in sizes:
    resized = draw_husky(size[0])
    ico_images.append(resized)

ico_images[0].save(
    os.path.join(script_dir, "icon.ico"),
    format="ICO",
    sizes=sizes,
    append_images=ico_images[1:]
)
print("Created icon.ico (16x16, 32x32, 48x48, 256x256)")

# Small icon for TitleBar
icon_24 = draw_husky(24)
icon_24.save(os.path.join(script_dir, "icon-small.png"))
print("Created icon-small.png (24x24)")

print("\nDone! All icon files generated successfully.")
