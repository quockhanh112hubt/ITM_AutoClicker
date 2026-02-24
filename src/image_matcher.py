"""
Image matching and clicking functionality
"""
import cv2
import numpy as np
from PIL import ImageGrab
from typing import Optional, Tuple
import pyautogui
import ctypes
import win32gui
import win32ui
import win32con


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
    
    def _capture_window_image(self, hwnd: int) -> Optional[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
        """
        Capture full window image using PrintWindow.
        
        Returns:
            (image_bgr, window_rect) or None
        """
        try:
            if not win32gui.IsWindow(hwnd):
                return None
            
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return None
            
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            mem_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            mem_dc.SelectObject(bitmap)
            
            # PW_RENDERFULLCONTENT (0x00000002) improves capture for some apps.
            result = ctypes.windll.user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 0x00000002)
            
            bmp_info = bitmap.GetInfo()
            bmp_bytes = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmp_bytes, dtype=np.uint8)
            img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))
            image_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Cleanup GDI resources.
            win32gui.DeleteObject(bitmap.GetHandle())
            mem_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            
            if result != 1:
                return None
            
            return image_bgr, (left, top, right, bottom)
        except Exception as e:
            print(f"Error capturing window: {e}")
            return None
    
    def find_image_in_window(self, template_path: str, hwnd: int) -> Optional[Tuple[int, int]]:
        """
        Find image inside a specific window.
        
        Returns:
            Screen coordinates (x, y) of matched center if found.
        """
        try:
            captured = self._capture_window_image(hwnd)
            if captured is None:
                return None
            
            window_image, (left, top, _, _) = captured
            
            template = cv2.imread(template_path)
            if template is None:
                return None
            
            th, tw = template.shape[:2]
            result = cv2.matchTemplate(window_image, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= self.confidence:
                center_x = left + max_loc[0] + tw // 2
                center_y = top + max_loc[1] + th // 2
                return (center_x, center_y)
            
            return None
        except Exception as e:
            print(f"Error finding image in window: {e}")
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
