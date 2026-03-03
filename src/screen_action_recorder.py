"""
Global screen action recorder (mouse + keyboard) for replayable POSITION actions.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import win32api
import win32con
from pynput import keyboard


class ScreenActionRecorder:
    """Record user actions globally and convert them to action payloads."""

    _DRAG_DISTANCE_THRESHOLD = 12.0
    _HOLD_DURATION_MS = 300
    _KEY_HOLD_DURATION_MS = 280

    def __init__(self) -> None:
        self.is_recording = False
        self._lock = threading.Lock()
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_poll_thread: Optional[threading.Thread] = None
        self._mouse_poll_stop = threading.Event()
        self._record_start_ts: float = 0.0
        self._last_action_ts: Optional[float] = None
        self._actions: List[Dict[str, Any]] = []

        self._mouse_pos: Tuple[int, int] = (0, 0)
        self._mouse_down: Dict[str, Dict[str, Any]] = {}
        self._pressed_modifiers: set[str] = set()
        self._key_down_map: Dict[str, Dict[str, Any]] = {}
        self._ignored_toggle_keys = {"f10"}
        self._prev_mouse_pressed = {
            "left": False,
            "right": False,
            "middle": False,
        }

    @property
    def action_count(self) -> int:
        with self._lock:
            return len(self._actions)

    @property
    def elapsed_seconds(self) -> float:
        if not self.is_recording:
            return 0.0
        return max(0.0, time.monotonic() - self._record_start_ts)

    def start(self) -> None:
        """Start global recording."""
        if self.is_recording:
            return

        with self._lock:
            self._actions = []
            self._mouse_down = {}
            self._pressed_modifiers = set()
            self._key_down_map = {}
            self._record_start_ts = time.monotonic()
            self._last_action_ts = None

        try:
            px, py = win32api.GetCursorPos()
            self._mouse_pos = (int(px), int(py))
        except Exception:
            self._mouse_pos = (0, 0)
        self._prev_mouse_pressed = {
            "left": self._is_vk_pressed(win32con.VK_LBUTTON),
            "right": self._is_vk_pressed(win32con.VK_RBUTTON),
            "middle": self._is_vk_pressed(win32con.VK_MBUTTON),
        }

        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self.is_recording = True
        self._mouse_poll_stop.clear()
        self._mouse_poll_thread = threading.Thread(target=self._mouse_poll_loop, daemon=True)
        self._mouse_poll_thread.start()
        self._keyboard_listener.start()

    def stop(self) -> List[Dict[str, Any]]:
        """Stop recording and return captured action payloads."""
        self._mouse_poll_stop.set()
        if self._mouse_poll_thread is not None:
            try:
                self._mouse_poll_thread.join(timeout=0.4)
            except Exception:
                pass
            self._mouse_poll_thread = None

        if self._keyboard_listener is not None:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

        self.is_recording = False
        with self._lock:
            result = [dict(action) for action in self._actions]
        return result

    def _mouse_poll_loop(self) -> None:
        while not self._mouse_poll_stop.is_set():
            try:
                x, y = win32api.GetCursorPos()
                self._on_move(int(x), int(y))
            except Exception:
                time.sleep(0.01)
                continue

            now = time.monotonic()
            state_map = {
                "left": self._is_vk_pressed(win32con.VK_LBUTTON),
                "right": self._is_vk_pressed(win32con.VK_RBUTTON),
                "middle": self._is_vk_pressed(win32con.VK_MBUTTON),
            }
            for button_name, pressed in state_map.items():
                prev_pressed = bool(self._prev_mouse_pressed.get(button_name, False))
                if pressed != prev_pressed:
                    self._on_click_state_change(
                        int(x), int(y), button_name, bool(pressed), now
                    )
                    self._prev_mouse_pressed[button_name] = bool(pressed)
            time.sleep(0.01)

    def _on_move(self, x, y) -> None:
        if not self.is_recording:
            return
        px, py = int(x), int(y)
        self._mouse_pos = (px, py)
        now = time.monotonic()
        with self._lock:
            for state in self._mouse_down.values():
                dx = px - int(state["start_x"])
                dy = py - int(state["start_y"])
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > float(state.get("max_dist", 0.0)):
                    state["max_dist"] = dist
                    state["last_x"] = px
                    state["last_y"] = py
                    state["last_ts"] = now

    def _on_click_state_change(
        self,
        x: int,
        y: int,
        button_name: str,
        pressed: bool,
        now: float,
    ) -> None:
        if not self.is_recording:
            return

        if not button_name:
            return

        px, py = int(x), int(y)
        self._mouse_pos = (px, py)
        if pressed:
            with self._lock:
                self._mouse_down[button_name] = {
                    "start_x": px,
                    "start_y": py,
                    "start_ts": now,
                    "last_x": px,
                    "last_y": py,
                    "last_ts": now,
                    "max_dist": 0.0,
                }
            return

        with self._lock:
            state = self._mouse_down.pop(button_name, None)
        if state is None:
            state = {
                "start_x": px,
                "start_y": py,
                "start_ts": now,
                "last_x": px,
                "last_y": py,
                "last_ts": now,
                "max_dist": 0.0,
            }

        start_x = int(state["start_x"])
        start_y = int(state["start_y"])
        hold_ms = max(0, int((now - float(state["start_ts"])) * 1000))
        max_dist = float(state.get("max_dist", 0.0))

        if max_dist >= self._DRAG_DISTANCE_THRESHOLD:
            payload = {
                "x": start_x,
                "y": start_y,
                "action_mode": "mouse_drag",
                "mouse_button": button_name,
                "drag_to_x": int(px),
                "drag_to_y": int(py),
                "drag_ms": max(60, hold_ms),
            }
        elif hold_ms >= self._HOLD_DURATION_MS:
            payload = {
                "x": start_x,
                "y": start_y,
                "action_mode": "mouse_hold",
                "mouse_button": button_name,
                "hold_ms": hold_ms,
            }
        else:
            payload = {
                "x": int(px),
                "y": int(py),
                "action_mode": "mouse_click",
                "mouse_button": button_name,
            }
        self._append_action(payload, now)

    def _on_key_press(self, key) -> None:
        if not self.is_recording:
            return
        key_name = self._normalize_key_name(key)
        if not key_name:
            return
        if key_name in self._ignored_toggle_keys:
            return

        now = time.monotonic()
        with self._lock:
            if self._is_modifier_key(key_name):
                self._pressed_modifiers.add(key_name)
            if key_name not in self._key_down_map:
                self._key_down_map[key_name] = {
                    "start_ts": now,
                    "mods": tuple(sorted(self._pressed_modifiers)),
                }

    def _on_key_release(self, key) -> None:
        if not self.is_recording:
            return
        key_name = self._normalize_key_name(key)
        if not key_name:
            return
        if key_name in self._ignored_toggle_keys:
            return

        now = time.monotonic()
        with self._lock:
            state = self._key_down_map.pop(key_name, None)
            mods_snapshot = tuple(state.get("mods", ())) if state else tuple(sorted(self._pressed_modifiers))
            if self._is_modifier_key(key_name):
                self._pressed_modifiers.discard(key_name)
                return

        hold_ms = 0
        if state:
            hold_ms = max(0, int((now - float(state.get("start_ts", now))) * 1000))

        x, y = self._mouse_pos
        if mods_snapshot:
            keys = list(mods_snapshot)
            if key_name not in keys:
                keys.append(key_name)
            payload = {
                "x": int(x),
                "y": int(y),
                "action_mode": "hotkey",
                "mouse_button": "left",
                "hotkey_keys": [str(k).lower() for k in keys if str(k).strip()],
            }
        elif hold_ms >= self._KEY_HOLD_DURATION_MS:
            payload = {
                "x": int(x),
                "y": int(y),
                "action_mode": "key_hold_true",
                "mouse_button": "left",
                "key_name": key_name,
                "hold_ms": hold_ms,
            }
        else:
            payload = {
                "x": int(x),
                "y": int(y),
                "action_mode": "key_press",
                "mouse_button": "left",
                "key_name": key_name,
            }
        self._append_action(payload, now)

    def _append_action(self, payload: Dict[str, Any], event_ts: float) -> None:
        with self._lock:
            if self._last_action_ts is None:
                delay_ms = int(max(0.0, event_ts - self._record_start_ts) * 1000)
            else:
                delay_ms = int(max(0.0, event_ts - self._last_action_ts) * 1000)
            self._last_action_ts = event_ts
            payload["delay_ms"] = max(0, int(delay_ms))
            self._actions.append(payload)

    @staticmethod
    def _is_vk_pressed(vk_code: int) -> bool:
        try:
            return bool(win32api.GetAsyncKeyState(int(vk_code)) & 0x8000)
        except Exception:
            return False

    @staticmethod
    def _is_modifier_key(name: str) -> bool:
        return name in {"ctrl", "shift", "alt", "win"}

    @staticmethod
    def _normalize_key_name(key) -> str:
        name = getattr(key, "name", None)
        if isinstance(name, str) and name:
            normalized = name.strip().lower()
            mapping = {
                "ctrl_l": "ctrl",
                "ctrl_r": "ctrl",
                "alt_l": "alt",
                "alt_gr": "alt",
                "alt_r": "alt",
                "shift_l": "shift",
                "shift_r": "shift",
                "cmd": "win",
                "cmd_l": "win",
                "cmd_r": "win",
                "windows": "win",
                "return": "enter",
                "escape": "esc",
                "prior": "pageup",
                "next": "pagedown",
            }
            return mapping.get(normalized, normalized)
        char = getattr(key, "char", None)
        if isinstance(char, str) and char:
            return char.lower()
        return ""
