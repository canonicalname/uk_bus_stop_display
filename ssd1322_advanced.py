#!/usr/bin/env python3
"""
SSD1322 OLED Display - Advanced Example
Shows multiple text styles, shapes, and animations
"""

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import ssd1322
from PIL import ImageFont, ImageDraw
import time

def main():
    # Initialize SPI connection
    serial = spi(device=0, port=0)
    
    # Initialize the SSD1322 device (256x64 resolution)
    device = ssd1322(serial)
    
    print(f"Display initialized: {device.width}x{device.height}")
    
    # Example 1: Simple text
    print("Displaying: Hello World")
    with canvas(device) as draw:
        draw.text((10, 20), "Hello World!", fill="white")
    time.sleep(2)
    
    # Example 2: Multiple lines
    print("Displaying: Multiple lines")
    with canvas(device) as draw:
        draw.text((10, 5), "Line 1: Hello", fill="white")
        draw.text((10, 20), "Line 2: Raspberry Pi", fill="white")
        draw.text((10, 35), "Line 3: SSD1322 OLED", fill="white")
    time.sleep(2)
    
    # Example 3: Shapes
    print("Displaying: Shapes")
    with canvas(device) as draw:
        draw.rectangle((10, 10, 50, 50), outline="white", fill="black")
        draw.ellipse((60, 10, 100, 50), outline="white", fill="black")
        draw.line((110, 10, 150, 50), fill="white", width=2)
    time.sleep(2)
    
    # Example 4: Centered text
    print("Displaying: Centered text")
    with canvas(device) as draw:
        text = "Centered!"
        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (device.width - text_width) // 2
        y = (device.height - text_height) // 2
        draw.text((x, y), text, fill="white")
    time.sleep(2)
    
    # Example 5: Progress bar
    print("Displaying: Progress bar")
    for i in range(0, 101, 5):
        with canvas(device) as draw:
            draw.text((10, 10), f"Loading: {i}%", fill="white")
            # Draw progress bar
            bar_width = int((device.width - 20) * i / 100)
            draw.rectangle((10, 35, 10 + bar_width, 45), outline="white", fill="white")
            draw.rectangle((10, 35, device.width - 10, 45), outline="white")
        time.sleep(0.1)
    
    time.sleep(1)
    
    # Clear display
    print("Clearing display")
    device.clear()

if __name__ == "__main__":
    main()
