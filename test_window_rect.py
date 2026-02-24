#!/usr/bin/env python3
"""Test window rect capturing"""

import sys
import win32gui
from PIL import ImageGrab

print("=" * 70)
print("TEST: Window Rect Analysis")
print("=" * 70)
print()

# Enumerate all visible windows
windows = []

def enum_callback(hwnd, result):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        if title:  # Only visible windows with titles
            windows.append((hwnd, title, class_name))

win32gui.EnumWindows(enum_callback, None)

print(f"Found {len(windows)} visible windows\n")

# Test first few windows
for i, (hwnd, title, cls) in enumerate(windows[:5]):
    print(f"[{i}] {title}")
    print(f"    Class: {cls}")
    
    rect = win32gui.GetWindowRect(hwnd)
    print(f"    Rect: {rect}")
    print(f"    Width x Height: {rect[2]-rect[0]} x {rect[3]-rect[1]}")
    
    # Try to capture window
    try:
        x1, y1, x2, y2 = rect
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        print(f"    Captured size: {img.size}")
        filename = f"test_window_{i}.png"
        img.save(filename)
        print(f"    Saved: {filename}")
    except Exception as e:
        print(f"    Error: {e}")
    
    print()

print("=" * 70)
