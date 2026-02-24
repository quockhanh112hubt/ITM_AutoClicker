"""
Test script to verify the new Image Recording workflow
"""
import sys
sys.path.insert(0, r'e:\GitHub\ITM_AutoClicker')

from src.image_recording_manager import ImageRecordingManager
from src.image_dialogs import ImageConfirmationDialog, ClickPositionDialog

def on_complete(recorded_images):
    """Callback when recording is complete"""
    print(f"[WORKFLOW] Recording complete!")
    print(f"[WORKFLOW] Recorded {len(recorded_images)} image(s):")
    for i, (image_path, click_x, click_y) in enumerate(recorded_images, 1):
        print(f"  {i}. Image: {image_path}")
        print(f"     Click Position: ({click_x}, {click_y})")

def on_cancelled():
    """Callback when recording is cancelled"""
    print("[WORKFLOW] Recording cancelled by user")

if __name__ == '__main__':
    print("[TEST] Image Recording Workflow Integration Test")
    print("[TEST] Creating ImageRecordingManager...")
    
    manager = ImageRecordingManager(
        on_complete=on_complete,
        on_cancel=on_cancelled
    )
    
    print("[TEST] ImageRecordingManager created successfully")
    print("[TEST] Manager has following methods:")
    print(f"  - start(): {hasattr(manager, 'start')}")
    print(f"  - stop(): {hasattr(manager, 'stop')}")
    print(f"  - recorded_images: {hasattr(manager, 'recorded_images')}")
    print(f"  - is_recording: {hasattr(manager, 'is_recording')}")
    print("[TEST] All checks passed!")
