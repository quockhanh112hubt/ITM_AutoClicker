"""
Main GUI for ITM AutoClicker
"""
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QLabel, QSpinBox, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QRadioButton, QButtonGroup, QStatusBar,
    QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap
from src.click_script import ClickScript, ClickAction, ClickType
from src.config import Config
from src.auto_clicker import AutoClicker
from src.keyboard_listener import KeyboardListener
from src.image_matcher import ImageMatcher
from src.image_recording_manager import ImageRecordingManager
from src.window_picker import WindowPickerDialog, Window
from pynput import mouse
import threading
import win32gui


class SettingsDialog(QDialog):
    """Dialog for configuring click type"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Click Action")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Radio buttons for click type selection
        label = QLabel("Select Click Type:")
        layout.addWidget(label)
        
        self.button_group = QButtonGroup()
        self.radio_position = QRadioButton("Position Based Click")
        self.radio_image = QRadioButton("Image Based Click")
        
        self.radio_position.setChecked(True)
        
        self.button_group.addButton(self.radio_position, 0)
        self.button_group.addButton(self.radio_image, 1)
        
        layout.addWidget(self.radio_position)
        layout.addWidget(self.radio_image)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_selected_type(self) -> ClickType:
        """Get selected click type"""
        if self.radio_position.isChecked():
            return ClickType.POSITION
        else:
            return ClickType.IMAGE


class PositionRecorder:
    """Helper class for recording positions"""
    
    def __init__(self, on_position_recorded=None, on_cancel=None):
        self.positions = []
        self.on_position_recorded = on_position_recorded
        self.on_cancel = on_cancel
        self.is_recording = False
        self.keyboard_listener = KeyboardListener()
    
    def start(self):
        """Start recording positions"""
        self.is_recording = True
        self.positions.clear()
        
        self.keyboard_listener.register_callback('page_up', self._on_page_up)
        self.keyboard_listener.register_callback('esc', self._on_esc)
        self.keyboard_listener.start()
    
    def stop(self):
        """Stop recording"""
        self.keyboard_listener.unregister_callback('page_up', self._on_page_up)
        self.keyboard_listener.unregister_callback('esc', self._on_esc)
        self.keyboard_listener.stop()
        self.is_recording = False
    
    def _on_page_up(self):
        """Handle Page Up key press"""
        if self.is_recording:
            mouse_controller = mouse.Controller()
            x, y = mouse_controller.position
            self.positions.append((int(x), int(y)))
            if self.on_position_recorded:
                self.on_position_recorded(len(self.positions))
    
    def _on_esc(self):
        """Handle ESC key press"""
        if self.is_recording:
            self.stop()
            if self.on_cancel:
                self.on_cancel(self.positions)


class ImageRecorder:
    """Helper class for recording image-based clicks"""
    
    def __init__(self, on_image_saved=None, on_cancel=None):
        self.images = []
        self.on_image_saved = on_image_saved
        self.on_cancel = on_cancel
        self.is_recording = False
        self.keyboard_listener = KeyboardListener()
        self.selection_start = None
        self.selection_end = None
    
    def start(self):
        """Start recording images"""
        self.is_recording = True
        self.images.clear()
        
        self.keyboard_listener.register_callback('page_up', self._on_page_up)
        self.keyboard_listener.register_callback('esc', self._on_esc)
        self.keyboard_listener.start()
    
    def stop(self):
        """Stop recording"""
        self.keyboard_listener.unregister_callback('page_up', self._on_page_up)
        self.keyboard_listener.unregister_callback('esc', self._on_esc)
        self.keyboard_listener.stop()
        self.is_recording = False
    
    def _on_page_up(self):
        """Handle Page Up key press - record click position for current image"""
        if self.is_recording and self.images:
            # The position will be recorded by the main window
            pass
    
    def _on_esc(self):
        """Handle ESC key press"""
        if self.is_recording:
            self.stop()
            if self.on_cancel:
                self.on_cancel(self.images)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ITM AutoClicker")
        self.setMinimumSize(800, 600)
        
        # Initialize config
        self.config = Config()
        
        # Initialize auto clicker
        self.auto_clicker = AutoClicker(
            self.config.get("click_delay_ms", 100),
            self.config.get("priority_cooldown_ms", 800)
        )
        self.auto_clicker.set_on_status_changed(self.on_status_changed)
        
        # Initialize keyboard listener for Start/Stop
        self.keyboard_listener = KeyboardListener()
        self.keyboard_listener.register_callback('end', self.toggle_auto_click)
        self.keyboard_listener.start()
        
        # Current script
        self.current_script = ClickScript()
        
        # Recorders
        self.position_recorder = None
        self.image_recorder = None
        self.image_recording_manager = None
        self.selected_target_window: Window | None = None
        self.target_info_label = None
        
        # Setup UI
        self.setup_ui()
        
        # Update table
        self.update_table()
    
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Tab 1: Main
        main_tab = self.create_main_tab()
        self.tabs.addTab(main_tab, "Main")
        
        # Tab 2: Settings
        settings_tab = self.create_settings_tab()
        self.tabs.addTab(settings_tab, "Settings")
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        central_widget.setLayout(layout)
    
    def create_main_tab(self) -> QWidget:
        """Create main tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Global target window selector
        target_layout = QHBoxLayout()
        target_title = QLabel("Target Window:")
        target_title.setStyleSheet("font-weight: bold;")
        self.target_info_label = QLabel("Not selected")
        btn_select_target = QPushButton("Select Target")
        btn_select_target.clicked.connect(self.on_select_target_window)
        target_layout.addWidget(target_title)
        target_layout.addWidget(self.target_info_label)
        target_layout.addStretch()
        target_layout.addWidget(btn_select_target)
        layout.addLayout(target_layout)
        
        # Title
        title = QLabel("Click Script")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Table for actions
        self.action_table = QTableWidget()
        self.action_table.setColumnCount(5)
        self.action_table.setHorizontalHeaderLabels(["#", "Type", "Image", "Priority", "Details"])
        self.action_table.setColumnWidth(0, 50)
        self.action_table.setColumnWidth(1, 150)
        self.action_table.setColumnWidth(2, 110)
        self.action_table.setColumnWidth(3, 90)
        self.action_table.setColumnWidth(4, 450)
        layout.addWidget(self.action_table)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Add button
        btn_add = QPushButton("Add Action")
        btn_add.clicked.connect(self.on_add_action)
        button_layout.addWidget(btn_add)
        
        # Remove button
        btn_remove = QPushButton("Remove Action")
        btn_remove.clicked.connect(self.on_remove_action)
        button_layout.addWidget(btn_remove)
        
        # Priority button (IMAGE actions)
        btn_priority = QPushButton("Set Priority")
        btn_priority.clicked.connect(self.on_set_priority)
        button_layout.addWidget(btn_priority)
        
        # Clear button
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self.on_clear_all)
        button_layout.addWidget(btn_clear)
        
        # Load button
        btn_load = QPushButton("Load Script")
        btn_load.clicked.connect(self.on_load_script)
        button_layout.addWidget(btn_load)
        
        # Save button
        btn_save = QPushButton("Save Script")
        btn_save.clicked.connect(self.on_save_script)
        button_layout.addWidget(btn_save)
        
        layout.addLayout(button_layout)
        
        # Control buttons layout
        control_layout = QHBoxLayout()
        
        # Start button
        self.btn_start = QPushButton("Start (END)")
        self.btn_start.clicked.connect(self.on_start)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        control_layout.addWidget(self.btn_start)
        
        # Stop button
        self.btn_stop = QPushButton("Stop (END)")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.btn_stop.setEnabled(False)
        control_layout.addWidget(self.btn_stop)
        
        layout.addLayout(control_layout)
        
        tab.setLayout(layout)
        return tab
    
    def create_settings_tab(self) -> QWidget:
        """Create settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Delay setting
        delay_layout = QHBoxLayout()
        delay_label = QLabel("Click Delay (ms):")
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setMinimum(0)
        self.delay_spinbox.setMaximum(10000)
        self.delay_spinbox.setValue(self.config.get("click_delay_ms", 100))
        self.delay_spinbox.valueChanged.connect(self.on_delay_changed)
        
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()
        layout.addLayout(delay_layout)
        
        # Priority cooldown setting
        priority_layout = QHBoxLayout()
        priority_label = QLabel("Priority Cooldown (ms):")
        self.priority_cooldown_spinbox = QSpinBox()
        self.priority_cooldown_spinbox.setMinimum(0)
        self.priority_cooldown_spinbox.setMaximum(60000)
        self.priority_cooldown_spinbox.setValue(self.config.get("priority_cooldown_ms", 800))
        self.priority_cooldown_spinbox.valueChanged.connect(self.on_priority_cooldown_changed)
        
        priority_layout.addWidget(priority_label)
        priority_layout.addWidget(self.priority_cooldown_spinbox)
        priority_layout.addStretch()
        layout.addLayout(priority_layout)
        
        layout.addStretch()
        
        tab.setLayout(layout)
        return tab
    
    def update_table(self):
        """Update the actions table"""
        self.action_table.setRowCount(len(self.current_script.get_actions()))
        
        for i, action in enumerate(self.current_script.get_actions()):
            self.action_table.setRowHeight(i, 56)

            # Index
            item_index = QTableWidgetItem(str(i + 1))
            item_index.setFlags(item_index.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.action_table.setItem(i, 0, item_index)
            
            # Type
            item_type = QTableWidgetItem(action.type.value.upper())
            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.action_table.setItem(i, 1, item_type)
            
            # Image preview
            preview_label = QLabel("-")
            preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if action.type == ClickType.IMAGE:
                image_path = action.data.get('image_path', '')
                if image_path and os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        preview_label.setPixmap(
                            pixmap.scaled(
                                96,
                                48,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                        )
                        preview_label.setText("")
            self.action_table.setCellWidget(i, 2, preview_label)
            
            # Priority
            if action.type == ClickType.IMAGE:
                priority_level = int(action.data.get('priority_level', 0) or 0)
                priority_text = f"P{priority_level}" if priority_level > 0 else "-"
            else:
                priority_text = "-"
            item_priority = QTableWidgetItem(priority_text)
            item_priority.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_priority.setFlags(item_priority.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.action_table.setItem(i, 3, item_priority)

            # Details
            if action.type == ClickType.POSITION:
                x = action.data.get('x', 0)
                y = action.data.get('y', 0)
                target_title = action.data.get('target_title', '')
                target_part = f" | Target: {target_title}" if target_title else ""
                details = f"Position: ({x}, {y}){target_part}"
            else:
                image_path = action.data.get('image_path', '')
                offset_x = action.data.get('offset_x', 0)
                offset_y = action.data.get('offset_y', 0)
                priority_level = int(action.data.get('priority_level', 0) or 0)
                priority_part = f" | Priority: P{priority_level}" if priority_level > 0 else ""
                target_title = action.data.get('target_title', '')
                target_part = f" | Target: {target_title}" if target_title else ""
                details = (
                    f"Image: {os.path.basename(image_path)} | Offset: ({offset_x}, {offset_y})"
                    f"{priority_part}{target_part}"
                )
            
            item_details = QTableWidgetItem(details)
            item_details.setFlags(item_details.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.action_table.setItem(i, 4, item_details)
    
    def on_add_action(self):
        """Handle add action button"""
        if not self._ensure_target_selected():
            return

        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            click_type = dialog.get_selected_type()
            
            if click_type == ClickType.POSITION:
                self.start_position_recording()
            else:
                self.start_image_recording()
    
    def start_position_recording(self):
        """Start recording positions"""
        if not self.selected_target_window:
            self.statusBar.showMessage("Position recording cancelled (invalid target window)")
            return
        
        reply = QMessageBox.information(
            self,
            "Position Recording",
            f"Target: {self.selected_target_window.title}\n\n"
            "Move mouse to desired positions and press PAGE UP to record each position.\n"
            "Press ESC when finished.",
            QMessageBox.StandardButton.Ok
        )
        
        if reply == QMessageBox.StandardButton.Ok:
            self.position_recorder = PositionRecorder(
                on_position_recorded=self.on_position_recorded,
                on_cancel=self.on_position_recording_cancelled
            )
            self.position_recorder.start()
            self.statusBar.showMessage("Recording positions... Press PAGE UP to record, ESC to finish")
    
    def on_position_recorded(self, count: int):
        """Handle position recorded"""
        self.statusBar.showMessage(f"Recording positions... ({count} recorded) Press PAGE UP to record, ESC to finish")
    
    def on_position_recording_cancelled(self, positions):
        """Handle position recording cancelled"""
        if positions:
            target_hwnd = None
            target_title = ""
            if self.selected_target_window:
                target_hwnd = int(self.selected_target_window.hwnd)
                target_title = self.selected_target_window.title
            
            for x, y in positions:
                action_data = {
                    "x": int(x),
                    "y": int(y),
                }
                if target_hwnd is not None:
                    action_data["target_hwnd"] = target_hwnd
                    action_data["target_title"] = target_title
                    try:
                        client_x, client_y = win32gui.ScreenToClient(target_hwnd, (int(x), int(y)))
                        action_data["client_x"] = int(client_x)
                        action_data["client_y"] = int(client_y)
                    except Exception:
                        pass
                
                action = ClickAction(ClickType.POSITION, **action_data)
                self.current_script.add_action(action)
            self.update_table()
            self.statusBar.showMessage(f"Added {len(positions)} position-based click(s)")
        else:
            self.statusBar.showMessage("No positions recorded")
    
    def start_image_recording(self):
        """Start recording images using the new manager"""
        if not self.selected_target_window:
            self.statusBar.showMessage("Image recording cancelled (no target window selected)")
            return

        self.image_recording_manager = ImageRecordingManager(
            on_complete=self.on_image_recording_complete,
            on_cancel=self.on_image_recording_cancelled,
            on_image_recorded=self.on_image_recorded,
            parent=self
        )
        self.image_recording_manager.start(target_window=self.selected_target_window)
        self.statusBar.showMessage(f"Image recording started. Target: {self.selected_target_window.title}")
    
    def on_image_recorded(self, recorded: dict, total_count: int):
        """Handle one image+click position recorded and persist it immediately"""
        action = ClickAction(
            ClickType.IMAGE,
            image_path=recorded.get("image_path", ""),
            offset_x=0,
            offset_y=0,
            click_x=recorded.get("click_x"),
            click_y=recorded.get("click_y"),
            click_client_x=recorded.get("click_client_x"),
            click_client_y=recorded.get("click_client_y"),
            target_hwnd=recorded.get("target_hwnd"),
            target_title=recorded.get("target_title", ""),
            priority_level=0
        )
        self.current_script.add_action(action)
        self.update_table()
        self.statusBar.showMessage(
            f"Recorded {total_count} image action(s). Continue selecting, press ESC to finish."
        )
    
    def on_image_recording_complete(self, recorded_images):
        """Handle image recording complete"""
        count = len(recorded_images) if recorded_images else 0
        if count > 0:
            self.statusBar.showMessage(f"Image recording finished. Total recorded: {count}")
        else:
            self.statusBar.showMessage("Image recording finished. No images recorded.")
    
    def on_image_recording_cancelled(self):
        """Handle image recording cancelled"""
        self.statusBar.showMessage("Image recording cancelled")

    
    def on_remove_action(self):
        """Handle remove action button"""
        current_row = self.action_table.currentRow()
        if current_row >= 0:
            self.current_script.remove_action(current_row)
            self.update_table()
            self.statusBar.showMessage("Action removed")
    
    def on_set_priority(self):
        """Set priority for selected IMAGE action"""
        row = self.action_table.currentRow()
        if row < 0:
            self.statusBar.showMessage("Select an action row first")
            return
        
        actions = self.current_script.get_actions()
        if row >= len(actions):
            self.statusBar.showMessage("Invalid selected row")
            return
        
        action = actions[row]
        if action.type != ClickType.IMAGE:
            QMessageBox.information(self, "Set Priority", "Priority is available only for IMAGE actions.")
            return
        
        current_level = int(action.data.get("priority_level", 0) or 0)
        value, ok = QInputDialog.getInt(
            self,
            "Set Priority Level",
            "Priority level (0 = disabled, 1 = highest):",
            current_level,
            0,
            999,
            1
        )
        if not ok:
            return
        
        action.data["priority_level"] = int(value)
        self.update_table()
        if value > 0:
            self.statusBar.showMessage(f"Row {row + 1} set to priority P{value}")
        else:
            self.statusBar.showMessage(f"Priority disabled for row {row + 1}")
    
    def on_clear_all(self):
        """Handle clear all button"""
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Are you sure you want to clear all actions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.current_script.clear()
            self.update_table()
            self.statusBar.showMessage("All actions cleared")
    
    def on_save_script(self):
        """Handle save script button"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Script",
            "scripts",
            "Script Files (*.json)"
        )
        
        if file_path:
            try:
                self.current_script.save(file_path)
                self.statusBar.showMessage(f"Script saved: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save script: {e}")
    
    def on_load_script(self):
        """Handle load script button"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Script",
            "scripts",
            "Script Files (*.json)"
        )
        
        if file_path:
            try:
                self.current_script = ClickScript.load(file_path)
                self.update_table()
                self.statusBar.showMessage(f"Script loaded: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load script: {e}")
    
    def on_start(self):
        """Handle start button"""
        if len(self.current_script.get_actions()) == 0:
            QMessageBox.warning(self, "Warning", "No actions to execute!")
            return

        if not self._ensure_target_selected():
            return
        
        self._apply_selected_target_to_actions()
        self.update_table()
        
        self.auto_clicker.execute_script(self.current_script)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
    
    def on_stop(self):
        """Handle stop button"""
        self.auto_clicker.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
    
    def toggle_auto_click(self):
        """Toggle auto click (END key)"""
        if self.auto_clicker.is_running:
            self.on_stop()
        else:
            self.on_start()
    
    def on_delay_changed(self, value: int):
        """Handle delay changed"""
        self.auto_clicker.set_delay(value)
        self.config.set("click_delay_ms", value)
    
    def on_priority_cooldown_changed(self, value: int):
        """Handle priority cooldown changed"""
        self.auto_clicker.set_priority_cooldown(value)
        self.config.set("priority_cooldown_ms", value)
    
    def on_status_changed(self, message: str):
        """Handle status changed"""
        self.statusBar.showMessage(message)
    
    def on_select_target_window(self):
        """Select a global target window for recording and execution"""
        picker = WindowPickerDialog(parent=self)
        if not picker.exec():
            return
        
        selected = picker.get_selected_window()
        if not selected:
            self.statusBar.showMessage("No target window selected")
            return
        
        self.selected_target_window = selected
        self._update_target_label()
        self.statusBar.showMessage(f"Target selected: {selected.title}")
    
    def _update_target_label(self):
        """Update target info label in main tab"""
        if not self.target_info_label:
            return
        
        if self.selected_target_window:
            self.target_info_label.setText(f"{self.selected_target_window.title} (hwnd={self.selected_target_window.hwnd})")
        else:
            self.target_info_label.setText("Not selected")
    
    def _ensure_target_selected(self) -> bool:
        """Ensure a global target window is selected"""
        if self.selected_target_window:
            try:
                if win32gui.IsWindow(int(self.selected_target_window.hwnd)):
                    return True
                self.statusBar.showMessage("Selected target is no longer valid. Please reselect target window.")
                self.selected_target_window = None
                self._update_target_label()
            except Exception:
                self.selected_target_window = None
                self._update_target_label()
        
        self.on_select_target_window()
        return self.selected_target_window is not None
    
    def _apply_selected_target_to_actions(self):
        """Apply selected target to all actions before Start."""
        if not self.selected_target_window:
            return
        
        target_hwnd = int(self.selected_target_window.hwnd)
        target_title = self.selected_target_window.title
        
        for action in self.current_script.get_actions():
            action.data["target_hwnd"] = target_hwnd
            action.data["target_title"] = target_title
            
            if action.type == ClickType.POSITION:
                # Keep recorded client coordinates if available to avoid drift.
                client_x = action.data.get("client_x")
                client_y = action.data.get("client_y")
                x = action.data.get("x")
                y = action.data.get("y")
                if (client_x is None or client_y is None) and x is not None and y is not None:
                    try:
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(x), int(y)))
                        action.data["client_x"] = int(cx)
                        action.data["client_y"] = int(cy)
                    except Exception:
                        pass
            elif action.type == ClickType.IMAGE:
                # Keep recorded client coordinates if available to avoid drift.
                click_client_x = action.data.get("click_client_x")
                click_client_y = action.data.get("click_client_y")
                click_x = action.data.get("click_x")
                click_y = action.data.get("click_y")
                if (click_client_x is None or click_client_y is None) and click_x is not None and click_y is not None:
                    try:
                        cx, cy = win32gui.ScreenToClient(target_hwnd, (int(click_x), int(click_y)))
                        action.data["click_client_x"] = int(cx)
                        action.data["click_client_y"] = int(cy)
                    except Exception:
                        pass
    
    def closeEvent(self, event):
        """Handle window close"""
        self.keyboard_listener.stop()
        self.auto_clicker.stop()
        event.accept()


def main():
    """Main entry point"""
    app = sys.modules.get('PyQt6.QtWidgets.QApplication') or __import__('PyQt6.QtWidgets', fromlist=['QApplication']).QApplication([])
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
