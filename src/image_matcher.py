"""
Image matching and clicking functionality
"""
import cv2
import numpy as np
from PIL import ImageGrab
from typing import Optional, Tuple
import pyautogui


class ImageMatcher:
    """Handle image template matching and clicking"""
    
    def __init__(self, confidence: float = 0.8):
        """
        Initialize image matcher
        
        Args:
            confidence: Confidence threshold for template matching (0-1)
        """
        self.confidence = confidence
    
    def find_image(self, template_path: str) -> Optional[Tuple[int, int]]:
        """
        Find image on screen
        
        Args:
            template_path: Path to template image
            
        Returns:
            Tuple of (x, y) if found, None otherwise
        """
        try:
            # Take screenshot
            screenshot = ImageGrab.grab()
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Load template
            template = cv2.imread(template_path)
            if template is None:
                return None
            
            # Get dimensions
            h, w = template.shape[:2]
            
            # Template matching
            result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # Check if confidence threshold is met
            if max_val >= self.confidence:
                # Return center of matched region
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y)
            
            return None
        except Exception as e:
            print(f"Error finding image: {e}")
            return None
    
    def click_on_image(self, template_path: str, click_offset: Tuple[int, int] = (0, 0)) -> bool:
        """
        Find and click on image
        
        Args:
            template_path: Path to template image
            click_offset: Offset from center (dx, dy)
            
        Returns:
            True if clicked successfully, False otherwise
        """
        pos = self.find_image(template_path)
        if pos:
            x, y = pos
            x += click_offset[0]
            y += click_offset[1]
            pyautogui.click(x, y)
            return True
        return False
    
    @staticmethod
    def capture_region(x1: int, y1: int, x2: int, y2: int, save_path: str):
        """
        Capture a rectangular region of the screen
        
        Args:
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            save_path: Path to save the captured image
        """
        # Normalize coordinates
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        
        print(f"[DEBUG ImageMatcher] Received: ({x1}, {y1}, {x2}, {y2})")
        print(f"[DEBUG ImageMatcher] Normalized: ({left}, {top}, {right}, {bottom})")
        
        # Clamp to valid screen coordinates (in case of negative coords from DPI scaling)
        left = max(0, left)
        top = max(0, top)
        right = max(0, right)
        bottom = max(0, bottom)
        
        print(f"[DEBUG ImageMatcher] Clamped: ({left}, {top}, {right}, {bottom})")
        
        width = right - left
        height = bottom - top
        print(f"[DEBUG ImageMatcher] Size: {width}x{height}")
        
        # Check if size is valid
        if width <= 0 or height <= 0:
            print(f"[ERROR] Invalid region size: {width}x{height}")
            return
        
        # Capture region
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        print(f"[DEBUG ImageMatcher] Captured image size: {screenshot.size}")
        
        screenshot.save(save_path)
        print(f"[DEBUG ImageMatcher] Saved to: {save_path}")
