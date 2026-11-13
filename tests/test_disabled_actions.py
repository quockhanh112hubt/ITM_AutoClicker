"""Unchecked items must never reach scanners or input, including priority/IF."""
import unittest
from unittest.mock import patch
from src.auto_clicker import AutoClicker
from src.click_script import ClickAction, ClickScript, ClickType


class DisabledActionsTests(unittest.TestCase):
    def engine(self, *actions):
        engine = AutoClicker()
        engine.current_script = ClickScript()
        for action in actions:
            engine.current_script.add_action(action)
        engine.is_running = True
        return engine

    def test_disabled_priority_image_is_neither_scanned_nor_clicked(self):
        for kind in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
            with self.subTest(kind=kind):
                action = ClickAction(kind, priority_level=1, __normal_enabled=False)
                engine = self.engine(action)
                with patch.object(engine, "_is_image_action_triggered") as scan, \
                     patch.object(engine, "_execute_image_click") as image, \
                     patch.object(engine, "_execute_image_direct_click") as direct:
                    engine._execute_priority_actions()
                scan.assert_not_called()
                image.assert_not_called()
                direct.assert_not_called()

    def test_enabled_priority_still_runs_while_unchecked_neighbor_is_skipped(self):
        disabled = ClickAction(ClickType.IMAGE_DIRECT, priority_level=1, __normal_enabled=False)
        enabled = ClickAction(ClickType.IMAGE_DIRECT, priority_level=1, __normal_enabled=True)
        engine = self.engine(disabled, enabled)
        with patch.object(engine, "_is_image_action_triggered", return_value=True) as scan, \
             patch.object(engine, "_execute_image_direct_click", return_value=True) as execute, \
             patch.object(engine, "_sleep_interruptible", return_value=True):
            engine._execute_priority_actions()
        scan.assert_called_once_with(enabled)
        execute.assert_called_once_with(enabled)

    def test_if_queue_cannot_force_an_unchecked_action(self):
        action = ClickAction(ClickType.IMAGE_DIRECT, __normal_enabled=False, __invokable_enabled=True)
        engine = self.engine(action)
        engine._pending_runtime_indices = [0]
        engine._pending_runtime_forced_counts = {0: 1}
        with patch.object(engine, "_execute_image_direct_click") as click:
            engine._execute_once()
        click.assert_not_called()
        self.assertEqual(engine._action_execution_totals, {})

    def test_disabled_ocr_is_not_polled(self):
        engine = self.engine(ClickAction(ClickType.IMAGE_RECOGNITION, __normal_enabled=False))
        with patch.object(engine, "_execute_image_recognition") as ocr:
            engine._poll_image_recognition_actions()
        ocr.assert_not_called()

    def test_uncheck_during_priority_scan_prevents_the_following_click(self):
        action = ClickAction(ClickType.IMAGE_DIRECT, priority_level=1, __normal_enabled=True)
        engine = self.engine(action)
        def scan(_):
            action.data['__normal_enabled'] = False
            return True
        with patch.object(engine, '_is_image_action_triggered', side_effect=scan), \
             patch.object(engine, '_execute_image_direct_click') as click:
            engine._execute_priority_actions()
        click.assert_not_called()
