"""
Auto clicker engine for executing click scripts
"""
import pyautogui
import time
import threading
from typing import Callable, Optional
from src.click_script import ClickScript, ClickAction, ClickType
from src.image_matcher import ImageMatcher
import os
import win32api
import win32con
import win32gui


class AutoClicker:
    """Engine for recording and executing click scripts"""
    
    def __init__(self, delay_ms: int = 100):
        """
        Initialize auto clicker
        
        Args:
            delay_ms: Delay between clicks in milliseconds
        """
        self.delay_ms = delay_ms
        self.is_running = False
        self.is_paused = False
        self.current_script: Optional[ClickScript] = None
        self.image_matcher = ImageMatcher(confidence=0.8)
        self._execution_thread: Optional[threading.Thread] = None
        self._on_status_changed: Optional[Callable] = None
    
    def set_delay(self, delay_ms: int):
        """Set delay between clicks"""
        self.delay_ms = max(0, delay_ms)
    
    def set_on_status_changed(self, callback: Callable):
        """Set callback for status changes"""
        self._on_status_changed = callback
    
    def _notify_status(self, message: str):
        """Notify status change"""
        if self._on_status_changed:
            self._on_status_changed(message)
    
    def execute_script(self, script: ClickScript):
        """
        Execute a click script in a separate thread
        
        Args:
            script: ClickScript to execute
        """
        if self.is_running:
            return
        
        self.current_script = script
        self.is_running = True
        self._notify_status("Starting auto click...")
        
        self._execution_thread = threading.Thread(target=self._execute_loop, daemon=True)
        self._execution_thread.start()
    
    def _execute_loop(self):
        """Main execution loop"""
        try:
            while self.is_running:
                if not self.is_paused and self.current_script:
                    self._execute_once()
        except Exception as e:
            self._notify_status(f"Error: {e}")
        finally:
            self.is_running = False
            self._notify_status("Auto click stopped")
    
    def _execute_once(self):
        """Execute script once"""
        for i, action in enumerate(self.current_script.get_actions()):
            if not self.is_running:
                break
            
            try:
                if action.type == ClickType.POSITION:
                    self._execute_position_click(action)
                elif action.type == ClickType.IMAGE:
                    self._execute_image_click(action)
                
                # Wait delay between clicks
                if i < len(self.current_script.get_actions()) - 1:
                    time.sleep(self.delay_ms / 1000.0)
            except Exception as e:
                self._notify_status(f"Error executing action {i}: {e}")
    
    def _execute_position_click(self, action: ClickAction):
        """Execute position-based click"""
        x = action.data.get('x', 0)
        y = action.data.get('y', 0)
        target_hwnd = action.data.get('target_hwnd')
        if target_hwnd:
            ok, error = self._validate_target_window(int(target_hwnd))
            if not ok:
                self._stop_due_to_target_error(error)
                return
            client_x, client_y = win32gui.ScreenToClient(int(target_hwnd), (int(x), int(y)))
            self._post_click_client(int(target_hwnd), int(client_x), int(client_y))
            self._notify_status(f"Clicked target hwnd={target_hwnd} at client ({client_x}, {client_y})")
            return
        
        pyautogui.click(int(x), int(y))
        self._notify_status(f"Clicked at ({int(x)}, {int(y)})")
    
    def _execute_image_click(self, action: ClickAction):
        """Execute image-based click"""
        image_path = action.data.get('image_path', '')
        offset_x = action.data.get('offset_x', 0)
        offset_y = action.data.get('offset_y', 0)
        click_x = action.data.get('click_x')
        click_y = action.data.get('click_y')
        click_client_x = action.data.get('click_client_x')
        click_client_y = action.data.get('click_client_y')
        target_hwnd = action.data.get('target_hwnd')
        target_title = action.data.get('target_title', '')
        
        if target_hwnd is not None:
            target_hwnd = int(target_hwnd)
            ok, error = self._validate_target_window(target_hwnd)
            if not ok:
                self._stop_due_to_target_error(error, target_title)
                return
        
        if os.path.exists(image_path):
            if target_hwnd is not None:
                # Keep image as condition, but detect within target window capture.
                match_pos = self.image_matcher.find_image_in_window(image_path, target_hwnd)
            else:
                match_pos = self.image_matcher.find_image(image_path)
            
            if match_pos:
                # Preferred behavior: image is a trigger condition,
                # click at recorded absolute position from PAGE UP.
                if target_hwnd is not None:
                    if click_client_x is not None and click_client_y is not None:
                        cx = int(click_client_x)
                        cy = int(click_client_y)
                        self._post_click_client(target_hwnd, cx, cy)
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> clicked target client ({cx}, {cy})"
                        )
                    elif click_x is not None and click_y is not None:
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(click_x), int(click_y)))
                        self._post_click_client(target_hwnd, int(cx), int(cy))
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> clicked target client ({int(cx)}, {int(cy)})"
                        )
                    else:
                        mx, my = match_pos
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(mx), int(my)))
                        self._post_click_client(target_hwnd, int(cx), int(cy))
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> clicked matched position in target"
                        )
                elif click_x is not None and click_y is not None:
                    pyautogui.click(int(click_x), int(click_y))
                    self._notify_status(
                        f"Image found: {os.path.basename(image_path)} -> clicked recorded position ({int(click_x)}, {int(click_y)})"
                    )
                else:
                    # Backward compatibility for old scripts without click_x/click_y.
                    x, y = match_pos
                    x += offset_x
                    y += offset_y
                    pyautogui.click(x, y)
                    self._notify_status(
                        f"Image found: {os.path.basename(image_path)} -> clicked image position ({x}, {y})"
                    )
            else:
                self._notify_status(f"Image not found: {os.path.basename(image_path)}")
        else:
            self._notify_status(f"Image file not found: {image_path}")
    
    def _validate_target_window(self, hwnd: int):
        """Validate target window state before background click."""
        if not win32gui.IsWindow(hwnd):
            return False, "Target window was closed."
        if win32gui.IsIconic(hwnd):
            return False, "Target window is minimized."
        if not win32gui.IsWindowVisible(hwnd):
            return False, "Target window is hidden."
        return True, ""
    
    def _post_click_client(self, hwnd: int, client_x: int, client_y: int):
        """Post left click messages directly to target window client area."""
        lparam = win32api.MAKELONG(int(client_x), int(client_y))
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    
    def _stop_due_to_target_error(self, error: str, target_title: str = ""):
        """Stop execution when target window is not usable."""
        label = f" [{target_title}]" if target_title else ""
        self.is_running = False
        self._notify_status(f"Stopped: {error}{label}")
    
    def pause(self):
        """Pause execution"""
        self.is_paused = True
        self._notify_status("Paused")
    
    def resume(self):
        """Resume execution"""
        self.is_paused = False
        self._notify_status("Resumed")
    
    def stop(self):
        """Stop execution"""
        self.is_running = False
        if self._execution_thread:
            self._execution_thread.join(timeout=2)
        self._notify_status("Stopped")
