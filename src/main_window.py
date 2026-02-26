"""
Main GUI for ITM AutoClicker
"""
import sys
import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget,
    QLabel, QSpinBox, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QRadioButton, QButtonGroup, QStatusBar,
    QComboBox, QTreeWidget, QTreeWidgetItem, QInputDialog, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon
from src.click_script import ClickScript, ClickAction, ClickType
from src.config import Config
from src.auto_clicker import AutoClicker
from src.keyboard_listener import KeyboardListener
from src.image_recording_manager import ImageRecordingManager
from src.window_picker import WindowPickerDialog, Window
from src.action_options import choose_advanced_action
from pynput import mouse
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
        self.radio_image_direct = QRadioButton("Image Direct Click (click on matched image)")
        
        self.radio_position.setChecked(True)
        
        self.button_group.addButton(self.radio_position, 0)
        self.button_group.addButton(self.radio_image, 1)
        self.button_group.addButton(self.radio_image_direct, 2)
        
        layout.addWidget(self.radio_position)
        layout.addWidget(self.radio_image)
        layout.addWidget(self.radio_image_direct)
        
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
        elif self.radio_image_direct.isChecked():
            return ClickType.IMAGE_DIRECT
        else:
            return ClickType.IMAGE


class PositionRecorder:
    """Helper class for recording positions"""
    
    def __init__(self, on_position_recorded=None, on_cancel=None, on_choose_action=None, key_bindings=None):
        self.positions = []
        self.on_position_recorded = on_position_recorded
        self.on_cancel = on_cancel
        self.on_choose_action = on_choose_action
        self.is_recording = False
        self.keyboard_listener = KeyboardListener()
        self.key_bindings = key_bindings or {}
    
    def start(self):
        """Start recording positions"""
        self.is_recording = True
        self.positions.clear()
        
        for logical_key, physical_key in self.key_bindings.items():
            self.keyboard_listener.set_binding(logical_key, physical_key)
        
        self.keyboard_listener.register_callback('page_up', self._on_page_up)
        self.keyboard_listener.register_callback('page_down', self._on_page_down)
        self.keyboard_listener.register_callback('esc', self._on_esc)
        self.keyboard_listener.start()
    
    def stop(self):
        """Stop recording"""
        self.keyboard_listener.unregister_callback('page_up', self._on_page_up)
        self.keyboard_listener.unregister_callback('page_down', self._on_page_down)
        self.keyboard_listener.unregister_callback('esc', self._on_esc)
        self.keyboard_listener.stop()
        self.is_recording = False
    
    def _on_page_up(self):
        """Handle Page Up key press"""
        if self.is_recording:
            mouse_controller = mouse.Controller()
            x, y = mouse_controller.position
            self.positions.append({
                "x": int(x),
                "y": int(y),
                "action_mode": "mouse_click",
                "mouse_button": "left"
            })
            if self.on_position_recorded:
                self.on_position_recorded(len(self.positions))
    
    def _on_page_down(self):
        """Handle Page Down key press for custom action recording"""
        if not self.is_recording:
            return
        
        mouse_controller = mouse.Controller()
        x, y = mouse_controller.position
        
        action_data = {"action_mode": "mouse_click", "mouse_button": "right"}
        if self.on_choose_action:
            try:
                chosen = self.on_choose_action(int(x), int(y))
            except TypeError:
                chosen = self.on_choose_action()
            if not chosen:
                return
            action_data = chosen
        
        payload = {
            "x": int(x),
            "y": int(y),
        }
        payload.update(action_data)
        self.positions.append(payload)
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
    action_executed_signal = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self._icons = self._load_ui_icons()
        self.setWindowTitle("ITM AutoClicker")
        if not self._icons.get("app").isNull():
            self.setWindowIcon(self._icons.get("app"))
        self.setMinimumSize(800, 600)
        
        # Initialize config
        self.config = Config()
        
        # Initialize auto clicker
        self.auto_clicker = AutoClicker(
            self.config.get("click_delay_ms", 100),
            self.config.get("priority_cooldown_ms", 800),
            self.config.get("drag_mode", "hybrid")
        )
        self.auto_clicker.set_on_status_changed(self.on_status_changed)
        self.auto_clicker.set_on_action_executed(self._on_action_executed_from_worker)
        self.hotkey_bindings = self._load_hotkey_bindings()
        
        # Initialize keyboard listener for Start/Stop
        self.keyboard_listener = KeyboardListener()
        self.keyboard_listener.set_binding('end', self.hotkey_bindings['end'])
        self.keyboard_listener.register_callback('end', self.toggle_auto_click)
        self.keyboard_listener.start()
        
        # Grouped scripts (branches)
        self.script_groups: list[dict] = []
        self.action_counts: dict[tuple[int, int], int] = {}
        self._tree_action_items: dict[tuple[int, int], QTreeWidgetItem] = {}
        self._running_action_key_map: list[tuple[int, int]] = []
        
        # Recorders
        self.position_recorder = None
        self.image_recorder = None
        self.image_recording_manager = None
        self.pending_image_action_type = ClickType.IMAGE
        self.pending_branch_index: int | None = None
        self._active_action_tool_button: QToolButton | None = None
        self._action_tool_buttons: list[QToolButton] = []
        self._last_selected_branch_index: int | None = None
        self.selected_target_window: Window | None = None
        self.target_info_label = None
        self._updating_table = False
        self.action_executed_signal.connect(self._on_action_executed_main_thread)
        self._ensure_default_group()
        
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
        title = QLabel("Click Script List")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Action toolbar (replaces Add Action + Select Click Type dialog)
        action_toolbar = QHBoxLayout()
        self.btn_tool_position = QToolButton()
        self.btn_tool_position.setText("Position Based")
        self.btn_tool_position.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_position.setCheckable(True)
        self.btn_tool_position.setMinimumWidth(110)
        self.btn_tool_position.setMinimumHeight(56)
        if self._icons.get("position") and not self._icons.get("position").isNull():
            self.btn_tool_position.setIcon(self._icons.get("position"))
            self.btn_tool_position.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_position.clicked.connect(lambda: self.on_toolbar_add_action(ClickType.POSITION, self.btn_tool_position))
        action_toolbar.addWidget(self.btn_tool_position)

        self.btn_tool_image = QToolButton()
        self.btn_tool_image.setText("Image Based")
        self.btn_tool_image.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_image.setCheckable(True)
        self.btn_tool_image.setMinimumWidth(110)
        self.btn_tool_image.setMinimumHeight(56)
        if self._icons.get("image") and not self._icons.get("image").isNull():
            self.btn_tool_image.setIcon(self._icons.get("image"))
            self.btn_tool_image.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_image.clicked.connect(lambda: self.on_toolbar_add_action(ClickType.IMAGE, self.btn_tool_image))
        action_toolbar.addWidget(self.btn_tool_image)

        self.btn_tool_image_direct = QToolButton()
        self.btn_tool_image_direct.setText("Image Direct")
        self.btn_tool_image_direct.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_image_direct.setCheckable(True)
        self.btn_tool_image_direct.setMinimumWidth(110)
        self.btn_tool_image_direct.setMinimumHeight(56)
        if self._icons.get("image_direct") and not self._icons.get("image_direct").isNull():
            self.btn_tool_image_direct.setIcon(self._icons.get("image_direct"))
            self.btn_tool_image_direct.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_image_direct.clicked.connect(
            lambda: self.on_toolbar_add_action(ClickType.IMAGE_DIRECT, self.btn_tool_image_direct)
        )
        action_toolbar.addWidget(self.btn_tool_image_direct)
        self._action_tool_buttons = [
            self.btn_tool_position,
            self.btn_tool_image,
            self.btn_tool_image_direct,
        ]
        self._apply_action_toolbar_button_style()

        action_toolbar.addStretch()

        # Start/Stop buttons moved next to action toolbar (right side)
        self.btn_start = QPushButton(f"Start ({self._to_hotkey_display(self.hotkey_bindings['end'])})")
        self.btn_start.clicked.connect(self.on_start)
        self.btn_start.setMinimumWidth(130)
        self.btn_start.setMinimumHeight(65)
        action_toolbar.addWidget(self.btn_start)

        self.btn_stop = QPushButton(f"Stop ({self._to_hotkey_display(self.hotkey_bindings['end'])})")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setMinimumWidth(130)
        self.btn_stop.setMinimumHeight(65)
        action_toolbar.addWidget(self.btn_stop)
        self._update_run_button_states(False)
        layout.addLayout(action_toolbar)
        
        # Tree list for script branches/actions
        self.script_tree = QTreeWidget()
        self.script_tree.setColumnCount(7)
        self.script_tree.setHeaderLabels(["Click Script List", "Type", "Image", "Priority", "Delay (ms)", "Count", "Details"])
        self.script_tree.setColumnWidth(0, 220)
        self.script_tree.setColumnWidth(1, 110)
        self.script_tree.setColumnWidth(2, 110)
        self.script_tree.setColumnWidth(3, 90)
        self.script_tree.setColumnWidth(4, 90)
        self.script_tree.setColumnWidth(5, 80)
        self.script_tree.setColumnWidth(6, 360)
        self.script_tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.script_tree.itemChanged.connect(self.on_script_tree_item_changed)
        self.script_tree.itemDoubleClicked.connect(self.on_script_tree_item_double_clicked)
        self.script_tree.currentItemChanged.connect(self.on_script_tree_current_item_changed)
        layout.addWidget(self.script_tree)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        btn_add_group = QPushButton("Add Branch")
        btn_add_group.clicked.connect(self.on_add_branch)
        button_layout.addWidget(btn_add_group)
        
        # Remove button
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.on_remove_action)
        button_layout.addWidget(btn_remove)
        
        btn_rename = QPushButton("Rename")
        btn_rename.clicked.connect(self.on_rename_selected)
        button_layout.addWidget(btn_rename)
        
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
        
        # Drag mode setting
        drag_layout = QHBoxLayout()
        drag_label = QLabel("Drag Mode (target window):")
        self.drag_mode_combo = QComboBox()
        self.drag_mode_combo.addItem("Hybrid (Background first)")
        self.drag_mode_combo.addItem("Background only")
        self.drag_mode_combo.addItem("Real drag (occupy mouse)")
        mode = str(self.config.get("drag_mode", "hybrid")).lower()
        if mode == "background":
            self.drag_mode_combo.setCurrentIndex(1)
        elif mode == "real":
            self.drag_mode_combo.setCurrentIndex(2)
        else:
            self.drag_mode_combo.setCurrentIndex(0)
        self.drag_mode_combo.currentIndexChanged.connect(self.on_drag_mode_changed)
        drag_layout.addWidget(drag_label)
        drag_layout.addWidget(self.drag_mode_combo)
        drag_layout.addStretch()
        layout.addLayout(drag_layout)
        
        # Hotkey settings
        hotkey_title = QLabel("Hotkeys")
        hotkey_font = QFont()
        hotkey_font.setBold(True)
        hotkey_title.setFont(hotkey_font)
        layout.addWidget(hotkey_title)
        
        self.hotkey_options = self._build_hotkey_options()
        
        hk_confirm_layout = QHBoxLayout()
        hk_confirm_label = QLabel("Record Confirm (PAGE UP):")
        self.hotkey_page_up_combo = QComboBox()
        self.hotkey_page_up_combo.addItems(self.hotkey_options)
        page_up_text = self._to_hotkey_display(self.hotkey_bindings["page_up"])
        if self.hotkey_page_up_combo.findText(page_up_text) < 0:
            self.hotkey_page_up_combo.addItem(page_up_text)
        self.hotkey_page_up_combo.setCurrentText(page_up_text)
        self.hotkey_page_up_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("page_up", text)
        )
        hk_confirm_layout.addWidget(hk_confirm_label)
        hk_confirm_layout.addWidget(self.hotkey_page_up_combo)
        hk_confirm_layout.addStretch()
        layout.addLayout(hk_confirm_layout)
        
        hk_action_layout = QHBoxLayout()
        hk_action_label = QLabel("Record Action Menu (PAGE DOWN):")
        self.hotkey_page_down_combo = QComboBox()
        self.hotkey_page_down_combo.addItems(self.hotkey_options)
        page_down_text = self._to_hotkey_display(self.hotkey_bindings["page_down"])
        if self.hotkey_page_down_combo.findText(page_down_text) < 0:
            self.hotkey_page_down_combo.addItem(page_down_text)
        self.hotkey_page_down_combo.setCurrentText(page_down_text)
        self.hotkey_page_down_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("page_down", text)
        )
        hk_action_layout.addWidget(hk_action_label)
        hk_action_layout.addWidget(self.hotkey_page_down_combo)
        hk_action_layout.addStretch()
        layout.addLayout(hk_action_layout)
        
        hk_toggle_layout = QHBoxLayout()
        hk_toggle_label = QLabel("Start/Stop Toggle (END):")
        self.hotkey_end_combo = QComboBox()
        self.hotkey_end_combo.addItems(self.hotkey_options)
        end_text = self._to_hotkey_display(self.hotkey_bindings["end"])
        if self.hotkey_end_combo.findText(end_text) < 0:
            self.hotkey_end_combo.addItem(end_text)
        self.hotkey_end_combo.setCurrentText(end_text)
        self.hotkey_end_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("end", text)
        )
        hk_toggle_layout.addWidget(hk_toggle_label)
        hk_toggle_layout.addWidget(self.hotkey_end_combo)
        hk_toggle_layout.addStretch()
        layout.addLayout(hk_toggle_layout)
        
        layout.addStretch()
        
        tab.setLayout(layout)
        return tab
    
    def update_table(self):
        """Update tree list for script branches/actions."""
        self._updating_table = True
        try:
            preferred_branch = self._get_selected_branch_index(require_selection=False)
            self._tree_action_items.clear()
            self.script_tree.clear()
            
            for group_index, group in enumerate(self.script_groups):
                group_item = QTreeWidgetItem(self.script_tree)
                group_item.setText(0, group.get("name", f"Branch {group_index + 1}"))
                group_item.setText(6, f"{len(group.get('actions', []))} action(s)")
                group_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                group_item.setCheckState(
                    0,
                    Qt.CheckState.Checked if group.get("enabled", True) else Qt.CheckState.Unchecked
                )
                group_item.setData(0, Qt.ItemDataRole.UserRole, ("group", group_index))
                
                for action_index, entry in enumerate(group.get("actions", [])):
                    action = entry.get("action")
                    if not isinstance(action, ClickAction):
                        continue
                    
                    key = (group_index, action_index)
                    action_item = QTreeWidgetItem(group_item)
                    action_item.setData(0, Qt.ItemDataRole.UserRole, ("action", group_index, action_index))
                    action_item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    action_item.setCheckState(
                        0,
                        Qt.CheckState.Checked if entry.get("enabled", True) else Qt.CheckState.Unchecked
                    )
                    action_item.setText(0, str(entry.get("name", f"Action {action_index + 1}")))
                    self._apply_action_icon(action_item, action)
                    action_item.setText(1, action.type.value.upper())
                    
                    # Image preview
                    preview_label = QLabel("-")
                    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    if action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
                        image_path = action.data.get("image_path", "")
                        if image_path and os.path.exists(image_path):
                            pixmap = QPixmap(image_path)
                            if not pixmap.isNull():
                                preview_label.setPixmap(
                                    pixmap.scaled(
                                        96, 48,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation
                                    )
                                )
                                preview_label.setText("")
                    self.script_tree.setItemWidget(action_item, 2, preview_label)
                    
                    # Priority
                    if action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
                        priority_combo = self._create_priority_combo(group_index, action_index, action)
                        self.script_tree.setItemWidget(action_item, 3, priority_combo)
                    else:
                        action_item.setText(3, "-")
                    
                    # Delay (editable)
                    delay_ms = int(action.data.get("delay_ms", self.config.get("click_delay_ms", 100)) or 0)
                    delay_spin = QSpinBox()
                    delay_spin.setMinimum(0)
                    delay_spin.setMaximum(600000)
                    delay_spin.setValue(delay_ms)
                    delay_spin.valueChanged.connect(
                        lambda value, g=group_index, a=action_index: self._on_delay_spin_changed(g, a, value)
                    )
                    self.script_tree.setItemWidget(action_item, 4, delay_spin)
                    
                    # Count
                    action_item.setText(5, str(int(self.action_counts.get(key, 0))))
                    action_item.setTextAlignment(5, Qt.AlignmentFlag.AlignCenter)
                    
                    # Details
                    action_item.setText(6, self._build_action_details(action))
                    self._tree_action_items[key] = action_item
                
                group_item.setExpanded(True)
            
            if preferred_branch is not None and 0 <= preferred_branch < len(self.script_groups):
                top = self.script_tree.topLevelItem(int(preferred_branch))
                if top:
                    self.script_tree.setCurrentItem(top)
                    self._last_selected_branch_index = int(preferred_branch)
            elif len(self.script_groups) > 0:
                top = self.script_tree.topLevelItem(0)
                if top:
                    self.script_tree.setCurrentItem(top)
                    self._last_selected_branch_index = 0
        finally:
            self._updating_table = False
    
    def on_add_action(self):
        """Handle add action button"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._start_add_action_flow(dialog.get_selected_type())

    def on_toolbar_add_action(self, click_type: ClickType, source_button: QToolButton):
        """Handle toolbar quick-add action buttons."""
        if self._active_action_tool_button is source_button and self._is_recording_active():
            source_button.setChecked(True)
            return
        
        # If another action flow is active, auto-ESC it before starting new one.
        if self._active_action_tool_button is not None and self._active_action_tool_button is not source_button:
            self._cancel_recording_for_action_switch()
        
        self._active_action_tool_button = source_button
        source_button.setChecked(True)
        self._start_add_action_flow(click_type)

    def _start_add_action_flow(self, click_type: ClickType):
        """Shared flow for adding action by type."""
        if not self._ensure_target_selected():
            self._release_active_action_tool_button()
            return
        
        branch_index = self._get_selected_branch_index(require_selection=True)
        if branch_index is None:
            QMessageBox.information(
                self,
                "Select Branch",
                "Please select a branch in Click Script List before adding action."
            )
            self.statusBar.showMessage("Select a branch first, then add action")
            self._release_active_action_tool_button()
            return
        
        self.pending_branch_index = int(branch_index)
        if click_type == ClickType.POSITION:
            self.start_position_recording()
        else:
            self.start_image_recording(click_type)

    def _release_active_action_tool_button(self):
        """Release pressed state of currently active toolbar action button."""
        if self._active_action_tool_button:
            self._active_action_tool_button.setChecked(False)
            self._active_action_tool_button = None

    def _set_action_toolbar_locked(self, locked: bool, active_button: QToolButton | None):
        """Lock other action buttons while one action-flow is in progress."""
        # No longer locking buttons; kept for compatibility.
        for button in self._action_tool_buttons:
            button.setEnabled(True)

    def _cancel_recording_for_action_switch(self):
        """Auto-ESC current recording flow when switching action button."""
        # Position recording: stop and persist current recorded points (ESC behavior).
        if self.position_recorder and self.position_recorder.is_recording:
            positions = list(self.position_recorder.positions)
            self.position_recorder.stop()
            self.on_position_recording_cancelled(positions)
            return
        
        # Image recording: finish gracefully (ESC behavior).
        if self.image_recording_manager and self.image_recording_manager.is_recording:
            self.image_recording_manager.finish()
    
    def on_add_branch(self):
        """Add a new script branch."""
        default_name = f"Branch {len(self.script_groups) + 1}"
        name, ok = QInputDialog.getText(self, "Add Branch", "Branch name:", text=default_name)
        if not ok:
            return
        title = (name or "").strip() or default_name
        self.script_groups.append({"name": title, "enabled": True, "actions": []})
        self.update_table()
        self.statusBar.showMessage(f"Added branch: {title}")
    
    def start_position_recording(self):
        """Start recording positions"""
        if not self.selected_target_window:
            self.statusBar.showMessage("Position recording cancelled (invalid target window)")
            return
        
        reply = QMessageBox.information(
            self,
            "Position Recording",
            f"Target: {self.selected_target_window.title}\n\n"
            f"{self._to_hotkey_display(self.hotkey_bindings['page_up'])}: Record Left Click at current mouse position.\n"
            f"{self._to_hotkey_display(self.hotkey_bindings['page_down'])}: Choose advanced action and record at current position.\n"
            "Press ESC when finished.",
            QMessageBox.StandardButton.Ok
        )
        
        if reply == QMessageBox.StandardButton.Ok:
            self.position_recorder = PositionRecorder(
                on_position_recorded=self.on_position_recorded,
                on_cancel=self.on_position_recording_cancelled,
                on_choose_action=self._choose_record_action,
                key_bindings=self._get_recording_hotkeys()
            )
            self.position_recorder.start()
            self.statusBar.showMessage(
                f"Recording actions... {self._to_hotkey_display(self.hotkey_bindings['page_up'])}=Left, "
                f"{self._to_hotkey_display(self.hotkey_bindings['page_down'])}=Advanced actions, ESC=finish"
            )
        else:
            self.pending_branch_index = None
            self._release_active_action_tool_button()
    
    def on_position_recorded(self, count: int):
        """Handle position recorded"""
        self.statusBar.showMessage(
            f"Recording actions... ({count} recorded) "
            f"{self._to_hotkey_display(self.hotkey_bindings['page_up'])}=Left, "
            f"{self._to_hotkey_display(self.hotkey_bindings['page_down'])}=Advanced, ESC=finish"
        )
    
    def on_position_recording_cancelled(self, positions):
        """Handle position recording cancelled"""
        if positions:
            default_delay_ms = int(self.config.get("click_delay_ms", 100))
            target_hwnd = None
            target_title = ""
            if self.selected_target_window:
                target_hwnd = int(self.selected_target_window.hwnd)
                target_title = self.selected_target_window.title
            
            for pos in positions:
                if isinstance(pos, dict):
                    x = int(pos.get("x", 0))
                    y = int(pos.get("y", 0))
                    action_mode = str(pos.get("action_mode", "mouse_click")).lower()
                    mouse_button = str(pos.get("mouse_button", "left")).lower()
                    hold_ms = pos.get("hold_ms")
                    drag_to_x = pos.get("drag_to_x")
                    drag_to_y = pos.get("drag_to_y")
                    drag_ms = pos.get("drag_ms")
                    key_name = pos.get("key_name")
                    hotkey_keys = pos.get("hotkey_keys")
                else:
                    # Backward compatibility for older tuple-based records.
                    x, y = pos
                    action_mode = "mouse_click"
                    mouse_button = "left"
                    hold_ms = None
                    drag_to_x = None
                    drag_to_y = None
                    drag_ms = None
                    key_name = None
                    hotkey_keys = None
                action_data = {
                    "x": int(x),
                    "y": int(y),
                    "action_mode": action_mode,
                    "mouse_button": mouse_button if mouse_button in ("left", "right", "middle") else "left",
                    "delay_ms": default_delay_ms,
                }
                if hold_ms is not None:
                    action_data["hold_ms"] = int(hold_ms)
                if drag_to_x is not None and drag_to_y is not None:
                    action_data["drag_to_x"] = int(drag_to_x)
                    action_data["drag_to_y"] = int(drag_to_y)
                if drag_ms is not None:
                    action_data["drag_ms"] = int(drag_ms)
                if key_name:
                    action_data["key_name"] = str(key_name)
                if hotkey_keys:
                    action_data["hotkey_keys"] = list(hotkey_keys)
                if target_hwnd is not None:
                    action_data["target_hwnd"] = target_hwnd
                    action_data["target_title"] = target_title
                    try:
                        client_x, client_y = win32gui.ScreenToClient(target_hwnd, (int(x), int(y)))
                        action_data["client_x"] = int(client_x)
                        action_data["client_y"] = int(client_y)
                    except Exception:
                        pass
                    if drag_to_x is not None and drag_to_y is not None:
                        try:
                            drag_client_x, drag_client_y = win32gui.ScreenToClient(
                                target_hwnd, (int(drag_to_x), int(drag_to_y))
                            )
                            action_data["drag_client_x"] = int(drag_client_x)
                            action_data["drag_client_y"] = int(drag_client_y)
                        except Exception:
                            pass
                
                action = ClickAction(ClickType.POSITION, **action_data)
                self._add_action_to_selected_branch(action, self.pending_branch_index)
            self.update_table()
            self.statusBar.showMessage(f"Added {len(positions)} position-based click(s)")
        else:
            self.statusBar.showMessage("No positions recorded")
        self.pending_branch_index = None
        self._release_active_action_tool_button()
    
    def _choose_record_action(self, start_x: int | None = None, start_y: int | None = None):
        """Show action chooser for PAGE DOWN during recording."""
        return choose_advanced_action(self, start_x, start_y)
    
    def start_image_recording(self, image_click_type: ClickType = ClickType.IMAGE):
        """Start recording images using the new manager"""
        if not self.selected_target_window:
            self.statusBar.showMessage("Image recording cancelled (no target window selected)")
            return

        self.pending_image_action_type = image_click_type
        require_click_position = image_click_type == ClickType.IMAGE
        
        self.image_recording_manager = ImageRecordingManager(
            on_complete=self.on_image_recording_complete,
            on_cancel=self.on_image_recording_cancelled,
            on_image_recorded=self.on_image_recorded,
            key_bindings=self._get_recording_hotkeys(),
            parent=self
        )
        self.image_recording_manager.start(
            target_window=self.selected_target_window,
            require_click_position=require_click_position
        )
        mode = "Image Based" if require_click_position else "Image Direct"
        self.statusBar.showMessage(f"{mode} recording started. Target: {self.selected_target_window.title}")
    
    def on_image_recorded(self, recorded: dict, total_count: int):
        """Handle one image+click position recorded and persist it immediately"""
        is_direct = self.pending_image_action_type == ClickType.IMAGE_DIRECT
        default_delay_ms = int(self.config.get("click_delay_ms", 100))
        action = ClickAction(
            self.pending_image_action_type,
            image_path=recorded.get("image_path", ""),
            offset_x=0,
            offset_y=0,
            click_x=recorded.get("click_x"),
            click_y=recorded.get("click_y"),
            click_client_x=recorded.get("click_client_x"),
            click_client_y=recorded.get("click_client_y"),
            action_mode=recorded.get("action_mode", "mouse_click"),
            mouse_button=recorded.get("mouse_button", "left"),
            hold_ms=recorded.get("hold_ms"),
            drag_to_x=recorded.get("drag_to_x"),
            drag_to_y=recorded.get("drag_to_y"),
            drag_client_x=recorded.get("drag_client_x"),
            drag_client_y=recorded.get("drag_client_y"),
            drag_ms=recorded.get("drag_ms"),
            key_name=recorded.get("key_name"),
            hotkey_keys=recorded.get("hotkey_keys"),
            target_hwnd=recorded.get("target_hwnd"),
            target_title=recorded.get("target_title", ""),
            priority_level=1 if is_direct else 0,
            delay_ms=default_delay_ms
        )
        self._add_action_to_selected_branch(action, self.pending_branch_index)
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
        self.pending_branch_index = None
        self._release_active_action_tool_button()
    
    def on_image_recording_cancelled(self):
        """Handle image recording cancelled"""
        self.statusBar.showMessage("Image recording cancelled")
        self.pending_branch_index = None
        self._release_active_action_tool_button()

    
    def on_remove_action(self):
        """Handle remove selected branch/action"""
        checked_actions = []
        checked_groups = []
        
        for gi, group in enumerate(self.script_groups):
            group_item_checked = False
            group_item = self.script_tree.topLevelItem(gi)
            if group_item:
                group_item_checked = group_item.checkState(0) == Qt.CheckState.Checked
            if group_item_checked:
                checked_groups.append(gi)
            
            for ai, entry in enumerate(group.get("actions", [])):
                if bool(entry.get("enabled", True)):
                    checked_actions.append((gi, ai))
        
        # Prefer removing checked actions first (avoid accidental group delete).
        if checked_actions:
            by_group: dict[int, list[int]] = {}
            for gi, ai in checked_actions:
                by_group.setdefault(gi, []).append(ai)
            for gi, indexes in by_group.items():
                indexes.sort(reverse=True)
                actions = self.script_groups[gi].get("actions", [])
                for ai in indexes:
                    if 0 <= ai < len(actions):
                        actions.pop(ai)
            self.update_table()
            self.statusBar.showMessage(f"Removed {len(checked_actions)} action(s)")
            return
        
        if checked_groups:
            for gi in sorted(checked_groups, reverse=True):
                if 0 <= gi < len(self.script_groups):
                    self.script_groups.pop(gi)
            self._ensure_default_group()
            self.update_table()
            self.statusBar.showMessage(f"Removed {len(checked_groups)} branch(es)")
            return
        
        current_item = self.script_tree.currentItem()
        if not current_item:
            self.statusBar.showMessage("Tick action/branch or select one item to remove")
            return
        
        payload = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        
        if payload[0] == "group":
            group_index = int(payload[1])
            if 0 <= group_index < len(self.script_groups):
                self.script_groups.pop(group_index)
                self._ensure_default_group()
                self.update_table()
                self.statusBar.showMessage("Branch removed")
            return
        
        if payload[0] == "action":
            group_index = int(payload[1])
            action_index = int(payload[2])
            if 0 <= group_index < len(self.script_groups):
                actions = self.script_groups[group_index].get("actions", [])
                if 0 <= action_index < len(actions):
                    actions.pop(action_index)
                    self.update_table()
                    self.statusBar.showMessage("Action removed")
    
    def on_rename_selected(self):
        """Rename currently selected branch/action."""
        item = self.script_tree.currentItem()
        if not item:
            self.statusBar.showMessage("Select a branch or action to rename")
            return
        self.on_script_tree_item_double_clicked(item, 0)
    
    def _create_priority_combo(self, group_index: int, action_index: int, action: ClickAction) -> QComboBox:
        """Create priority combo for image action rows."""
        combo = QComboBox()
        combo.addItem("-")
        for level in range(1, 21):
            combo.addItem(f"P{level}")
        
        priority_level = int(action.data.get("priority_level", 0) or 0)
        if priority_level <= 0:
            combo.setCurrentText("-")
        elif priority_level <= 20:
            combo.setCurrentText(f"P{priority_level}")
        else:
            combo.setCurrentText("P20")
            action.data["priority_level"] = 20
        
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.currentTextChanged.connect(
            lambda text, g=group_index, a=action_index: self._on_priority_combo_changed(g, a, text)
        )
        return combo
    
    def _on_priority_combo_changed(self, group_index: int, action_index: int, text: str):
        """Handle priority combo changes from table."""
        if self._updating_table:
            return
        
        if group_index < 0 or group_index >= len(self.script_groups):
            return
        group = self.script_groups[group_index]
        actions = group.get("actions", [])
        if action_index < 0 or action_index >= len(actions):
            return
        action = actions[action_index].get("action")
        
        if action.type not in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
            return
        
        raw = (text or "").strip().upper()
        if raw in ("", "-", "0", "P0"):
            level = 0
        else:
            if raw.startswith("P"):
                raw = raw[1:]
            if not raw.isdigit():
                self.statusBar.showMessage("Priority must be '-' or a positive number (example: P1)")
                self._updating_table = True
                try:
                    current = int(action.data.get("priority_level", 0) or 0)
                    item = self._tree_action_items.get((group_index, action_index))
                    combo = self.script_tree.itemWidget(item, 3) if item else None
                    if isinstance(combo, QComboBox):
                        combo.setCurrentText("-" if current <= 0 else f"P{current}")
                finally:
                    self._updating_table = False
                return
            level = int(raw)
        
        action.data["priority_level"] = max(0, level)
        self.update_table()
        if level > 0:
            self.statusBar.showMessage(
                f"{group.get('name', f'Branch {group_index + 1}')} - Action {action_index + 1}: priority P{level}"
            )
        else:
            self.statusBar.showMessage(
                f"{group.get('name', f'Branch {group_index + 1}')} - Action {action_index + 1}: priority disabled"
            )
    
    def on_script_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle checkboxes and editable fields in script tree."""
        if self._updating_table:
            return
        if item is None:
            return
        
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        
        if column == 0:
            if payload[0] == "group":
                group_index = int(payload[1])
                if group_index < 0 or group_index >= len(self.script_groups):
                    return
                checked = item.checkState(0) == Qt.CheckState.Checked
                group = self.script_groups[group_index]
                group["enabled"] = checked
                self._updating_table = True
                try:
                    for action_index, entry in enumerate(group.get("actions", [])):
                        entry["enabled"] = checked
                        child = self._tree_action_items.get((group_index, action_index))
                        if child:
                            child.setCheckState(
                                0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                            )
                finally:
                    self._updating_table = False
                return
            
            if payload[0] == "action":
                group_index = int(payload[1])
                action_index = int(payload[2])
                if group_index < 0 or group_index >= len(self.script_groups):
                    return
                actions = self.script_groups[group_index].get("actions", [])
                if action_index < 0 or action_index >= len(actions):
                    return
                checked = item.checkState(0) == Qt.CheckState.Checked
                actions[action_index]["enabled"] = checked
                
                # Reflect mixed states on branch checkbox.
                enabled_count = sum(1 for x in actions if bool(x.get("enabled", True)))
                any_checked = enabled_count > 0
                all_checked = enabled_count == len(actions) and len(actions) > 0
                self.script_groups[group_index]["enabled"] = any_checked
                parent = item.parent()
                if parent:
                    self._updating_table = True
                    try:
                        if all_checked:
                            parent.setCheckState(0, Qt.CheckState.Checked)
                        elif any_checked:
                            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
                        else:
                            parent.setCheckState(0, Qt.CheckState.Unchecked)
                    finally:
                        self._updating_table = False
                return
        
    def on_script_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Rename branch/action when double-clicking the name column."""
        if column != 0 or item is None:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        
        if payload[0] == "group":
            group_index = int(payload[1])
            if group_index < 0 or group_index >= len(self.script_groups):
                return
            current_name = self.script_groups[group_index].get("name", f"Branch {group_index + 1}")
            name, ok = QInputDialog.getText(self, "Rename Branch", "Branch name:", text=str(current_name))
            if not ok:
                return
            new_name = (name or "").strip()
            if not new_name:
                return
            self.script_groups[group_index]["name"] = new_name
            item.setText(0, new_name)
            self.statusBar.showMessage(f"Renamed branch: {new_name}")
            return
        
        if payload[0] == "action":
            group_index = int(payload[1])
            action_index = int(payload[2])
            if group_index < 0 or group_index >= len(self.script_groups):
                return
            actions = self.script_groups[group_index].get("actions", [])
            if action_index < 0 or action_index >= len(actions):
                return
            current_name = actions[action_index].get("name", f"Action {action_index + 1}")
            name, ok = QInputDialog.getText(self, "Rename Action", "Action name:", text=str(current_name))
            if not ok:
                return
            new_name = (name or "").strip()
            if not new_name:
                return
            actions[action_index]["name"] = new_name
            item.setText(0, new_name)
            self.statusBar.showMessage(f"Renamed action: {new_name}")

    def on_script_tree_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        """Track last selected branch to keep add-action flow smooth across refreshes."""
        if current is None:
            return
        payload = current.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        if payload[0] == "group":
            self._last_selected_branch_index = int(payload[1])
        elif payload[0] == "action":
            self._last_selected_branch_index = int(payload[1])
    
    def _on_delay_spin_changed(self, group_index: int, action_index: int, value: int):
        """Handle delay changes from per-action spinbox."""
        if self._updating_table:
            return
        if group_index < 0 or group_index >= len(self.script_groups):
            return
        actions = self.script_groups[group_index].get("actions", [])
        if action_index < 0 or action_index >= len(actions):
            return
        action = actions[action_index].get("action")
        if not isinstance(action, ClickAction):
            return
        action.data["delay_ms"] = max(0, int(value))
    
    def _build_hotkey_options(self) -> list[str]:
        """Build available key options for hotkey combo boxes."""
        special = [
            "Page Up", "Page Down", "End", "Home", "Insert", "Delete",
            "Space", "Tab", "Enter"
        ]
        function_keys = [f"F{i}" for i in range(1, 13)]
        letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
        digits = [str(i) for i in range(0, 10)]
        return special + function_keys + letters + digits

    def _apply_action_toolbar_button_style(self):
        """Apply 3D style for action toolbar buttons."""
        style = """
        QToolButton {
            min-width: 110px;
            min-height: 52px;
            max-height: 64px;
            padding: 4px 8px 6px 8px;
            border: 1px solid #8d99a6;
            border-bottom: 3px solid #64707d;
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #fefefe, stop:1 #e2e6ea);
            color: #22303d;
            font-weight: 600;
            font-size: 11px;
        }
        QToolButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #ffffff, stop:1 #d8dee5);
            border: 1px solid #6a7785;
        }
        QToolButton:pressed, QToolButton:checked {
            padding-top: 5px;
            padding-bottom: 4px;
            border: 1px solid #4f5a67;
            border-bottom: 1px solid #4f5a67;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #cfd5dc, stop:1 #b9c1ca);
            color: #111a22;
        }
        QToolButton:disabled {
            border: 1px solid #c3c8cd;
            border-bottom: 2px solid #b5bcc3;
            background: #e9ecef;
            color: #8d96a0;
        }
        """
        for button in self._action_tool_buttons:
            button.setStyleSheet(style)

    def _resource_path(self, relative_path: str) -> str:
        """Resolve resource path for dev and PyInstaller."""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_dir, relative_path)

    def _load_ui_icons(self) -> dict:
        """Load UI icons from resource folder."""
        app_icon = QIcon(self._resource_path(os.path.join("resource", "Icon.ico")))
        position_icon = QIcon(self._resource_path(os.path.join("resource", "Position.png")))
        image_icon = QIcon(self._resource_path(os.path.join("resource", "Image.png")))
        image_direct_icon = QIcon(self._resource_path(os.path.join("resource", "ImageDirect.png")))
        return {
            "app": app_icon,
            "position": position_icon,
            "image": image_icon,
            "image_direct": image_direct_icon,
        }

    def _apply_action_icon(self, item: QTreeWidgetItem, action: ClickAction):
        """Attach action-type icon to tree row."""
        if action.type == ClickType.POSITION:
            icon = self._icons.get("position")
        elif action.type == ClickType.IMAGE_DIRECT:
            icon = self._icons.get("image_direct")
        else:
            icon = self._icons.get("image")
        if icon and not icon.isNull():
            item.setIcon(0, icon)
    
    def _to_hotkey_display(self, key_token: str) -> str:
        """Convert internal token to user display string."""
        token = str(key_token or "").strip().lower()
        mapping = {
            "page_up": "Page Up",
            "page_down": "Page Down",
            "end": "End",
            "home": "Home",
            "insert": "Insert",
            "delete": "Delete",
            "esc": "Esc",
            "space": "Space",
            "tab": "Tab",
            "enter": "Enter",
        }
        if token in mapping:
            return mapping[token]
        if token.startswith("f") and token[1:].isdigit():
            return token.upper()
        if len(token) == 1:
            return token.upper()
        return token
    
    def _from_hotkey_display(self, display_value: str) -> str:
        """Convert user display string to internal token."""
        value = str(display_value or "").strip().lower()
        value = value.replace(" ", "_").replace("-", "_")
        return value
    
    def _load_hotkey_bindings(self) -> dict:
        """Load hotkey bindings from config."""
        bindings = {
            "page_up": str(self.config.get("hotkey_page_up", "page_up")),
            "page_down": str(self.config.get("hotkey_page_down", "page_down")),
            "end": str(self.config.get("hotkey_end", "end")),
        }
        return bindings
    
    def _get_recording_hotkeys(self) -> dict:
        """Get recording hotkey mapping for listeners."""
        return {
            "page_up": self.hotkey_bindings["page_up"],
            "page_down": self.hotkey_bindings["page_down"],
        }
    
    def _update_run_button_states(self, running: bool):
        """Update Start/Stop button enabled state and visual style."""
        start_active = not running
        stop_active = running
        
        self.btn_start.setEnabled(start_active)
        self.btn_stop.setEnabled(stop_active)
        
        start_style = (
            "QPushButton {"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #56c46c, stop:1 #2f9f45);"
            "color: white; font-weight: 700; border: 1px solid #2a7f3b; border-bottom: 3px solid #1f5f2c;"
            "border-radius: 7px; padding: 6px 12px; }"
            "QPushButton:pressed { border-bottom: 1px solid #1f5f2c; padding-top: 8px; padding-bottom: 4px; }"
            if start_active else
            "QPushButton {"
            "background: #e6e8ea; color: #8b949e; font-weight: 700; border: 1px solid #c7ccd1;"
            "border-bottom: 2px solid #b6bcc3; border-radius: 7px; padding: 6px 12px; }"
        )
        stop_style = (
            "QPushButton {"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ff5f54, stop:1 #df3a30);"
            "color: white; font-weight: 700; border: 1px solid #b92f27; border-bottom: 3px solid #8f241d;"
            "border-radius: 7px; padding: 6px 12px; }"
            "QPushButton:pressed { border-bottom: 1px solid #8f241d; padding-top: 8px; padding-bottom: 4px; }"
            if stop_active else
            "QPushButton {"
            "background: #e6e8ea; color: #8b949e; font-weight: 700; border: 1px solid #c7ccd1;"
            "border-bottom: 2px solid #b6bcc3; border-radius: 7px; padding: 6px 12px; }"
        )
        self.btn_start.setStyleSheet(start_style)
        self.btn_stop.setStyleSheet(stop_style)
    
    def on_clear_all(self):
        """Handle clear all button"""
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Are you sure you want to clear all actions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.script_groups.clear()
            self._ensure_default_group()
            self._reset_action_counts()
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
                payload = self._serialize_grouped_script()
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
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
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._load_grouped_script_data(data)
                self._reset_action_counts()
                self.update_table()
                self.statusBar.showMessage(f"Script loaded: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load script: {e}")
    
    def on_start(self):
        """Handle start button"""
        runtime_script, key_map = self._build_runtime_script_and_key_map()
        if len(runtime_script.get_actions()) == 0:
            QMessageBox.warning(self, "Warning", "No actions to execute!")
            return

        if not self._ensure_target_selected():
            return
        
        self._apply_selected_target_to_actions()
        self._reset_action_counts()
        self._running_action_key_map = key_map
        self.update_table()
        
        self.auto_clicker.execute_script(runtime_script)
        self._update_run_button_states(True)
    
    def on_stop(self):
        """Handle stop button"""
        self.auto_clicker.stop()
        self._update_run_button_states(False)
    
    def toggle_auto_click(self):
        """Toggle auto click (END key)"""
        if self.auto_clicker.is_running:
            self.on_stop()
        else:
            if self._is_recording_active():
                self._finish_recording_for_quick_start()
            self.on_start()
    
    def on_delay_changed(self, value: int):
        """Handle delay changed"""
        self.auto_clicker.set_delay(value)
        self.config.set("click_delay_ms", value)
    
    def on_priority_cooldown_changed(self, value: int):
        """Handle priority cooldown changed"""
        self.auto_clicker.set_priority_cooldown(value)
        self.config.set("priority_cooldown_ms", value)

    def on_drag_mode_changed(self, index: int):
        """Handle drag mode changed."""
        mode = "hybrid"
        if int(index) == 1:
            mode = "background"
        elif int(index) == 2:
            mode = "real"
        self.auto_clicker.set_drag_mode(mode)
        self.config.set("drag_mode", mode)
    
    def on_hotkey_changed(self, logical_key: str, display_value: str):
        """Handle hotkey changed from settings."""
        if self._updating_table:
            return
        key_token = self._from_hotkey_display(display_value)
        if not key_token:
            return
        
        # Prevent duplicate bindings for these 3 actions.
        existing = {k: v for k, v in self.hotkey_bindings.items() if k != logical_key}
        if key_token in existing.values():
            self.statusBar.showMessage("Hotkey already in use by another function")
            # Restore previous selection
            self._updating_table = True
            try:
                combo = {
                    "page_up": self.hotkey_page_up_combo,
                    "page_down": self.hotkey_page_down_combo,
                    "end": self.hotkey_end_combo,
                }.get(logical_key)
                if combo:
                    combo.setCurrentText(self._to_hotkey_display(self.hotkey_bindings[logical_key]))
            finally:
                self._updating_table = False
            return
        
        self.hotkey_bindings[logical_key] = key_token
        self.config.set(f"hotkey_{logical_key}", key_token)
        if logical_key == "end":
            self.keyboard_listener.set_binding("end", key_token)
            self.btn_start.setText(f"Start ({self._to_hotkey_display(key_token)})")
            self.btn_stop.setText(f"Stop ({self._to_hotkey_display(key_token)})")
        self.statusBar.showMessage(f"Hotkey {logical_key} set to {self._to_hotkey_display(key_token)}")
    
    def on_status_changed(self, message: str):
        """Handle status changed"""
        self.statusBar.showMessage(message)
        if (not self.auto_clicker.is_running) and self.btn_stop.isEnabled():
            self._update_run_button_states(False)
    
    def _ensure_default_group(self):
        """Ensure at least one branch exists."""
        if not self.script_groups:
            self.script_groups.append({"name": "Branch 1", "enabled": True, "actions": []})
    
    def _get_selected_branch_index(self, require_selection: bool = False) -> int | None:
        """Resolve selected branch from current tree selection."""
        current_item = self.script_tree.currentItem()
        if current_item:
            payload = current_item.data(0, Qt.ItemDataRole.UserRole)
            if payload:
                if payload[0] == "group":
                    idx = int(payload[1])
                    if 0 <= idx < len(self.script_groups):
                        return idx
                elif payload[0] == "action":
                    idx = int(payload[1])
                    if 0 <= idx < len(self.script_groups):
                        return idx
        if self._last_selected_branch_index is not None:
            idx = int(self._last_selected_branch_index)
            if 0 <= idx < len(self.script_groups):
                return idx
        if require_selection:
            return None
        self._ensure_default_group()
        return 0
    
    def _add_action_to_selected_branch(self, action: ClickAction, branch_index: int | None = None):
        """Append a new action to selected branch."""
        if branch_index is None:
            branch_index = self._get_selected_branch_index()
        if branch_index is None:
            self._ensure_default_group()
            branch_index = 0
        if branch_index < 0 or branch_index >= len(self.script_groups):
            branch_index = 0
        
        actions = self.script_groups[int(branch_index)].setdefault("actions", [])
        actions.append({
            "name": f"Action {len(actions) + 1}",
            "enabled": True,
            "action": action
        })
    
    def _build_runtime_script_and_key_map(self):
        """Build executable flat script from checked branch/action entries."""
        script = ClickScript()
        key_map: list[tuple[int, int]] = []
        
        for group_index, group in enumerate(self.script_groups):
            if not group.get("enabled", True):
                continue
            for action_index, entry in enumerate(group.get("actions", [])):
                if not entry.get("enabled", True):
                    continue
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                script.add_action(action)
                key_map.append((group_index, action_index))
        return script, key_map
    
    def _serialize_grouped_script(self) -> dict:
        """Serialize grouped script structure to JSON payload."""
        groups = []
        for group in self.script_groups:
            group_payload = {
                "name": str(group.get("name", "Branch")),
                "enabled": bool(group.get("enabled", True)),
                "actions": []
            }
            for entry in group.get("actions", []):
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                group_payload["actions"].append({
                    "name": str(entry.get("name", "Action")),
                    "enabled": bool(entry.get("enabled", True)),
                    "action": action.to_dict()
                })
            groups.append(group_payload)
        return {"version": "2.0", "groups": groups}
    
    def _load_grouped_script_data(self, data: dict):
        """Load grouped script structure with backward compatibility."""
        loaded_groups: list[dict] = []
        
        if isinstance(data, dict) and isinstance(data.get("groups"), list):
            for group_data in data.get("groups", []):
                name = str(group_data.get("name", "Branch")).strip() or "Branch"
                enabled = bool(group_data.get("enabled", True))
                actions = []
                for entry in group_data.get("actions", []):
                    action_dict = entry.get("action")
                    if not action_dict:
                        continue
                    try:
                        action = ClickAction.from_dict(action_dict)
                    except Exception:
                        continue
                    actions.append({
                        "name": str(entry.get("name", f"Action {len(actions) + 1}")),
                        "enabled": bool(entry.get("enabled", True)),
                        "action": action
                    })
                loaded_groups.append({"name": name, "enabled": enabled, "actions": actions})
        else:
            # Legacy flat format.
            legacy = ClickScript.from_dict(data if isinstance(data, dict) else {})
            actions = [
                {"name": f"Action {idx + 1}", "enabled": True, "action": action}
                for idx, action in enumerate(legacy.get_actions())
            ]
            loaded_groups.append({"name": "Branch 1", "enabled": True, "actions": actions})
        
        self.script_groups = loaded_groups
        self._ensure_default_group()
    
    def _build_action_details(self, action: ClickAction) -> str:
        """Build details text for one action."""
        if action.type == ClickType.POSITION:
            x = action.data.get('x', 0)
            y = action.data.get('y', 0)
            mode_part = f" [{self._format_action_mode_label(action.data)}]"
            target_title = action.data.get('target_title', '')
            target_part = f" | Target: {target_title}" if target_title else ""
            return f"Position{mode_part}: ({x}, {y}){target_part}"
        
        if action.type == ClickType.IMAGE:
            image_path = action.data.get('image_path', '')
            offset_x = action.data.get('offset_x', 0)
            offset_y = action.data.get('offset_y', 0)
            mode_part = f" [{self._format_action_mode_label(action.data)}]"
            priority_level = int(action.data.get('priority_level', 0) or 0)
            priority_part = f" | Priority: P{priority_level}" if priority_level > 0 else ""
            target_title = action.data.get('target_title', '')
            target_part = f" | Target: {target_title}" if target_title else ""
            return (
                f"Image{mode_part}: {os.path.basename(image_path)} | Offset: ({offset_x}, {offset_y})"
                f"{priority_part}{target_part}"
            )
        
        image_path = action.data.get('image_path', '')
        mode_part = f" [{self._format_action_mode_label(action.data)}]"
        priority_level = int(action.data.get('priority_level', 0) or 0)
        priority_part = f" | Priority: P{priority_level}" if priority_level > 0 else ""
        target_title = action.data.get('target_title', '')
        target_part = f" | Target: {target_title}" if target_title else ""
        return f"Image Direct{mode_part}: {os.path.basename(image_path)}{priority_part}{target_part}"
    
    def _reset_action_counts(self):
        """Reset all action counts to zero."""
        self.action_counts = {}
        for group_index, group in enumerate(self.script_groups):
            for action_index, _ in enumerate(group.get("actions", [])):
                self.action_counts[(group_index, action_index)] = 0
    
    def _on_action_executed_from_worker(self, action_index: int):
        """Forward worker-thread callback to Qt main thread."""
        self.action_executed_signal.emit(int(action_index))
    
    def _on_action_executed_main_thread(self, action_index: int):
        """Increment and refresh one count cell in table."""
        if action_index < 0:
            return
        if action_index >= len(self._running_action_key_map):
            return
        
        key = self._running_action_key_map[action_index]
        self.action_counts[key] = int(self.action_counts.get(key, 0)) + 1
        item = self._tree_action_items.get(key)
        if not item:
            return
        
        self._updating_table = True
        try:
            item.setText(5, str(int(self.action_counts.get(key, 0))))
        finally:
            self._updating_table = False
    
    def _is_recording_active(self) -> bool:
        """Check whether any recording mode is active."""
        if self.position_recorder and self.position_recorder.is_recording:
            return True
        if self.image_recording_manager and self.image_recording_manager.is_recording:
            return True
        return False
    
    def _finish_recording_for_quick_start(self):
        """Finalize current recording before quick-start with END."""
        # Position recording: stop and persist recorded points.
        if self.position_recorder and self.position_recorder.is_recording:
            positions = list(self.position_recorder.positions)
            self.position_recorder.stop()
            self.on_position_recording_cancelled(positions)
        
        # Image recording: finish gracefully (equivalent to ESC flow).
        if self.image_recording_manager and self.image_recording_manager.is_recording:
            self.image_recording_manager.finish()
    
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
        
        for group in self.script_groups:
            for entry in group.get("actions", []):
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
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
                    drag_to_x = action.data.get("drag_to_x")
                    drag_to_y = action.data.get("drag_to_y")
                    drag_client_x = action.data.get("drag_client_x")
                    drag_client_y = action.data.get("drag_client_y")
                    if (
                        (drag_client_x is None or drag_client_y is None)
                        and drag_to_x is not None and drag_to_y is not None
                    ):
                        try:
                            dcx, dcy = win32gui.ScreenToClient(target_hwnd, (int(drag_to_x), int(drag_to_y)))
                            action.data["drag_client_x"] = int(dcx)
                            action.data["drag_client_y"] = int(dcy)
                        except Exception:
                            pass
                elif action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT):
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
                    drag_to_x = action.data.get("drag_to_x")
                    drag_to_y = action.data.get("drag_to_y")
                    drag_client_x = action.data.get("drag_client_x")
                    drag_client_y = action.data.get("drag_client_y")
                    if (
                        (drag_client_x is None or drag_client_y is None)
                        and drag_to_x is not None and drag_to_y is not None
                    ):
                        try:
                            dcx, dcy = win32gui.ScreenToClient(target_hwnd, (int(drag_to_x), int(drag_to_y)))
                            action.data["drag_client_x"] = int(dcx)
                            action.data["drag_client_y"] = int(dcy)
                        except Exception:
                            pass
    
    def _format_action_mode_label(self, data: dict) -> str:
        """Format user-facing action mode label for table details."""
        mode = str(data.get("action_mode", "mouse_click")).lower()
        button = str(data.get("mouse_button", "left")).lower()
        if mode == "mouse_click":
            return f"{button.upper()}"
        if mode == "mouse_hold":
            hold_ms = int(data.get("hold_ms", 1000) or 1000)
            return f"HOLD {button.upper()} {hold_ms}ms"
        if mode == "mouse_drag":
            drag_ms = int(data.get("drag_ms", 500) or 500)
            drag_to_x = data.get("drag_to_x")
            drag_to_y = data.get("drag_to_y")
            if drag_to_x is not None and drag_to_y is not None:
                return f"DRAG {button.upper()} -> ({int(drag_to_x)}, {int(drag_to_y)}) {drag_ms}ms"
            return f"DRAG {button.upper()} {drag_ms}ms"
        if mode == "key_press":
            return f"KEY {str(data.get('key_name', '')).upper()}"
        if mode == "hotkey":
            keys = data.get("hotkey_keys") or []
            return "HOTKEY " + "+".join(str(k).upper() for k in keys)
        if mode == "key_hold":
            hold_ms = int(data.get("hold_ms", 1000) or 1000)
            key_name = str(data.get("key_name", "")).upper()
            return f"HOLD KEY (REPEAT) {key_name} {hold_ms}ms"
        if mode == "key_hold_true":
            hold_ms = int(data.get("hold_ms", 1000) or 1000)
            key_name = str(data.get("key_name", "")).upper()
            return f"HOLD KEY (TRUE) {key_name} {hold_ms}ms"
        return button.upper()
    
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
