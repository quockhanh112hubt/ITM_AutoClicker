"""
Image matching and clicking functionality
"""
import cv2
import numpy as np
from PIL import ImageGrab
from typing import Optional, Tuple
import pyautogui
import ctypes
import os
import win32gui
import win32ui
import win32con
from src.logger import AppLogger
from src.constants import UNIFORM_COLOR_THRESHOLD, MIN_REGION_SIZE, IMAGE_CONFIDENCE_MIN, IMAGE_CONFIDENCE_MAX


class ImageMatcher:
    """Handle image template matching and clicking"""
    
    def __init__(self, confidence: float = 0.8) -> None:
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
            
        Raises:
            ValueError: If template_path is None or empty
            FileNotFoundError: If template file doesn't exist
        """
        if not template_path:
            raise ValueError("template_path cannot be None or empty")
        if not isinstance(template_path, str):
            raise ValueError(f"template_path must be a string, got {type(template_path).__name__}")
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
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
            AppLogger.error(f"Error finding image: {e}")
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
            AppLogger.error(f"Error capturing window: {e}")
            return None
    
    def find_image_in_window(self, template_path: str, hwnd: int) -> Optional[Tuple[int, int]]:
        """
        Find image inside a specific window.
        
        Args:
            template_path: Path to template image
            hwnd: Window handle
        
        Returns:
            Screen coordinates (x, y) of matched center if found.
            
        Raises:
            ValueError: If template_path is None or hwnd is invalid
            FileNotFoundError: If template file doesn't exist
        """
        if not template_path:
            raise ValueError("template_path cannot be None or empty")
        if not isinstance(template_path, str):
            raise ValueError(f"template_path must be a string, got {type(template_path).__name__}")
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")
        if not isinstance(hwnd, int):
            raise ValueError(f"hwnd must be an integer, got {type(hwnd).__name__}")
        if hwnd <= 0:
            raise ValueError(f"hwnd must be positive, got {hwnd}")
        
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
            AppLogger.error(f"Error finding image in window: {e}")
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
    def capture_region(x1: int, y1: int, x2: int, y2: int, save_path: str) -> bool:
        """
        Capture a rectangular region of the screen
        
        Args:
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
            save_path: Path to save the captured image
            
        Returns:
            True if capture successful, False otherwise
        """
        try:
            # Normalize coordinates
            left = min(x1, x2)
            top = min(y1, y2)
            right = max(x1, x2)
            bottom = max(y1, y2)
            
            # Clamp to valid screen coordinates (handle negative coords from DPI scaling)
            left = max(0, left)
            top = max(0, top)
            right = max(0, right)
            bottom = max(0, bottom)
            
            width = right - left
            height = bottom - top
            
            # Validate size
            if width <= MIN_REGION_SIZE or height <= MIN_REGION_SIZE:
                AppLogger.error(f"Invalid region size: {width}x{height}")
                return False
            
            # Capture region
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # Validate captured image is not all uniform (likely error)
            arr = np.array(screenshot)
            if np.std(arr) < UNIFORM_COLOR_THRESHOLD:  # Too uniform = likely error
                AppLogger.warning(f"Captured image looks invalid (uniform color)")
            
            # Ensure save directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            screenshot.save(save_path)
            AppLogger.info(f"Saved image to: {save_path} (size: {screenshot.size})")
            return True
            
        except Exception as e:
            AppLogger.error(f"Capture failed: {e}")
            return False
