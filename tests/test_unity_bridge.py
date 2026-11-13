"""Protocol and routing safeguards. Native integration has a separate fixture."""
import ctypes
import threading
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from src.auto_clicker import AutoClicker, _BackgroundInputInterrupted
from src.click_script import ClickAction, ClickScript, ClickType
from src.unity_bridge import Shared, UnityBridge, UnityBridgeError, UnityBridgeCancelled, _load_helper, HELPER_NAME


class UnityBridgeTests(unittest.TestCase):
    def test_packaged_copy_reuses_only_identical_resident_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            existing = root / "source" / HELPER_NAME
            packaged = root / "packaged" / HELPER_NAME
            existing.parent.mkdir()
            packaged.parent.mkdir()
            existing.write_bytes(b"same helper build")
            packaged.write_bytes(existing.read_bytes())
            with patch("src.unity_bridge.kernel.OpenProcess", return_value=1), \
                 patch("src.unity_bridge.kernel.CloseHandle"), \
                 patch("src.unity_bridge._modules", return_value=[(100, existing)]), \
                 patch("src.unity_bridge.kernel.CreateRemoteThread") as loader:
                _load_helper(123, packaged)
                loader.assert_not_called()
                packaged.write_bytes(b"different helper build")
                with self.assertRaisesRegex(UnityBridgeError, "restart the game"):
                    _load_helper(123, packaged)

    def test_ipc_matches_native_offsets(self):
        self.assertEqual(ctypes.sizeof(Shared), 96)
        self.assertEqual(Shared.seq.offset, 24)
        self.assertEqual(Shared.heartbeat.offset, 56)
        self.assertEqual(Shared.focus_overrides.offset, 84)

    def test_disabled_actions_do_not_block_mouse_only_script(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        script = ClickScript()
        script.add_action(ClickAction(ClickType.POSITION, target_hwnd=1,
            action_mode="key_press", __normal_enabled=False))
        with patch("src.auto_clicker.threading.Thread"):
            engine.execute_script(script)
        self.assertTrue(engine.is_running)
        engine.is_running = False

    def test_invalid_mode_and_full_screen_rejected_before_threads(self):
        for data in ({"target_hwnd": None}, {"target_hwnd": 1, "action_mode": "unsupported"}):
            with self.subTest(data=data):
                engine = AutoClicker(unity_virtual_mouse=True)
                script = ClickScript()
                script.add_action(ClickAction(ClickType.POSITION, **data))
                with self.assertRaises(ValueError), patch("src.auto_clicker.threading.Thread") as worker:
                    engine.execute_script(script)
                worker.assert_not_called()

    def test_unity_path_bypasses_win32_messages(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        with patch.object(engine, "_unity_mouse_action") as send, \
             patch("src.auto_clicker.win32gui.PostMessage") as post, \
             patch("src.auto_clicker.win32gui.SendMessageTimeout") as sync:
            engine._post_click_client(123, 25, 39)
        self.assertEqual(send.call_args.args[:3], (123, 25, 39))
        post.assert_not_called()
        sync.assert_not_called()

    def test_drag_uses_virtual_mouse_even_if_real_drag_was_saved(self):
        engine = AutoClicker(unity_virtual_mouse=True, drag_mode="real")
        action = ClickAction(ClickType.POSITION, drag_client_x=60, drag_client_y=70)
        with patch.object(engine, "_unity_mouse_action") as virtual, \
             patch.object(engine, "_execute_real_drag_for_target") as real:
            self.assertTrue(engine._execute_drag_for_target(action, 123, 25, 39))
        self.assertEqual(virtual.call_args.kwargs["drag_to"], (60, 70))
        real.assert_not_called()

    def test_bridge_failure_stops_instead_of_global_fallback(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        engine.is_running = True
        with patch("src.auto_clicker.UnityBridge", side_effect=UnityBridgeError("wrong build")), \
             patch.object(engine, "_perform_foreground_mouse_action") as real:
            with self.assertRaisesRegex(UnityBridgeError, "wrong build"):
                engine._post_click_client(123, 25, 39)
        self.assertFalse(engine.is_running)
        real.assert_not_called()
        statuses = []
        engine.set_on_status_changed(statuses.append)
        engine._recognition_loop()
        self.assertIn("wrong build", statuses[-1])

    def test_cancellation_does_not_become_delivery_success(self):
        engine = AutoClicker(unity_virtual_mouse=True)
        engine._unity_bridge = Mock(hwnd=123)
        engine._unity_bridge.mouse_action.side_effect = UnityBridgeCancelled()
        with self.assertRaises(_BackgroundInputInterrupted):
            engine._post_click_client(123, 25, 39)

    def test_release_disables_pointer_with_atomic_sequence(self):
        bridge = UnityBridge.__new__(UnityBridge)
        bridge._lock = threading.RLock()
        bridge.shared = Shared()
        bridge.shared.seq = 2
        bridge.shared.enabled = 1
        bridge.shared.buttons = 1
        bridge.release()
        self.assertEqual(bridge.shared.seq, 4)
        self.assertEqual(bridge.shared.enabled, 0)
        self.assertEqual(bridge.shared.buttons, 0)

    def test_reject_outside_client_before_virtual_command(self):
        bridge = UnityBridge.__new__(UnityBridge)
        bridge.cancelled = lambda: False
        bridge.hwnd = 123
        with patch("src.unity_bridge.win32gui.GetClientRect", return_value=(0, 0, 1280, 720)), \
             patch.object(bridge, "_command") as command:
            with self.assertRaisesRegex(UnityBridgeError, "outside"):
                bridge.mouse_action(-1, 50)
        command.assert_not_called()

    def test_paused_gesture_does_not_enable_virtual_input(self):
        bridge = UnityBridge.__new__(UnityBridge)
        bridge.cancelled = lambda: True
        with patch.object(bridge, "_command") as command:
            with self.assertRaises(UnityBridgeCancelled):
                bridge.mouse_action(20, 50)
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
