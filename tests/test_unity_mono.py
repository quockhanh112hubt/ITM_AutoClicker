"""Mono profile isolation, IPC release and keyboard routing without global input."""
import ctypes
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from src.auto_clicker import AutoClicker, _BackgroundInputInterrupted
from src.click_script import ClickAction, ClickType
from src.unity_bridge import MonoShared, UnityBridge, UnityBridgeError, UnityBridgeCancelled
from src.unity_keys import unity_key_code
from src.unity_profiles import ClientInfo, ProfileStore, select_profile, require_profile, UnityProfileError


def mono_candidate():
    return ClientInfo(123, 456, "Mono game", "C:/Games/Game.exe", "UnityWndClass", "x64", "6000.4.7f1",
        "mono", "legacy", True, True, {"UnityPlayer.dll": "a" * 64, "mono-2.0-bdwgc.dll": "b" * 64})


class MonoTests(unittest.TestCase):
    def test_mono_profile_never_matches_il2cpp_family(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProfileStore(Path(temp) / "profiles.json")
            info = mono_candidate()
            self.assertEqual(select_profile(info, store)["id"], "unity6-mono-legacy-x64")
            with self.assertRaisesRegex(UnityProfileError, "untested"):
                require_profile(info, store)
            with self.assertRaisesRegex(UnityProfileError, "does not match"):
                select_profile(info, store, "unity6-legacy-x64")
            saved = store.save_client(info, "Mono test", tested=True)
            self.assertEqual(require_profile(info, ProfileStore(store.path))["id"], saved["id"])
            info.fingerprints["mono-2.0-bdwgc.dll"] = "c" * 64
            self.assertEqual(select_profile(info, store)["status"], "experimental")

    def test_mono_layout_matches_native(self):
        self.assertEqual(ctypes.sizeof(MonoShared), 184)
        self.assertEqual(MonoShared.keys.offset, 96)
        self.assertEqual(MonoShared.key_reads.offset, 160)
        self.assertEqual(MonoShared.client_width.offset, 164)

    def bridge(self):
        bridge = UnityBridge.__new__(UnityBridge)
        bridge._lock = threading.RLock()
        bridge.shared = MonoShared()
        bridge.hwnd = 123
        bridge._is_mono = True
        bridge.cancelled = lambda: False
        return bridge

    def test_release_after_window_closed_clears_all_keys_and_buttons(self):
        bridge = self.bridge()
        bridge.shared.keys[9] = 1 << 18
        bridge.shared.buttons = bridge.shared.enabled = 1
        with patch("src.unity_bridge.win32gui.GetClientRect", side_effect=RuntimeError("closed")):
            bridge.release()
        self.assertFalse(any(bridge.shared.keys))
        self.assertEqual(bridge.shared.buttons, 0)
        self.assertEqual(bridge.shared.enabled, 0)
        self.assertEqual(bridge.shared.seq % 2, 0)

    def test_invalid_key_does_not_corrupt_seqlock_or_enable_input(self):
        bridge = self.bridge()
        with self.assertRaises(UnityBridgeError):
            bridge._command(0, 0, 0, keys=[512])
        self.assertEqual(bridge.shared.seq, 0)
        self.assertEqual(bridge.shared.enabled, 0)

    def test_keyboard_cancel_releases_pressed_keys(self):
        bridge = self.bridge()
        with patch.object(bridge, "_wait_ack", side_effect=[None, UnityBridgeCancelled("stop")]), \
             patch.object(bridge, "_sleep"), \
             patch("src.unity_bridge.win32gui.GetClientRect", return_value=(0, 0, 1440, 810)):
            with self.assertRaises(UnityBridgeCancelled):
                bridge.key_action("key_press", "esc")
        self.assertFalse(any(bridge.shared.keys))
        self.assertEqual(bridge.shared.enabled, 0)

    def test_unread_keyboard_reports_failure_and_releases(self):
        bridge = self.bridge()
        with patch.object(bridge, "_wait_ack"), patch.object(bridge, "_sleep"), \
             patch("src.unity_bridge.win32gui.GetClientRect", return_value=(0, 0, 1440, 810)):
            with self.assertRaisesRegex(UnityBridgeError, "did not read"):
                bridge.key_action("hotkey", hotkey_keys=["ctrl", "a"])
        self.assertFalse(any(bridge.shared.keys))
        self.assertEqual(bridge.shared.enabled, 0)

    def test_keyboard_routes_to_mono_without_focus_or_global_keys(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        engine._unity_bridge = Mock(hwnd=123)
        action = ClickAction(ClickType.POSITION, action_mode="hotkey", hotkey_keys=["ctrl", "r"])
        with patch("src.auto_clicker.win32gui.SetForegroundWindow") as focus, \
             patch("src.auto_clicker.pyautogui.hotkey") as global_keys:
            self.assertTrue(engine._execute_key_action(action, 123))
        engine._unity_bridge.key_action.assert_called_once_with("hotkey", "", ["ctrl", "r"], 1000)
        focus.assert_not_called()
        global_keys.assert_not_called()

    def test_keyboard_failure_stops_without_fallback(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        engine.is_running = True
        engine._unity_bridge = Mock(hwnd=123)
        engine._unity_bridge.key_action.side_effect = UnityBridgeError("unsupported")
        with patch("src.auto_clicker.pyautogui.press") as press:
            with self.assertRaises(UnityBridgeError):
                engine._execute_key_action(ClickAction(ClickType.POSITION, action_mode="key_press", key_name="esc"), 123)
        self.assertFalse(engine.is_running)
        self.assertIn("unsupported", engine._terminal_error)
        press.assert_not_called()

    def test_keyboard_uses_unity_keycodes_instead_of_windows_vk(self):
        self.assertEqual(unity_key_code("ctrl"), 306)
        self.assertEqual(unity_key_code("A"), 97)
        self.assertEqual(unity_key_code("up"), 273)
        with self.assertRaises(ValueError):
            unity_key_code("unknown key")


if __name__ == "__main__":
    unittest.main()
