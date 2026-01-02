#!/usr/bin/env python3
"""Generate PWA icons for Song Trainer"""

import os

# Try to use PIL/Pillow if available, otherwise create placeholder icons
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ICONS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'icons')
SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

def create_icon(size):
    """Create a simple icon with gradient background and music note"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle background with gradient-like effect
    # Using a simple purple color instead of gradient for simplicity
    corner_radius = size // 5
    
    # Draw filled rounded rectangle
    draw.rounded_rectangle(
        [(0, 0), (size-1, size-1)],
        radius=corner_radius,
        fill=(108, 99, 255)  # Primary purple color
    )
    
    # Draw music note emoji as text (if font supports it)
    try:
        # Try to use a large font
        font_size = size // 2
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("seguiemj.ttf", font_size)  # Windows emoji font
            except:
                font = ImageFont.load_default()
        
        text = "🎵"
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        
        draw.text((x, y), text, font=font, fill='white')
    except Exception as e:
        # Fallback: draw a simple music note shape
        note_color = 'white'
        center_x = size // 2
        center_y = size // 2
        note_size = size // 3
        
        # Draw a simple note head (oval)
        draw.ellipse([
            center_x - note_size//2, center_y,
            center_x + note_size//2, center_y + note_size//2
        ], fill=note_color)
        
        # Draw stem
        stem_width = max(2, size // 20)
        draw.rectangle([
            center_x + note_size//2 - stem_width, center_y - note_size//2,
            center_x + note_size//2, center_y + note_size//4
        ], fill=note_color)
    
    return img

def create_simple_icon(size):
    """Create a very simple icon without emoji support"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    corner_radius = size // 5
    
    # Draw rounded rectangle background
    draw.rounded_rectangle(
        [(0, 0), (size-1, size-1)],
        radius=corner_radius,
        fill=(108, 99, 255)
    )
    
    # Draw "ST" text as fallback
    try:
        font_size = size // 3
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "ST"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        draw.text((x, y), text, font=font, fill='white')
    except:
        pass
    
    return img

def main():
    os.makedirs(ICONS_DIR, exist_ok=True)
    
    if not HAS_PIL:
        print("Pillow not installed. Please run: pip install Pillow")
        print("Then run this script again to generate icons.")
        return
    
    for size in SIZES:
        try:
            img = create_simple_icon(size)
            filepath = os.path.join(ICONS_DIR, f'icon-{size}x{size}.png')
            img.save(filepath, 'PNG')
            print(f"Created {filepath}")
        except Exception as e:
            print(f"Error creating {size}x{size} icon: {e}")
    
    print("\nDone! Icons created in", ICONS_DIR)

if __name__ == '__main__':
    main()
