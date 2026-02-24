#!/usr/bin/env python3
"""Test image capture with proper coordinates"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PIL import ImageGrab
import time

print("=" * 70)
print("TEST: Manual Region Capture")
print("=" * 70)
print()

# Test capture different regions
test_regions = [
    ((0, 0, 100, 100), "top_left_100x100"),
    ((100, 100, 300, 300), "middle_200x200"),
    ((500, 300, 800, 600), "large_300x300"),
]

os.makedirs("test_captures", exist_ok=True)

for (x1, y1, x2, y2), name in test_regions:
    try:
        width = x2 - x1
        height = y2 - y1
        print(f"[TEST] Capturing ({x1}, {y1}) to ({x2}, {y2}) - {width}x{height}")
        
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        filepath = f"test_captures/{name}.png"
        img.save(filepath)
        
        print(f"    [OK] Saved {filepath} - Size: {img.size}")
        print()
        
    except Exception as e:
        print(f"    [ERROR] {e}")
        print()

print("=" * 70)
print("TEST COMPLETE - Check test_captures/ folder")
print("=" * 70)
