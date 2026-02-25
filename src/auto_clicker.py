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
    
    def __init__(self, delay_ms: int = 100, priority_cooldown_ms: int = 800):
        """
        Initialize auto clicker
        
        Args:
            delay_ms: Delay between clicks in milliseconds
            priority_cooldown_ms: Cooldown for priority image actions in milliseconds
        """
        self.delay_ms = delay_ms
        self.priority_cooldown_ms = max(0, priority_cooldown_ms)
        self.is_running = False
        self.is_paused = False
        self.current_script: Optional[ClickScript] = None
        self.image_matcher = ImageMatcher(confidence=0.8)
        self._execution_thread: Optional[threading.Thread] = None
        self._on_status_changed: Optional[Callable] = None
        self._on_action_executed: Optional[Callable] = None
        self._priority_last_trigger_at = {}
    
    def set_delay(self, delay_ms: int):
        """Set delay between clicks"""
        self.delay_ms = max(0, delay_ms)
    
    def set_priority_cooldown(self, cooldown_ms: int):
        """Set cooldown for priority actions"""
        self.priority_cooldown_ms = max(0, cooldown_ms)
    
    def set_on_status_changed(self, callback: Callable):
        """Set callback for status changes"""
        self._on_status_changed = callback
    
    def set_on_action_executed(self, callback: Callable):
        """Set callback(action_index) when an action is actually executed."""
        self._on_action_executed = callback
    
    def _notify_status(self, message: str):
        """Notify status change"""
        if self._on_status_changed:
            self._on_status_changed(message)
    
    def _notify_action_executed(self, action_index: int):
        """Notify when an action is executed."""
        if self._on_action_executed:
            self._on_action_executed(int(action_index))
    
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
        self._priority_last_trigger_at.clear()
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
        for action_index, action in enumerate(self.current_script.get_actions()):
            if not self.is_running:
                break
            
            try:
                executed = False
                if action.type == ClickType.POSITION:
                    executed = self._execute_position_click(action)
                elif action.type == ClickType.IMAGE:
                    executed = self._execute_image_click(action)
                elif action.type == ClickType.IMAGE_DIRECT:
                    executed = self._execute_image_direct_click(action)
                
                if executed:
                    self._notify_action_executed(action_index)
                
                if not self.is_running:
                    break
                
                # Always wait delay after each action, including the last action in a cycle.
                # This keeps timing consistent between ...->last and last->first.
                time.sleep(self._get_action_delay_ms(action) / 1000.0)
                self._execute_priority_actions()
            except Exception as e:
                self._notify_status(f"Error executing action: {e}")
    
    def _execute_priority_actions(self):
        """Execute currently-triggered priority image actions in ascending priority order."""
        if not self.current_script or not self.is_running:
            return
        
        candidates = []
        for idx, action in enumerate(self.current_script.get_actions()):
            if action.type not in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
                continue
            level = int(action.data.get('priority_level', 0) or 0)
            if level > 0:
                candidates.append((level, idx, action))
        
        if not candidates:
            return
        
        candidates.sort(key=lambda item: (item[0], item[1]))
        cooldown_sec = self.priority_cooldown_ms / 1000.0
        clicked_count = 0
        
        for level, idx, action in candidates:
            if not self.is_running:
                break
            
            now = time.time()
            last = self._priority_last_trigger_at.get(idx, 0.0)
            if cooldown_sec > 0 and (now - last) < cooldown_sec:
                continue
            
            if self._is_image_action_triggered(action):
                if action.type == ClickType.IMAGE_DIRECT:
                    executed = self._execute_image_direct_click(action)
                else:
                    executed = self._execute_image_click(action)
                if executed:
                    self._notify_action_executed(idx)
                    self._priority_last_trigger_at[idx] = time.time()
                    clicked_count += 1
                    time.sleep(self._get_action_delay_ms(action) / 1000.0)
        
        if clicked_count > 0:
            self._notify_status(f"Priority handled: {clicked_count} action(s). Resume normal sequence.")
    
    def _get_action_delay_ms(self, action: ClickAction) -> int:
        """Return per-action delay in ms, fallback to global delay."""
        try:
            value = int(action.data.get('delay_ms', self.delay_ms))
        except Exception:
            value = int(self.delay_ms)
        return max(0, value)
    
    def _is_image_action_triggered(self, action: ClickAction) -> bool:
        """Check whether image condition for an image action is currently met."""
        image_path = action.data.get('image_path', '')
        target_hwnd = action.data.get('target_hwnd')
        target_title = action.data.get('target_title', '')
        
        if not os.path.exists(image_path):
            return False
        
        if target_hwnd is not None:
            target_hwnd = int(target_hwnd)
            ok, error = self._validate_target_window(target_hwnd)
            if not ok:
                self._stop_due_to_target_error(error, target_title)
                return False
            return self.image_matcher.find_image_in_window(image_path, target_hwnd) is not None
        
        return self.image_matcher.find_image(image_path) is not None
    
    def _execute_position_click(self, action: ClickAction):
        """Execute position-based click"""
        x = action.data.get('x', 0)
        y = action.data.get('y', 0)
        action_mode = str(action.data.get('action_mode', 'mouse_click')).lower()
        mouse_button = str(action.data.get('mouse_button', 'left')).lower()
        hold_ms = int(action.data.get('hold_ms', 1000) or 1000)
        client_x = action.data.get('client_x')
        client_y = action.data.get('client_y')
        target_hwnd = action.data.get('target_hwnd')

        if action_mode in ("key_press", "hotkey", "key_hold", "key_hold_true"):
            return self._execute_key_action(action, int(target_hwnd) if target_hwnd else None)

        if target_hwnd:
            ok, error = self._validate_target_window(int(target_hwnd))
            if not ok:
                self._stop_due_to_target_error(error)
                return False
            if client_x is None or client_y is None:
                client_x, client_y = win32gui.ScreenToClient(int(target_hwnd), (int(x), int(y)))
            self._post_click_client(int(target_hwnd), int(client_x), int(client_y), mouse_button, action_mode, hold_ms)
            self._notify_status(
                f"Executed {action_mode} on target hwnd={target_hwnd} at client ({int(client_x)}, {int(client_y)})"
            )
            return True
        
        self._perform_foreground_mouse_action(int(x), int(y), mouse_button, action_mode, hold_ms)
        self._notify_status(f"Executed {action_mode} at ({int(x)}, {int(y)})")
        return True
    
    def _execute_image_click(self, action: ClickAction):
        """Execute image-based click"""
        image_path = action.data.get('image_path', '')
        offset_x = action.data.get('offset_x', 0)
        offset_y = action.data.get('offset_y', 0)
        action_mode = str(action.data.get('action_mode', 'mouse_click')).lower()
        click_x = action.data.get('click_x')
        click_y = action.data.get('click_y')
        mouse_button = str(action.data.get('mouse_button', 'left')).lower()
        hold_ms = int(action.data.get('hold_ms', 1000) or 1000)
        click_client_x = action.data.get('click_client_x')
        click_client_y = action.data.get('click_client_y')
        target_hwnd = action.data.get('target_hwnd')
        target_title = action.data.get('target_title', '')
        
        if target_hwnd is not None:
            target_hwnd = int(target_hwnd)
            ok, error = self._validate_target_window(target_hwnd)
            if not ok:
                self._stop_due_to_target_error(error, target_title)
                return False
        
        if os.path.exists(image_path):
            if target_hwnd is not None:
                # Keep image as condition, but detect within target window capture.
                match_pos = self.image_matcher.find_image_in_window(image_path, target_hwnd)
            else:
                match_pos = self.image_matcher.find_image(image_path)
            
            if match_pos:
                # Preferred behavior: image is a trigger condition,
                # click at recorded absolute position from PAGE UP.
                if action_mode in ("key_press", "hotkey", "key_hold", "key_hold_true"):
                    return self._execute_key_action(action, target_hwnd)

                if target_hwnd is not None:
                    if click_client_x is not None and click_client_y is not None:
                        cx = int(click_client_x)
                        cy = int(click_client_y)
                        self._post_click_client(target_hwnd, cx, cy, mouse_button, action_mode, hold_ms)
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> {action_mode} at ({cx}, {cy})"
                        )
                        return True
                    elif click_x is not None and click_y is not None:
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(click_x), int(click_y)))
                        self._post_click_client(target_hwnd, int(cx), int(cy), mouse_button, action_mode, hold_ms)
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> {action_mode} at ({int(cx)}, {int(cy)})"
                        )
                        return True
                    else:
                        mx, my = match_pos
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(mx), int(my)))
                        self._post_click_client(target_hwnd, int(cx), int(cy), mouse_button, action_mode, hold_ms)
                        self._notify_status(
                            f"Image found in target: {os.path.basename(image_path)} -> {action_mode} at matched position"
                        )
                        return True
                elif click_x is not None and click_y is not None:
                    self._perform_foreground_mouse_action(int(click_x), int(click_y), mouse_button, action_mode, hold_ms)
                    self._notify_status(
                        f"Image found: {os.path.basename(image_path)} -> {action_mode} at ({int(click_x)}, {int(click_y)})"
                    )
                    return True
                else:
                    # Backward compatibility for old scripts without click_x/click_y.
                    x, y = match_pos
                    x += offset_x
                    y += offset_y
                    self._perform_foreground_mouse_action(x, y, mouse_button, action_mode, hold_ms)
                    self._notify_status(
                        f"Image found: {os.path.basename(image_path)} -> {action_mode} at image position ({x}, {y})"
                    )
                    return True
            else:
                self._notify_status(f"Image not found: {os.path.basename(image_path)}")
                return False
        else:
            self._notify_status(f"Image file not found: {image_path}")
            return False
    
    def _execute_image_direct_click(self, action: ClickAction):
        """Execute direct-image click: click matched image center when detected."""
        image_path = action.data.get('image_path', '')
        action_mode = str(action.data.get('action_mode', 'mouse_click')).lower()
        mouse_button = str(action.data.get('mouse_button', 'left')).lower()
        hold_ms = int(action.data.get('hold_ms', 1000) or 1000)
        target_hwnd = action.data.get('target_hwnd')
        target_title = action.data.get('target_title', '')
        
        if target_hwnd is not None:
            target_hwnd = int(target_hwnd)
            ok, error = self._validate_target_window(target_hwnd)
            if not ok:
                self._stop_due_to_target_error(error, target_title)
                return False
        
        if not os.path.exists(image_path):
            self._notify_status(f"Image file not found: {image_path}")
            return False
        
        if target_hwnd is not None:
            match_pos = self.image_matcher.find_image_in_window(image_path, target_hwnd)
        else:
            match_pos = self.image_matcher.find_image(image_path)
        
        if not match_pos:
            self._notify_status(f"Image not found: {os.path.basename(image_path)}")
            return False
        
        if action_mode in ("key_press", "hotkey", "key_hold", "key_hold_true"):
            return self._execute_key_action(action, target_hwnd)
        
        mx, my = int(match_pos[0]), int(match_pos[1])
        if target_hwnd is not None:
            cx, cy = win32gui.ScreenToClient(target_hwnd, (mx, my))
            self._post_click_client(target_hwnd, int(cx), int(cy), mouse_button, action_mode, hold_ms)
            self._notify_status(
                f"Image direct {action_mode}: {os.path.basename(image_path)} -> target client ({int(cx)}, {int(cy)})"
            )
            return True
        else:
            self._perform_foreground_mouse_action(mx, my, mouse_button, action_mode, hold_ms)
            self._notify_status(
                f"Image direct {action_mode}: {os.path.basename(image_path)} -> screen ({mx}, {my})"
            )
            return True
    
    def _validate_target_window(self, hwnd: int):
        """Validate target window state before background click."""
        if not win32gui.IsWindow(hwnd):
            return False, "Target window was closed."
        if win32gui.IsIconic(hwnd):
            return False, "Target window is minimized."
        if not win32gui.IsWindowVisible(hwnd):
            return False, "Target window is hidden."
        return True, ""
    
    def _post_click_client(
        self,
        hwnd: int,
        client_x: int,
        client_y: int,
        mouse_button: str = "left",
        action_mode: str = "mouse_click",
        hold_ms: int = 1000
    ):
        """Post mouse action messages to the most relevant child window at point."""
        screen_x, screen_y = win32gui.ClientToScreen(hwnd, (int(client_x), int(client_y)))
        click_hwnd, lx, ly = self._resolve_click_target(hwnd, int(client_x), int(client_y))
        lparam = win32api.MAKELONG(int(lx), int(ly))
        win32gui.PostMessage(click_hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
        button = str(mouse_button).lower()
        mode = str(action_mode).lower()

        if button == "right":
            win32gui.PostMessage(click_hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
            if mode == "mouse_hold":
                time.sleep(max(0, int(hold_ms)) / 1000.0)
            win32gui.PostMessage(click_hwnd, win32con.WM_RBUTTONUP, 0, lparam)
            # Some apps only react to right-click when WM_CONTEXTMENU is posted.
            context_lparam = win32api.MAKELONG(int(screen_x), int(screen_y))
            win32gui.PostMessage(click_hwnd, win32con.WM_CONTEXTMENU, click_hwnd, context_lparam)
            if click_hwnd != hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CONTEXTMENU, click_hwnd, context_lparam)
        elif button == "middle":
            win32gui.PostMessage(click_hwnd, win32con.WM_MBUTTONDOWN, win32con.MK_MBUTTON, lparam)
            if mode == "mouse_hold":
                time.sleep(max(0, int(hold_ms)) / 1000.0)
            win32gui.PostMessage(click_hwnd, win32con.WM_MBUTTONUP, 0, lparam)
        else:
            win32gui.PostMessage(click_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            if mode == "mouse_hold":
                time.sleep(max(0, int(hold_ms)) / 1000.0)
            win32gui.PostMessage(click_hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    
    def _perform_foreground_mouse_action(self, x: int, y: int, mouse_button: str, action_mode: str, hold_ms: int):
        """Perform mouse action using pyautogui on foreground."""
        button = 'left'
        if str(mouse_button).lower() == 'right':
            button = 'right'
        elif str(mouse_button).lower() == 'middle':
            button = 'middle'

        if str(action_mode).lower() == "mouse_hold":
            pyautogui.mouseDown(int(x), int(y), button=button)
            time.sleep(max(0, int(hold_ms)) / 1000.0)
            pyautogui.mouseUp(int(x), int(y), button=button)
        else:
            pyautogui.click(int(x), int(y), button=button)

    def _execute_key_action(self, action: ClickAction, target_hwnd: Optional[int] = None):
        """Execute keyboard action types: key_press, hotkey, key_hold."""
        mode = str(action.data.get('action_mode', '')).lower()
        key_name = str(action.data.get('key_name', '')).lower()
        hotkey_keys = action.data.get('hotkey_keys') or []
        hold_ms = int(action.data.get('hold_ms', 1000) or 1000)
        
        # Keyboard actions are generally focus-based. Bring target to foreground first.
        if target_hwnd:
            try:
                win32gui.SetForegroundWindow(int(target_hwnd))
                time.sleep(0.05)
            except Exception:
                pass
        
        if mode == "key_press" and key_name:
            pyautogui.press(key_name)
            self._notify_status(f"Key press: {key_name}")
            return True
        elif mode == "key_hold" and key_name:
            # Many applications (e.g. Excel) do not auto-repeat reliably with synthetic keyDown.
            # Emulate hold by repeatedly pressing key during hold duration.
            duration = max(0, hold_ms) / 1000.0
            if duration <= 0:
                pyautogui.press(key_name)
            else:
                repeat_interval = 0.06  # ~16 presses/sec feels like normal key repeat
                end_at = time.time() + duration
                while time.time() < end_at and self.is_running:
                    pyautogui.press(key_name)
                    time.sleep(repeat_interval)
            self._notify_status(f"Key hold (repeat): {key_name} ({hold_ms}ms)")
            return True
        elif mode == "key_hold_true" and key_name:
            pyautogui.keyDown(key_name)
            time.sleep(max(0, hold_ms) / 1000.0)
            pyautogui.keyUp(key_name)
            self._notify_status(f"Key hold (true): {key_name} ({hold_ms}ms)")
            return True
        elif mode == "hotkey" and hotkey_keys:
            pyautogui.hotkey(*[str(k).lower() for k in hotkey_keys])
            self._notify_status(f"Hotkey: {'+'.join(str(k) for k in hotkey_keys)}")
            return True
        return False

    def _vk_from_key(self, key_name: str):
        key = str(key_name).lower()
        vk_map = {
            "ctrl": win32con.VK_CONTROL,
            "shift": win32con.VK_SHIFT,
            "alt": win32con.VK_MENU,
            "win": win32con.VK_LWIN,
            "enter": win32con.VK_RETURN,
            "tab": win32con.VK_TAB,
            "esc": win32con.VK_ESCAPE,
            "space": win32con.VK_SPACE,
            "up": win32con.VK_UP,
            "down": win32con.VK_DOWN,
            "left": win32con.VK_LEFT,
            "right": win32con.VK_RIGHT,
            "home": win32con.VK_HOME,
            "end": win32con.VK_END,
            "pageup": win32con.VK_PRIOR,
            "pagedown": win32con.VK_NEXT,
            "delete": win32con.VK_DELETE,
            "backspace": win32con.VK_BACK,
            "insert": win32con.VK_INSERT,
        }
        if key in vk_map:
            return vk_map[key]
        if key.startswith("f") and key[1:].isdigit():
            n = int(key[1:])
            if 1 <= n <= 24:
                return win32con.VK_F1 + (n - 1)
        if len(key) == 1:
            ch = key.upper()
            if "A" <= ch <= "Z" or "0" <= ch <= "9":
                return ord(ch)
        return None

    def _target_key_down(self, hwnd: int, key_name: str):
        vk = self._vk_from_key(key_name)
        if vk is None:
            return
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)

    def _target_key_up(self, hwnd: int, key_name: str):
        vk = self._vk_from_key(key_name)
        if vk is None:
            return
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)

    def _target_key_tap(self, hwnd: int, key_name: str):
        self._target_key_down(hwnd, key_name)
        self._target_key_up(hwnd, key_name)

    def _target_hotkey(self, hwnd: int, keys):
        if not keys:
            return
        if len(keys) == 1:
            self._target_key_tap(hwnd, keys[0])
            return
        modifiers = keys[:-1]
        main_key = keys[-1]
        for k in modifiers:
            self._target_key_down(hwnd, k)
        self._target_key_tap(hwnd, main_key)
        for k in reversed(modifiers):
            self._target_key_up(hwnd, k)
    
    def _resolve_click_target(self, hwnd: int, client_x: int, client_y: int):
        """
        Resolve deepest child window at a client point.
        Returns (target_hwnd, local_x, local_y) where local coords are for target_hwnd.
        """
        try:
            screen_x, screen_y = win32gui.ClientToScreen(hwnd, (client_x, client_y))
            current = hwnd
            local_x, local_y = client_x, client_y
            
            # Walk down child hierarchy at click point.
            for _ in range(10):
                child = win32gui.ChildWindowFromPointEx(
                    current,
                    (int(local_x), int(local_y)),
                    win32con.CWP_SKIPDISABLED | win32con.CWP_SKIPINVISIBLE
                )
                if not child or child == current:
                    break
                current = child
                local_x, local_y = win32gui.ScreenToClient(current, (int(screen_x), int(screen_y)))
            
            return current, int(local_x), int(local_y)
        except Exception:
            return hwnd, int(client_x), int(client_y)
    
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
