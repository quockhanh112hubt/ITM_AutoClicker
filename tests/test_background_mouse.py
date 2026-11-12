"""Background mouse contracts; run with python -m unittest discover -s tests -v."""
import threading
import time
import unittest
from unittest.mock import patch

import win32api
import win32con
import win32gui

from src.auto_clicker import AutoClicker, _BackgroundInputInterrupted
from src.click_script import ClickAction, ClickScript, ClickType


class BackgroundMouseTests(unittest.TestCase):
    def setUp(self):
        self.engine = AutoClicker(background_mouse_compatibility=True)
        self.engine.is_running = True
        self.messages = []
        self.waits = []
        self.addCleanup(self.engine.stop)
        self._patch("src.auto_clicker.AppLogger.debug")
        self._patch("src.auto_clicker.AppLogger.warning")
        self._patch("src.auto_clicker.win32gui.ChildWindowFromPointEx", return_value=101)
        self._patch("src.auto_clicker.win32gui.ClientToScreen", side_effect=lambda h, p: (p[0] - 1000, p[1] + 200))
        self.send = self._patch("src.auto_clicker.win32gui.SendMessageTimeout", side_effect=self.record_message)
        self.sleep = self._patch("src.auto_clicker.time.sleep", side_effect=lambda _: None)
        self.wait = self._patch("src.auto_clicker.AutoClicker._sleep_interruptible", side_effect=self.record_wait)
        self.post = self._patch("src.auto_clicker.win32gui.PostMessage")
        # Any accidental foreground fallback must fail the test.
        for name in ("click", "moveTo", "dragTo", "mouseDown", "mouseUp", "scroll"):
            self._patch(f"src.auto_clicker.pyautogui.{name}", side_effect=AssertionError("Real mouse was used"))
        self._patch("src.auto_clicker.win32gui.SetForegroundWindow", side_effect=AssertionError("Target was activated"))

    def _patch(self, name, **kwargs):
        p = patch(name, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    def record_message(self, hwnd, msg, wp, lp, flags, timeout):
        self.messages.append((hwnd, msg, wp, lp))
        self.assertEqual(timeout, 250)
        self.assertTrue(flags & win32con.SMTO_ABORTIFHUNG)
        return 1, 0  # A window procedure returning zero is still successful delivery.

    def record_wait(self, seconds):
        self.waits.append(seconds)
        return True

    def test_click_buttons_have_paced_down_up_at_recorded_client_point(self):
        for button, down, up, mask in (
            ("left", win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON),
            ("right", win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON),
            ("middle", win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP, win32con.MK_MBUTTON),
        ):
            with self.subTest(button=button):
                self.messages.clear()
                self.waits.clear()
                self.engine._post_click_client(101, 35, 60, mouse_button=button)
                lp = win32api.MAKELONG(35, 60)
                self.assertEqual(self.messages, [
                    (101, win32con.WM_MOUSEMOVE, 0, lp),
                    (101, down, mask, lp), (101, up, 0, lp),
                ])
                self.assertEqual(self.waits, [0.03, 0.05])
        self.post.assert_not_called()

    def test_hold_respects_configured_duration(self):
        self.engine._post_click_client(101, 3, 6, action_mode="mouse_hold", hold_ms=725)
        self.assertEqual(self.waits, [0.03, 0.725])

    def test_child_click_uses_child_local_coordinates(self):
        with patch.object(self.engine, "_resolve_click_target", return_value=(202, 5, 9)):
            self.engine._post_click_client(101, 100, 150)
        self.assertTrue(all(m[0] == 202 and m[3] == win32api.MAKELONG(5, 9) for m in self.messages))

    def test_pause_before_down_does_not_click(self):
        self.wait.side_effect = lambda _: False
        with self.assertRaises(_BackgroundInputInterrupted):
            self.engine._post_click_client(101, 3, 6)
        self.assertEqual([m[1] for m in self.messages], [win32con.WM_MOUSEMOVE])

    def test_stop_during_hold_still_sends_up(self):
        self.wait.side_effect = [True, False]
        with self.assertRaises(_BackgroundInputInterrupted):
            self.engine._post_click_client(101, 3, 6, action_mode="mouse_hold", hold_ms=60000)
        self.assertEqual(self.messages[-1][1:3], (win32con.WM_LBUTTONUP, 0))

    def test_timeout_on_down_attempts_up_and_reports_failure(self):
        def timed_out(hwnd, msg, *args):
            if msg == win32con.WM_LBUTTONDOWN:
                raise TimeoutError("unresponsive target")
            return self.record_message(hwnd, msg, *args)
        self.send.side_effect = timed_out
        with self.assertRaisesRegex(RuntimeError, "Background mouse delivery failed"):
            self.engine._post_click_client(101, 3, 6)
        self.assertEqual(self.messages[-1][1], win32con.WM_LBUTTONUP)

    def test_failed_dispatch_is_not_counted_as_executed(self):
        action = ClickAction(ClickType.POSITION, x=3, y=6, target_hwnd=101, client_x=3, client_y=6)
        script = ClickScript()
        script.add_action(action)
        self.engine.current_script = script
        self.send.return_value = (0, 0)
        self.send.side_effect = None
        executed = self._patch("src.auto_clicker.AutoClicker._notify_action_executed")
        with patch.object(self.engine, "_validate_target_window", return_value=(True, "")):
            self.engine._execute_once()
        executed.assert_not_called()
        self.assertEqual(self.engine._action_execution_totals, {})

    def test_wheel_uses_screen_coordinates_and_no_duplicate_root_delivery(self):
        for compatible in (False, True):
            with self.subTest(compatible=compatible):
                self.engine.background_mouse_compatibility = compatible
                self.messages.clear()
                self.post.reset_mock()
                self.engine._post_mouse_wheel(202, 101, 5, 9, -2)
                calls = self.messages if compatible else [c.args for c in self.post.call_args_list]
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(c == (202, win32con.WM_MOUSEWHEEL, (-120 << 16) & 0xFFFFFFFF,
                                          win32api.MAKELONG(-995, 209)) for c in calls))

    def test_drag_release_on_pause_uses_last_delivered_position(self):
        self.wait.side_effect = [True, True, False]
        with self.assertRaises(_BackgroundInputInterrupted):
            self.engine._post_drag_on_target_client(101, 10, 20, 50, 80, drag_ms=60)
        self.assertEqual(self.messages[-1][1:3], (win32con.WM_LBUTTONUP, 0))
        self.assertEqual(self.messages[-1][3], self.messages[-2][3])

    def test_hybrid_compatibility_never_falls_back_to_real_drag(self):
        action = ClickAction(ClickType.POSITION, drag_client_x=50, drag_client_y=80)
        with patch.object(self.engine, "_post_drag_on_target_client", side_effect=RuntimeError("timeout")):
            with patch.object(self.engine, "_execute_real_drag_for_target") as real_drag:
                self.assertFalse(self.engine._execute_drag_for_target(action, 101, 10, 20))
                real_drag.assert_not_called()

    def test_standard_click_remains_asynchronous(self):
        self.engine.background_mouse_compatibility = False
        self.engine._post_click_client(101, 3, 6)
        self.send.assert_not_called()
        self.assertEqual(self.post.call_count, 3)
        self.wait.assert_not_called()

    def test_image_direct_routes_match_to_target_client(self):
        action = ClickAction(ClickType.IMAGE_DIRECT, image_path="template.png", target_hwnd=101)
        with patch("src.auto_clicker.os.path.exists", return_value=True), \
             patch.object(self.engine, "_validate_target_window", return_value=(True, "")), \
             patch.object(self.engine.image_matcher, "find_image_in_window", return_value=(400, 500)), \
             patch("src.auto_clicker.win32gui.ScreenToClient", return_value=(35, 60)), \
             patch.object(self.engine, "_post_click_client") as click:
            self.assertTrue(self.engine._execute_image_direct_click(action))
        self.assertEqual(click.call_args.args[:3], (101, 35, 60))


class NativeBackgroundMouseTests(unittest.TestCase):
    """Dispatch to our own hidden Win32 windows on a separate GUI thread."""

    def test_real_window_delivery_and_child_coordinate_mapping(self):
        ready = threading.Event()
        finish = threading.Event()
        received = []
        state = {}
        relevant = {win32con.WM_MOUSEMOVE, win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP}

        def window_thread():
            name = f"ITMBackgroundMouseTest_{threading.get_ident()}"
            root = child = atom = None
            def procedure(hwnd, msg, wp, lp):
                if msg in relevant:
                    received.append((hwnd, msg, wp, lp, time.monotonic()))
                    return 0
                return win32gui.DefWindowProc(hwnd, msg, wp, lp)
            try:
                wc = win32gui.WNDCLASS()
                wc.lpfnWndProc = procedure
                wc.lpszClassName = name
                atom = win32gui.RegisterClass(wc)
                root = win32gui.CreateWindow(name, "ITM test", win32con.WS_POPUP,
                                             -9000, -9000, 300, 200, 0, 0, 0, None)
                child = win32gui.CreateWindow(name, "Child", win32con.WS_CHILD | win32con.WS_VISIBLE,
                                              20, 30, 100, 100, root, 0, 0, None)
                state.update(root=root, child=child)
                ready.set()
                while not finish.wait(0.001):
                    win32gui.PumpWaitingMessages()
            except Exception as exc:
                state["error"] = exc
                ready.set()
            finally:
                if root:
                    win32gui.DestroyWindow(root)
                if atom:
                    win32gui.UnregisterClass(name, None)

        worker = threading.Thread(target=window_thread, daemon=True)
        worker.start()
        try:
            self.assertTrue(ready.wait(3), "Window thread did not start")
            if "error" in state:
                raise state["error"]
            engine = AutoClicker(background_mouse_compatibility=True)
            engine.is_running = True
            before_cursor = win32gui.GetCursorPos()
            before_focus = win32gui.GetForegroundWindow()
            engine._post_click_client(state["root"], 25, 39)
            # Our window procedure deliberately returns zero; delivery must succeed.
            self.assertEqual([r[1] for r in received], [win32con.WM_MOUSEMOVE,
                                                      win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP])
            self.assertTrue(all(r[0] == state["child"] for r in received))
            self.assertTrue(all(r[3] == win32api.MAKELONG(5, 9) for r in received))
            self.assertGreaterEqual(received[1][4] - received[0][4], 0.025)
            self.assertGreaterEqual(received[2][4] - received[1][4], 0.045)
            # Observe rather than assert: the user may move the mouse during this test.
            print(f"\nNative delivery: cursor {before_cursor} -> {win32gui.GetCursorPos()}, "
                  f"foreground {before_focus} -> {win32gui.GetForegroundWindow()}")
        finally:
            finish.set()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive(), "Window thread did not shut down")


if __name__ == "__main__":
    unittest.main()
