"""Profile UI contracts without accessing game processes or loading helpers."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from src.main_window import MainWindow
from src.config import Config
from src.unity_profiles import ProfileStore
from src.window_picker import Window
from src.click_script import ClickAction, ClickType
from PyQt6.QtCore import Qt
from test_unity_profiles import candidate


class UnityProfileUITests(unittest.TestCase):
    def test_unchecking_branch_and_action_updates_running_snapshot(self):
        w = self.window
        w._add_action_to_selected_branch(ClickAction(ClickType.IMAGE_DIRECT, priority_level=1))
        w._add_action_to_selected_branch(ClickAction(ClickType.POSITION, x=1, y=2))
        w.update_table()
        script, keys = w._build_runtime_script_and_key_map()
        w.auto_clicker.current_script = script
        w._running_action_key_map = keys
        w.auto_clicker.is_running = True
        try:
            group = w.script_tree.topLevelItem(0)
            group.setCheckState(0, Qt.CheckState.Unchecked)
            self.assertTrue(all(not a.data['__normal_enabled'] for a in script.actions))
            group.setCheckState(0, Qt.CheckState.Checked)
            self.assertTrue(all(a.data['__normal_enabled'] for a in script.actions))
            w._tree_action_items[(0, 0)].setCheckState(0, Qt.CheckState.Unchecked)
            self.assertFalse(script.actions[0].data['__normal_enabled'])
            self.assertTrue(script.actions[1].data['__normal_enabled'])
        finally:
            w.auto_clicker.is_running = False

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Config(str(Path(self.temp.name) / "settings.json"))
        self.enterContext(patch("src.main_window.Config", return_value=self.config))
        self.enterContext(patch("src.main_window.KeyboardListener.start"))
        self.enterContext(patch.object(MainWindow, "_setup_system_tray"))
        self.enterContext(patch.object(MainWindow, "_apply_always_on_top_to_main"))
        self.enterContext(patch("src.main_window.QTimer.singleShot"))
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_profile_preference_persists_and_cannot_change_while_running(self):
        w = self.window
        index = w.unity_profile_combo.findData("unity6-legacy-x64")
        w.unity_profile_combo.setCurrentIndex(index)
        w.unity_allow_experimental_checkbox.setChecked(True)
        saved = Config(self.config.config_file)
        self.assertEqual(saved.get("unity_profile_id"), "unity6-legacy-x64")
        self.assertTrue(saved.get("allow_experimental_unity_profiles"))
        w.auto_clicker.is_running = True
        try:
            w.unity_profile_combo.setCurrentIndex(0)
            w.unity_allow_experimental_checkbox.setChecked(False)
            self.assertEqual(w.unity_profile_combo.currentData(), "unity6-legacy-x64")
            self.assertTrue(w.unity_allow_experimental_checkbox.isChecked())
        finally:
            w.auto_clicker.is_running = False

    def test_stale_scan_is_ignored_and_full_screen_clears_client(self):
        w = self.window
        w._unity_scan_token = 2
        w._unity_scan_identity = (123, 456)
        w._on_unity_scan_completed({"token": 1, "identity": (123, 456), "info": candidate()})
        self.assertIsNone(w._unity_client_info)
        w._on_unity_scan_completed({"token": 2, "identity": (123, 456), "info": candidate()})
        self.assertIn("experimental", w.unity_profile_status_label.text())
        w._full_screen_target = True
        w._queue_unity_scan()
        self.assertIsNone(w._unity_client_info)
        self.assertFalse(w.unity_tested_button.isEnabled())

    def test_async_detection_does_not_load_a_helper(self):
        w = self.window
        w.selected_target_window = Window(123, "Other game", "CustomUnityWindowClass")
        with patch("src.main_window.win32process.GetWindowThreadProcessId", return_value=(1, 456)), \
             patch("src.main_window.inspect_client", return_value=candidate()), \
             patch("src.unity_bridge._load_helper") as load:
            w._queue_unity_scan(force=True)
            deadline = time.monotonic() + 2
            while w._unity_client_info is None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.005)
        self.assertIsNotNone(w._unity_client_info)
        self.assertIn("Other Unity game", w.unity_client_info_label.text())
        load.assert_not_called()

    def test_mark_tested_saves_exact_build_and_selects_it(self):
        w = self.window
        w._unity_client_info = candidate()
        with patch("src.main_window.inspect_client", return_value=candidate()), \
             patch("src.main_window.QInputDialog.getText", return_value=("My client", True)):
            w._save_unity_client_profile(tested=True)
        saved = ProfileStore(w.unity_profile_store.path).custom
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "user-tested")
        self.assertEqual(saved[0]["fingerprints"], candidate().fingerprints)
        self.assertEqual(w.unity_profile_combo.currentData(), saved[0]["id"])

    def test_export_report_includes_profile_and_build_identity(self):
        w = self.window
        w._unity_client_info = candidate()
        output = Path(self.temp.name) / "report.json"
        with patch("src.main_window.QFileDialog.getSaveFileName", return_value=(str(output), "JSON")):
            w._export_unity_detection_report()
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["selection"]["status"], "experimental")
        self.assertEqual(report["client"]["fingerprints"], candidate().fingerprints)


if __name__ == "__main__":
    unittest.main()
