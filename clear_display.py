#!/usr/bin/env python3
"""
Clear the OLED display
Used when stopping the service
"""

from luma.core.interface.serial import spi
from luma.oled.device import ssd1322

try:
    serial = spi(device=0, port=0)
    device = ssd1322(serial, width=256, height=64)
    device.clear()
    print("Display cleared")
except Exception as e:
    print(f"Error clearing display: {e}")
