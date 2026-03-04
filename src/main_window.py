"""
Main GUI for ITM AutoClicker
"""
import sys
import os
import json
import uuid
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget,
    QLabel, QSpinBox, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QRadioButton, QButtonGroup, QStatusBar, QFormLayout,
    QComboBox, QTreeWidget, QTreeWidgetItem, QInputDialog, QToolButton, QCheckBox, QMenu, QApplication, QLineEdit,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon, QCursor, QColor, QBrush
from src.click_script import ClickScript, ClickAction, ClickType
from src.config import Config
from src.auto_clicker import AutoClicker
from src.keyboard_listener import KeyboardListener
from src.image_recording_manager import ImageRecordingManager
from src.window_picker import WindowPickerDialog, Window, WindowPicker
from src.action_options import choose_advanced_action, choose_advanced_action_by_choice
from src.ui.dialogs import SettingsDialog
from src.ui.recorders import PositionRecorder, ImageRecorder
from src.ui.widgets import ScriptTreeWidget, DragCreateToolButton, DragSelectTargetButton
from src.screen_action_recorder import ScreenActionRecorder
from pynput import mouse
import win32gui
import win32con


class MainWindow(QMainWindow):
    """Main application window"""
    action_executed_signal = pyqtSignal(int)
    action_detail_changed_signal = pyqtSignal(int, str)
    status_changed_signal = pyqtSignal(str)
    
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
            self.config.get("drag_mode", "hybrid"),
            self.config.get("use_real_mouse", False),
            self.config.get("image_confidence", 0.8),
            self.config.get("ocr_language", "eng+vie")
        )
        self.auto_clicker.set_on_status_changed(self._on_status_changed_from_worker)
        self.auto_clicker.set_on_action_executed(self._on_action_executed_from_worker)
        self.auto_clicker.set_on_action_detail_changed(self._on_action_detail_changed_from_worker)
        self.hotkey_bindings = self._load_hotkey_bindings()
        
        # Initialize keyboard listener for Start/Pause/Resume and Stop
        self.keyboard_listener = KeyboardListener()
        self.keyboard_listener.set_binding('home', self.hotkey_bindings['home'])
        self.keyboard_listener.set_binding('end', self.hotkey_bindings['end'])
        self.keyboard_listener.set_binding('f10', self.hotkey_bindings['record'])
        self.keyboard_listener.register_callback('home', self.on_home_hotkey_pressed)
        self.keyboard_listener.register_callback('end', self.on_end_hotkey_pressed)
        self.keyboard_listener.register_callback('f10', self.on_screen_record_hotkey_pressed)
        
        # Grouped scripts (branches)
        self.script_groups: list[dict] = []
        self.action_counts: dict[tuple[int, int], int] = {}
        self._tree_action_items: dict[tuple[int, int], QTreeWidgetItem] = {}
        self._running_action_key_map: list[tuple[int, int]] = []
        self._highlighted_action_key: tuple[int, int] | None = None
        
        # Recorders
        self.position_recorder = None
        self.image_recorder = None
        self.image_recording_manager = None
        self.pending_image_action_type = ClickType.IMAGE
        self.pending_branch_index: int | None = None
        self._active_action_tool_button: QToolButton | None = None
        self._action_tool_buttons: list[QToolButton] = []
        self._advanced_action_toolbar_widget: QWidget | None = None
        self._last_selected_branch_index: int | None = None
        self.selected_target_window: Window | None = None
        self.target_info_label = None
        self.target_x_spin: QSpinBox | None = None
        self.target_y_spin: QSpinBox | None = None
        self.target_w_spin: QSpinBox | None = None
        self.target_h_spin: QSpinBox | None = None
        self.btn_speed_up: QPushButton | None = None
        self.btn_speed_down: QPushButton | None = None
        self._updating_table = False
        self.screen_action_recorder: ScreenActionRecorder | None = None
        self._screen_record_armed = False
        self._screen_recording_active = False
        self._screen_record_target_branch_index: int | None = None
        self._screen_record_elapsed_timer = QTimer(self)
        self._screen_record_elapsed_timer.setInterval(200)
        self._screen_record_elapsed_timer.timeout.connect(self._on_screen_record_elapsed_tick)
        self._screen_record_restore_states: dict = {}
        self.action_executed_signal.connect(self._on_action_executed_main_thread)
        self.action_detail_changed_signal.connect(self._on_action_detail_changed_main_thread)
        self.status_changed_signal.connect(self.on_status_changed)
        self._ensure_default_group()
        self._always_on_top_enabled = bool(self.config.get("always_on_top", False))
        
        # Setup UI
        self.setup_ui()
        self._apply_always_on_top_to_main()
        self.keyboard_listener.start()
        
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
        self.btn_select_target = DragSelectTargetButton()
        self.btn_select_target.setText("Select Target")
        self.btn_select_target.clicked.connect(self.on_select_target_window)
        self.btn_select_target.target_dropped.connect(self.on_select_target_window_dropped)
        self.btn_select_target.setToolTip("Choose the target window for recording and execution.")
        drag_cursor_pm = self._icons.get("mouse_on_drag")
        if isinstance(drag_cursor_pm, QPixmap) and not drag_cursor_pm.isNull():
            scaled_cursor = drag_cursor_pm.scaled(
                36,
                36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            hot_x = max(0, int(scaled_cursor.width() / 2))
            hot_y = max(0, int(scaled_cursor.height() / 2))
            self.btn_select_target.set_drag_cursor_pixmap(scaled_cursor, hot_x=hot_x, hot_y=hot_y)
        self.btn_load_top = QPushButton("Load Script")
        self.btn_load_top.clicked.connect(self.on_load_script)
        self.btn_load_top.setToolTip("Load script from JSON file.")
        self.btn_save_top = QPushButton("Save Script")
        self.btn_save_top.clicked.connect(self.on_save_script)
        self.btn_save_top.setToolTip("Save current script list to JSON file.")
        target_layout.addWidget(target_title)
        target_layout.addWidget(self.target_info_label)
        target_layout.addStretch()
        target_layout.addWidget(self.btn_load_top)
        target_layout.addWidget(self.btn_save_top)
        target_layout.addWidget(self.btn_select_target)
        layout.addLayout(target_layout)

        # Target geometry controls
        target_geo_layout = QHBoxLayout()
        target_geo_layout.addWidget(QLabel("X:"))
        self.target_x_spin = QSpinBox()
        self.target_x_spin.setRange(-10000, 10000)
        self.target_x_spin.setToolTip("Target window left position")
        target_geo_layout.addWidget(self.target_x_spin)

        target_geo_layout.addWidget(QLabel("Y:"))
        self.target_y_spin = QSpinBox()
        self.target_y_spin.setRange(-10000, 10000)
        self.target_y_spin.setToolTip("Target window top position")
        target_geo_layout.addWidget(self.target_y_spin)

        target_geo_layout.addWidget(QLabel("W:"))
        self.target_w_spin = QSpinBox()
        self.target_w_spin.setRange(100, 10000)
        self.target_w_spin.setToolTip("Target window width")
        target_geo_layout.addWidget(self.target_w_spin)

        target_geo_layout.addWidget(QLabel("H:"))
        self.target_h_spin = QSpinBox()
        self.target_h_spin.setRange(100, 10000)
        self.target_h_spin.setToolTip("Target window height")
        target_geo_layout.addWidget(self.target_h_spin)

        self.btn_refresh_target_rect = QPushButton("Refresh Rect")
        self.btn_refresh_target_rect.clicked.connect(self.on_refresh_target_geometry)
        self.btn_refresh_target_rect.setToolTip("Read current target window position/size into X/Y/W/H fields.")
        target_geo_layout.addWidget(self.btn_refresh_target_rect)

        self.btn_fix_target_rect = QPushButton("Fix")
        self.btn_fix_target_rect.clicked.connect(self.on_fix_target_geometry)
        self.btn_fix_target_rect.setToolTip("Apply X/Y/W/H fields to target window.")
        target_geo_layout.addWidget(self.btn_fix_target_rect)
        target_geo_layout.addStretch()
        layout.addLayout(target_geo_layout)
        
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
        self.btn_tool_position.setText("Record multi Action")
        self.btn_tool_position.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_position.setCheckable(True)
        self.btn_tool_position.setMinimumWidth(110)
        self.btn_tool_position.setMinimumHeight(56)
        self.btn_tool_position.setToolTip(
            "Record POSITION actions.\n"
            "Use Page Up for left click, Page Down for advanced actions.\n"
            "Press ESC to finish recording."
        )
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
        self.btn_tool_image.setToolTip(
            "Record IMAGE-based actions.\n"
            "Program detects image, then performs action at recorded click position."
        )
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
        self.btn_tool_image_direct.setToolTip(
            "Record IMAGE DIRECT actions.\n"
            "Program detects image, then clicks directly on image match location."
        )
        if self._icons.get("image_direct") and not self._icons.get("image_direct").isNull():
            self.btn_tool_image_direct.setIcon(self._icons.get("image_direct"))
            self.btn_tool_image_direct.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_image_direct.clicked.connect(
            lambda: self.on_toolbar_add_action(ClickType.IMAGE_DIRECT, self.btn_tool_image_direct)
        )
        action_toolbar.addWidget(self.btn_tool_image_direct)

        self.btn_tool_record_screen = QToolButton()
        self.btn_tool_record_screen.setText("Record screen action")
        self.btn_tool_record_screen.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_record_screen.setCheckable(True)
        self.btn_tool_record_screen.setMinimumWidth(128)
        self.btn_tool_record_screen.setMinimumHeight(56)
        self.btn_tool_record_screen.setToolTip("")
        if self._icons.get("record_screen") and not self._icons.get("record_screen").isNull():
            self.btn_tool_record_screen.setIcon(self._icons.get("record_screen"))
            self.btn_tool_record_screen.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_record_screen.clicked.connect(self.on_record_screen_action_clicked)
        action_toolbar.addWidget(self.btn_tool_record_screen)

        self.btn_tool_image_recognition = QToolButton()
        self.btn_tool_image_recognition.setText("Image Recognition")
        self.btn_tool_image_recognition.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_tool_image_recognition.setCheckable(True)
        self.btn_tool_image_recognition.setMinimumWidth(128)
        self.btn_tool_image_recognition.setMinimumHeight(56)
        self.btn_tool_image_recognition.setToolTip(
            "Record IMAGE RECOGNITION action.\n"
            "Program detects the selected image area and reads text value from it."
        )
        if self._icons.get("image_recognition") and not self._icons.get("image_recognition").isNull():
            self.btn_tool_image_recognition.setIcon(self._icons.get("image_recognition"))
            self.btn_tool_image_recognition.setIconSize(QPixmap(40, 40).size())
        self.btn_tool_image_recognition.clicked.connect(
            lambda: self.on_toolbar_add_action(ClickType.IMAGE_RECOGNITION, self.btn_tool_image_recognition)
        )
        action_toolbar.addWidget(self.btn_tool_image_recognition)

        self._action_tool_buttons = [
            self.btn_tool_position,
            self.btn_tool_image,
            self.btn_tool_image_direct,
            self.btn_tool_record_screen,
            self.btn_tool_image_recognition,
        ]
        self._update_record_hotkey_ui()
        self._apply_action_toolbar_button_style()

        action_toolbar.addStretch()

        # Start/Stop buttons moved next to action toolbar (right side)
        self.btn_start = QPushButton(f"Start ({self._to_hotkey_display(self.hotkey_bindings['home'])})")
        self.btn_start.clicked.connect(self.on_start_pause_resume)
        self.btn_start.setMinimumWidth(130)
        self.btn_start.setMinimumHeight(65)
        self.btn_start.setToolTip("Start/Pause/Resume checked actions. Hotkey: Home (or your custom key).")
        action_toolbar.addWidget(self.btn_start)

        speed_layout = QVBoxLayout()
        speed_layout.setSpacing(3)
        self.btn_speed_up = QPushButton("")
        self.btn_speed_up.setFixedWidth(max(40, int(self.btn_start.minimumWidth() / 3)))
        self.btn_speed_up.setFixedHeight(31)
        self.btn_speed_up.setToolTip("Speed up: reduce delay of all checked actions")
        speed_up_icon = self._icons.get("speed_up")
        if speed_up_icon and not speed_up_icon.isNull():
            self.btn_speed_up.setIcon(speed_up_icon)
            self.btn_speed_up.setIconSize(QPixmap(18, 18).size())
        self.btn_speed_up.clicked.connect(self.on_speed_up_clicked)
        speed_layout.addWidget(self.btn_speed_up)

        self.btn_speed_down = QPushButton("")
        self.btn_speed_down.setFixedWidth(max(40, int(self.btn_start.minimumWidth() / 3)))
        self.btn_speed_down.setFixedHeight(31)
        self.btn_speed_down.setToolTip("Slow down: increase delay of all checked actions")
        speed_down_icon = self._icons.get("speed_down")
        if speed_down_icon and not speed_down_icon.isNull():
            self.btn_speed_down.setIcon(speed_down_icon)
            self.btn_speed_down.setIconSize(QPixmap(18, 18).size())
        self.btn_speed_down.clicked.connect(self.on_speed_down_clicked)
        speed_layout.addWidget(self.btn_speed_down)
        action_toolbar.addLayout(speed_layout)

        self.btn_stop = QPushButton(f"Stop ({self._to_hotkey_display(self.hotkey_bindings['end'])})")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setMinimumWidth(130)
        self.btn_stop.setMinimumHeight(65)
        self.btn_stop.setToolTip("Stop execution immediately. Hotkey: End (or your custom key).")
        action_toolbar.addWidget(self.btn_stop)
        self._update_run_button_states(False)
        layout.addLayout(action_toolbar)

        # Advanced action toolbar (equivalent quick actions for PAGE DOWN menu)
        self._advanced_action_toolbar_widget = QWidget()
        adv_toolbar = QHBoxLayout()
        self._advanced_action_toolbar_widget.setLayout(adv_toolbar)
        adv_toolbar.setSpacing(4)
        toolbar_h = max(28, int(self.btn_tool_position.minimumHeight() * 1.2))
        icon_size = max(14, int(toolbar_h * 0.8))
        self._advanced_toolbar_buttons = []
        quick_actions = [
            ("Left Click", "adv_left_click", "Left Click"),
            ("Right Click", "adv_right_click", "Right Click"),
            ("Middle Click", "adv_middle_click", "Middle Click"),
            ("Scroll Up", "adv_scroll_up", "Scroll Up"),
            ("Scroll Down", "adv_scroll_down", "Scroll Down"),
            ("Mouse Hold Left", "adv_mouse_hold_left", "Mouse Hold Left"),
            ("Mouse Hold Right", "adv_mouse_hold_right", "Mouse Hold Right"),
            ("Drag Drop", "adv_drag_left", "Drag Drop"),
            ("Key Press", "adv_key_press", "Key Press"),
            ("Hotkey", "adv_hotkey", "Hotkey"),
            ("Key Hold (Repeat)", "adv_key_hold_repeat", "Key Hold (Repeat)"),
        ]
        for choice_name, icon_key, tooltip_text in quick_actions:
            btn = DragCreateToolButton(choice_name)
            btn.setToolTip(f"{tooltip_text}: drag and drop to create action at drop position.")
            btn.setAutoRaise(False)
            btn.setFixedHeight(toolbar_h)
            btn.setFixedWidth(toolbar_h + 8)
            icon = self._icons.get(icon_key)
            if icon and not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QPixmap(icon_size, icon_size).size())
            drag_cursor_pm = self._icons.get("mouse_on_drag")
            if isinstance(drag_cursor_pm, QPixmap) and not drag_cursor_pm.isNull():
                scaled_cursor = drag_cursor_pm.scaled(
                    max(18, int(toolbar_h * 0.85)),
                    max(18, int(toolbar_h * 0.85)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                hot_x = max(0, int(scaled_cursor.width() / 2))
                hot_y = max(0, int(scaled_cursor.height() / 2))
                btn.set_drag_cursor_pixmap(scaled_cursor, hot_x=hot_x, hot_y=hot_y)
            btn.action_dropped.connect(self.on_advanced_toolbar_drop)
            adv_toolbar.addWidget(btn)
            self._advanced_toolbar_buttons.append(btn)
        adv_toolbar.addStretch()
        layout.addWidget(self._advanced_action_toolbar_widget)
        
        # Tree list for script branches/actions
        self.script_tree = ScriptTreeWidget()
        self.script_tree.setColumnCount(8)
        self.script_tree.setHeaderLabels(["Click Script List", "Type", "Image", "Priority", "Delay (ms)", "Limit", "Count", "Details"])
        self.script_tree.setColumnWidth(0, 220)
        self.script_tree.setColumnWidth(1, 110)
        self.script_tree.setColumnWidth(2, 110)
        self.script_tree.setColumnWidth(3, 90)
        self.script_tree.setColumnWidth(4, 90)
        self.script_tree.setColumnWidth(5, 90)
        self.script_tree.setColumnWidth(6, 80)
        self.script_tree.setColumnWidth(7, 340)
        self.script_tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.script_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.script_tree.setDragEnabled(True)
        self.script_tree.viewport().setAcceptDrops(True)
        self.script_tree.setAcceptDrops(True)
        self.script_tree.setDropIndicatorShown(True)
        self.script_tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.script_tree.itemChanged.connect(self.on_script_tree_item_changed)
        self.script_tree.itemDoubleClicked.connect(self.on_script_tree_item_double_clicked)
        self.script_tree.currentItemChanged.connect(self.on_script_tree_current_item_changed)
        self.script_tree.order_changed.connect(self.on_script_tree_order_changed)
        self.script_tree.replace_action_requested.connect(self.on_replace_action_requested)
        self.script_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.script_tree.customContextMenuRequested.connect(self.on_script_tree_context_menu_requested)
        layout.addWidget(self.script_tree)
        
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

        speed_step_layout = QHBoxLayout()
        speed_step_label = QLabel("Speed Adjust Step (ms):")
        self.speed_step_spinbox = QSpinBox()
        self.speed_step_spinbox.setMinimum(1)
        self.speed_step_spinbox.setMaximum(10000)
        self.speed_step_spinbox.setValue(int(self.config.get("speed_adjust_step_ms", 100)))
        self.speed_step_spinbox.valueChanged.connect(self.on_speed_step_changed)
        self.speed_step_spinbox.setToolTip(
            "Amount of delay changed by Speed Up / Slow Down buttons."
        )
        speed_step_layout.addWidget(speed_step_label)
        speed_step_layout.addWidget(self.speed_step_spinbox)
        speed_step_layout.addStretch()
        layout.addLayout(speed_step_layout)
        
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

        # OCR language
        ocr_layout = QHBoxLayout()
        ocr_label = QLabel("OCR Language:")
        self.ocr_language_combo = QComboBox()
        self.ocr_language_combo.addItem("English + Vietnamese (eng+vie)", "eng+vie")
        self.ocr_language_combo.addItem("Vietnamese (vie)", "vie")
        self.ocr_language_combo.addItem("English (eng)", "eng")
        current_ocr_lang = str(self.config.get("ocr_language", "eng+vie") or "eng+vie").strip().lower()
        ocr_index = self.ocr_language_combo.findData(current_ocr_lang)
        if ocr_index < 0:
            self.ocr_language_combo.addItem(f"Custom ({current_ocr_lang})", current_ocr_lang)
            ocr_index = self.ocr_language_combo.findData(current_ocr_lang)
        self.ocr_language_combo.setCurrentIndex(max(0, ocr_index))
        self.ocr_language_combo.currentIndexChanged.connect(self.on_ocr_language_changed)
        self.ocr_language_combo.setToolTip(
            "Tesseract language code used by Image Recognition.\n"
            "For Vietnamese, make sure vie.traineddata exists in tessdata."
        )
        ocr_layout.addWidget(ocr_label)
        ocr_layout.addWidget(self.ocr_language_combo)
        ocr_layout.addStretch()
        layout.addLayout(ocr_layout)
        
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

        # Mouse control mode
        mouse_mode_layout = QHBoxLayout()
        self.real_mouse_checkbox = QCheckBox("Use real mouse for all actions (occupy mouse)")
        self.real_mouse_checkbox.setChecked(bool(self.config.get("use_real_mouse", False)))
        self.real_mouse_checkbox.toggled.connect(self.on_use_real_mouse_changed)
        self.real_mouse_checkbox.setToolTip(
            "When enabled, all mouse actions use real cursor input.\n"
            "Best compatibility for apps that ignore background input,\n"
            "but it will occupy your mouse during execution."
        )
        mouse_mode_layout.addWidget(self.real_mouse_checkbox)
        mouse_mode_layout.addStretch()
        layout.addLayout(mouse_mode_layout)

        # Always-on-top mode
        ontop_layout = QHBoxLayout()
        self.always_on_top_checkbox = QCheckBox("Always on top")
        self.always_on_top_checkbox.setChecked(bool(self._always_on_top_enabled))
        self.always_on_top_checkbox.toggled.connect(self.on_always_on_top_changed)
        self.always_on_top_checkbox.setToolTip(
            "Keep main window and child dialogs above other windows."
        )
        ontop_layout.addWidget(self.always_on_top_checkbox)
        ontop_layout.addStretch()
        layout.addLayout(ontop_layout)
        
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
        
        hk_home_layout = QHBoxLayout()
        hk_home_label = QLabel("Start/Pause/Resume (HOME):")
        self.hotkey_home_combo = QComboBox()
        self.hotkey_home_combo.addItems(self.hotkey_options)
        home_text = self._to_hotkey_display(self.hotkey_bindings["home"])
        if self.hotkey_home_combo.findText(home_text) < 0:
            self.hotkey_home_combo.addItem(home_text)
        self.hotkey_home_combo.setCurrentText(home_text)
        self.hotkey_home_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("home", text)
        )
        hk_home_layout.addWidget(hk_home_label)
        hk_home_layout.addWidget(self.hotkey_home_combo)
        hk_home_layout.addStretch()
        layout.addLayout(hk_home_layout)

        hk_stop_layout = QHBoxLayout()
        hk_stop_label = QLabel("Stop (END):")
        self.hotkey_end_combo = QComboBox()
        self.hotkey_end_combo.addItems(self.hotkey_options)
        end_text = self._to_hotkey_display(self.hotkey_bindings["end"])
        if self.hotkey_end_combo.findText(end_text) < 0:
            self.hotkey_end_combo.addItem(end_text)
        self.hotkey_end_combo.setCurrentText(end_text)
        self.hotkey_end_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("end", text)
        )
        hk_stop_layout.addWidget(hk_stop_label)
        hk_stop_layout.addWidget(self.hotkey_end_combo)
        hk_stop_layout.addStretch()
        layout.addLayout(hk_stop_layout)

        hk_record_layout = QHBoxLayout()
        hk_record_label = QLabel("Record Screen Toggle:")
        self.hotkey_record_combo = QComboBox()
        self.hotkey_record_combo.addItems(self.hotkey_options)
        record_text = self._to_hotkey_display(self.hotkey_bindings["record"])
        if self.hotkey_record_combo.findText(record_text) < 0:
            self.hotkey_record_combo.addItem(record_text)
        self.hotkey_record_combo.setCurrentText(record_text)
        self.hotkey_record_combo.currentTextChanged.connect(
            lambda text: self.on_hotkey_changed("record", text)
        )
        hk_record_layout.addWidget(hk_record_label)
        hk_record_layout.addWidget(self.hotkey_record_combo)
        hk_record_layout.addStretch()
        layout.addLayout(hk_record_layout)
        
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
                group_item.setText(7, f"{len(group.get('actions', []))} action(s)")
                group_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsDragEnabled
                    | Qt.ItemFlag.ItemIsDropEnabled
                )
                group_item.setCheckState(
                    0,
                    Qt.CheckState.Checked if group.get("enabled", True) else Qt.CheckState.Unchecked
                )
                group_item.setData(0, Qt.ItemDataRole.UserRole, ("group", group_index))

                actions = group.get("actions", [])
                for entry in actions:
                    if not entry.get("id"):
                        entry["id"] = uuid.uuid4().hex

                action_children: dict[str | None, list[int]] = {}
                for action_index, entry in enumerate(actions):
                    parent_id = entry.get("parent_id")
                    if not parent_id or not any(x.get("id") == parent_id for x in actions):
                        parent_id = None
                        entry["parent_id"] = None
                    action_children.setdefault(parent_id, []).append(action_index)

                visited = set()

                def add_action_node(action_index: int, parent_tree_item):
                    if action_index in visited:
                        return
                    visited.add(action_index)
                    entry = actions[action_index]
                    if "max_executions" not in entry:
                        entry["max_executions"] = None
                    action = entry.get("action")
                    if not isinstance(action, ClickAction):
                        return

                    key = (group_index, action_index)
                    action_item = QTreeWidgetItem(parent_tree_item)
                    action_item.setData(0, Qt.ItemDataRole.UserRole, ("action", group_index, action_index))
                    action_item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                        | Qt.ItemFlag.ItemIsDragEnabled
                        | Qt.ItemFlag.ItemIsDropEnabled
                    )
                    action_item.setCheckState(
                        0,
                        Qt.CheckState.Checked if entry.get("enabled", True) else Qt.CheckState.Unchecked
                    )
                    action_item.setText(0, str(entry.get("name", f"Action {action_index + 1}")))
                    self._apply_action_icon(action_item, action)
                    if action.type == ClickType.IF:
                        mode = str(action.data.get("if_mode", "if")).strip().lower()
                        action_item.setText(1, "IF NOT" if mode == "if_not" else "IF")
                    elif action.type == ClickType.IMAGE_RECOGNITION:
                        action_item.setText(1, "IMAGE RECOG")
                    else:
                        action_item.setText(1, action.type.value.upper())

                    preview_label = QLabel("-")
                    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    if action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IMAGE_RECOGNITION):
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
                    elif action.type == ClickType.IF:
                        preview_label.setText(str(action.data.get("source_action_name", "-")))
                    self.script_tree.setItemWidget(action_item, 2, preview_label)

                    if action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IF):
                        priority_combo = self._create_priority_combo(group_index, action_index, action)
                        self.script_tree.setItemWidget(action_item, 3, priority_combo)
                    else:
                        action_item.setText(3, "-")

                    delay_ms = int(action.data.get("delay_ms", self.config.get("click_delay_ms", 100)) or 0)
                    delay_spin = QSpinBox()
                    delay_spin.setMinimum(0)
                    delay_spin.setMaximum(600000)
                    delay_spin.setValue(delay_ms)
                    delay_spin.valueChanged.connect(
                        lambda value, g=group_index, a=action_index: self._on_delay_spin_changed(g, a, value)
                    )
                    self.script_tree.setItemWidget(action_item, 4, delay_spin)

                    limit_spin = QSpinBox()
                    limit_spin.setMinimum(0)
                    limit_spin.setMaximum(1000000)
                    limit_spin.setSpecialValueText("Unlimited")
                    max_exec = entry.get("max_executions")
                    if max_exec is None:
                        limit_spin.setValue(0)
                    else:
                        limit_spin.setValue(max(1, int(max_exec)))
                    limit_spin.valueChanged.connect(
                        lambda value, g=group_index, a=action_index: self._on_limit_spin_changed(g, a, value)
                    )
                    self.script_tree.setItemWidget(action_item, 5, limit_spin)

                    action_item.setText(6, str(int(self.action_counts.get(key, 0))))
                    action_item.setTextAlignment(6, Qt.AlignmentFlag.AlignCenter)
                    action_item.setText(7, self._build_action_details(action))
                    self._tree_action_items[key] = action_item

                    for child_index in action_children.get(entry.get("id"), []):
                        add_action_node(child_index, action_item)

                for root_index in action_children.get(None, []):
                    add_action_node(root_index, group_item)
                for fallback_index in range(len(actions)):
                    add_action_node(fallback_index, group_item)
                
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

            if self._highlighted_action_key is not None:
                hi_item = self._tree_action_items.get(self._highlighted_action_key)
                if hi_item:
                    self._set_action_item_highlight(hi_item, True)
                else:
                    self._highlighted_action_key = None
        finally:
            self._updating_table = False
    
    def on_add_action(self):
        """Handle add action button"""
        dialog = SettingsDialog(self)
        self._apply_always_on_top_to_dialog(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._start_add_action_flow(dialog.get_selected_type())

    def on_toolbar_add_action(self, click_type: ClickType, source_button: QToolButton):
        """Handle toolbar quick-add action buttons."""
        if self._screen_recording_active:
            self.statusBar.showMessage("Screen recording is active. Press F10 to stop first.")
            source_button.setChecked(False)
            return
        if self._screen_record_armed:
            self._screen_record_armed = False
            self.btn_tool_record_screen.setChecked(False)
            self.statusBar.showMessage("Record Screen Action canceled")

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
        if self._screen_recording_active:
            self._stop_screen_recording()
            return
        if self._screen_record_armed:
            self._screen_record_armed = False
            self._screen_record_target_branch_index = None
            self.btn_tool_record_screen.setChecked(False)
            self.statusBar.showMessage("Record Screen Action canceled")
            return
        # Position recording: stop and persist current recorded points (ESC behavior).
        if self.position_recorder and self.position_recorder.is_recording:
            positions = list(self.position_recorder.positions)
            self.position_recorder.stop()
            self.on_position_recording_cancelled(positions)
            return
        
        # Image recording: finish gracefully (ESC behavior).
        if self.image_recording_manager and self.image_recording_manager.is_recording:
            self.image_recording_manager.finish()

    def on_record_screen_action_clicked(self):
        """Arm Record Screen mode, then use F10 to start/stop."""
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Stop auto click before recording screen actions")
            self.btn_tool_record_screen.setChecked(False)
            return

        if self._screen_record_armed and not self._screen_recording_active:
            self._screen_record_armed = False
            self._screen_record_target_branch_index = None
            self.btn_tool_record_screen.setChecked(False)
            self.statusBar.showMessage("Record Screen Action canceled")
            return

        if self._screen_recording_active:
            self.statusBar.showMessage("Screen recording is running. Press F10 to stop.")
            self.btn_tool_record_screen.setChecked(True)
            return

        if self._is_recording_active():
            self._cancel_recording_for_action_switch()

        if not self._ensure_target_selected():
            self.btn_tool_record_screen.setChecked(False)
            return

        branch_index = self._get_selected_branch_index(require_selection=True)
        if branch_index is None:
            QMessageBox.information(
                self,
                "Select Branch",
                "Please select a branch in Click Script List before recording screen actions."
            )
            self.statusBar.showMessage("Select a branch first, then use Record screen action")
            self.btn_tool_record_screen.setChecked(False)
            return

        self._screen_record_target_branch_index = int(branch_index)
        self._screen_record_armed = True
        self.btn_tool_record_screen.setChecked(True)
        QMessageBox.information(
            self,
            "Record Screen Action",
            f"Press {self._to_hotkey_display(self.hotkey_bindings['record'])} to start recording.\n"
            f"Press {self._to_hotkey_display(self.hotkey_bindings['record'])} again to stop recording."
        )
        self.statusBar.showMessage(
            f"Record Screen armed: press {self._to_hotkey_display(self.hotkey_bindings['record'])} to start"
        )

    def on_screen_record_hotkey_pressed(self):
        """Handle global F10 toggle for screen recording."""
        if not self._screen_record_armed and not self._screen_recording_active:
            return
        if self._screen_recording_active:
            self._stop_screen_recording()
        else:
            self._start_screen_recording()

    def _start_screen_recording(self):
        """Start screen action recording."""
        if self._screen_recording_active:
            return
        if not self._screen_record_armed:
            return
        if self._screen_record_target_branch_index is None:
            self._screen_record_target_branch_index = self._get_selected_branch_index(require_selection=True)
            if self._screen_record_target_branch_index is None:
                self._screen_record_armed = False
                self.btn_tool_record_screen.setChecked(False)
                self.statusBar.showMessage("No branch selected for recording")
                return

        if not self._ensure_target_selected():
            self._screen_record_armed = False
            self.btn_tool_record_screen.setChecked(False)
            return

        try:
            self.screen_action_recorder = ScreenActionRecorder()
            self.screen_action_recorder.start()
            self._screen_recording_active = True
            self._set_screen_recording_controls_locked(True)
            self._set_status_recording_style(True)
            self._screen_record_elapsed_timer.start()
            self._update_screen_record_status()
        except Exception as e:
            self.screen_action_recorder = None
            self._screen_recording_active = False
            self._screen_record_armed = False
            self.btn_tool_record_screen.setChecked(False)
            QMessageBox.warning(self, "Record Screen Action", f"Cannot start recording:\n{e}")

    def _stop_screen_recording(self):
        """Stop screen action recording and append recorded actions."""
        recorded_actions = []
        if self.screen_action_recorder:
            try:
                recorded_actions = self.screen_action_recorder.stop()
            except Exception:
                recorded_actions = []
        self.screen_action_recorder = None
        self._screen_recording_active = False
        self._screen_record_armed = False
        self._screen_record_elapsed_timer.stop()
        self._set_status_recording_style(False)
        self.btn_tool_record_screen.setChecked(False)
        self._set_screen_recording_controls_locked(False)

        branch_index = self._screen_record_target_branch_index
        self._screen_record_target_branch_index = None
        if not recorded_actions:
            self.statusBar.showMessage("Screen recording stopped: no action captured")
            return
        if branch_index is None:
            branch_index = self._get_selected_branch_index(require_selection=False)

        target_hwnd = int(self.selected_target_window.hwnd) if self.selected_target_window else None
        target_title = self.selected_target_window.title if self.selected_target_window else ""
        added_count = 0
        for payload in recorded_actions:
            try:
                action_data = dict(payload)
                x = int(action_data.get("x", 0))
                y = int(action_data.get("y", 0))
                if target_hwnd is not None:
                    action_data["target_hwnd"] = int(target_hwnd)
                    action_data["target_title"] = str(target_title)
                    try:
                        cx, cy = win32gui.ScreenToClient(int(target_hwnd), (int(x), int(y)))
                        action_data["client_x"] = int(cx)
                        action_data["client_y"] = int(cy)
                    except Exception:
                        pass
                    if action_data.get("drag_to_x") is not None and action_data.get("drag_to_y") is not None:
                        try:
                            dcx, dcy = win32gui.ScreenToClient(
                                int(target_hwnd),
                                (int(action_data.get("drag_to_x")), int(action_data.get("drag_to_y")))
                            )
                            action_data["drag_client_x"] = int(dcx)
                            action_data["drag_client_y"] = int(dcy)
                        except Exception:
                            pass

                action = ClickAction(ClickType.POSITION, **action_data)
                self._add_action_to_selected_branch(action, branch_index)
                added_count += 1
            except Exception:
                continue

        self.update_table()
        self.statusBar.showMessage(f"Screen recording stopped: added {added_count} action(s)")

    def _set_screen_recording_controls_locked(self, locked: bool):
        """Disable all controls except Record Screen button while recording."""
        controls = [
            self.btn_select_target,
            self.btn_load_top,
            self.btn_save_top,
            self.btn_refresh_target_rect,
            self.btn_fix_target_rect,
            self.btn_tool_position,
            self.btn_tool_image,
            self.btn_tool_image_direct,
            self.btn_tool_image_recognition,
            self.btn_start,
            self.btn_stop,
            self.btn_speed_up,
            self.btn_speed_down,
            self.script_tree,
            self.target_x_spin,
            self.target_y_spin,
            self.target_w_spin,
            self.target_h_spin,
        ]
        controls.extend(list(self._advanced_toolbar_buttons))
        if locked:
            self._screen_record_restore_states = {}
            for widget in controls:
                if widget is None:
                    continue
                self._screen_record_restore_states[widget] = bool(widget.isEnabled())
                widget.setEnabled(False)
            self.btn_tool_record_screen.setEnabled(True)
            self.btn_tool_record_screen.setChecked(True)
            return

        for widget, enabled in self._screen_record_restore_states.items():
            try:
                widget.setEnabled(bool(enabled))
            except Exception:
                continue
        self._screen_record_restore_states = {}
        self._update_run_button_states(self.auto_clicker.is_running)

    def _on_screen_record_elapsed_tick(self):
        """Update status bar with recording elapsed time."""
        if not self._screen_recording_active:
            self._screen_record_elapsed_timer.stop()
            return
        self._update_screen_record_status()

    def _update_screen_record_status(self):
        """Show live recording duration and action count."""
        if not self._screen_recording_active or not self.screen_action_recorder:
            return
        elapsed = float(self.screen_action_recorder.elapsed_seconds)
        action_count = int(self.screen_action_recorder.action_count)
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        deci = int((elapsed - int(elapsed)) * 10)
        self.statusBar.showMessage(
            f"[REC] Screen recording {minutes:02d}:{seconds:02d}.{deci} | "
            f"actions: {action_count} | {self._to_hotkey_display(self.hotkey_bindings['record'])}=stop"
        )
    
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
            self._set_status_recording_style(True)
            self.statusBar.showMessage(
                f"🔴 Recording actions... {self._to_hotkey_display(self.hotkey_bindings['page_up'])}=Left, "
                f"{self._to_hotkey_display(self.hotkey_bindings['page_down'])}=Advanced actions, ESC=finish"
            )
        else:
            self.pending_branch_index = None
            self._release_active_action_tool_button()
    
    def on_position_recorded(self, count: int):
        """Handle position recorded"""
        self._set_status_recording_style(True)
        self.statusBar.showMessage(
            f"🔴 Recording actions... ({count} recorded) "
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
                    scroll_clicks = pos.get("scroll_clicks")
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
                    scroll_clicks = None
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
                if scroll_clicks is not None:
                    action_data["scroll_clicks"] = int(scroll_clicks)
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
        self._set_status_recording_style(False)
        self.pending_branch_index = None
        self._release_active_action_tool_button()
    
    def _choose_record_action(self, start_x: int | None = None, start_y: int | None = None):
        """Show action chooser for PAGE DOWN during recording."""
        return choose_advanced_action(self, start_x, start_y)

    def on_advanced_toolbar_drop(self, choice_name: str, drop_x: int, drop_y: int):
        """Create one POSITION action by dragging advanced-action icon to screen point."""
        if self._screen_recording_active:
            self.statusBar.showMessage("Screen recording is active. Press F10 to stop first.")
            return
        if self._screen_record_armed:
            self._screen_record_armed = False
            self.btn_tool_record_screen.setChecked(False)
            self.statusBar.showMessage("Record Screen Action canceled")
        if not self._ensure_target_selected():
            return
        branch_index = self._get_selected_branch_index(require_selection=True)
        if branch_index is None:
            QMessageBox.information(
                self,
                "Select Branch",
                "Please select a branch before using advanced action toolbar."
            )
            self.statusBar.showMessage("Select a branch first")
            return

        action_data = choose_advanced_action_by_choice(self, choice_name, int(drop_x), int(drop_y))
        if not action_data:
            return

        default_delay_ms = int(self.config.get("click_delay_ms", 100))
        target_hwnd = int(self.selected_target_window.hwnd) if self.selected_target_window else None
        target_title = self.selected_target_window.title if self.selected_target_window else ""

        payload = {
            "x": int(drop_x),
            "y": int(drop_y),
            "action_mode": str(action_data.get("action_mode", "mouse_click")).lower(),
            "mouse_button": str(action_data.get("mouse_button", "left")).lower(),
            "delay_ms": default_delay_ms,
            "target_hwnd": target_hwnd,
            "target_title": target_title,
        }
        if action_data.get("scroll_clicks") is not None:
            payload["scroll_clicks"] = int(action_data.get("scroll_clicks"))
        if action_data.get("hold_ms") is not None:
            payload["hold_ms"] = int(action_data.get("hold_ms"))
        if action_data.get("drag_to_x") is not None and action_data.get("drag_to_y") is not None:
            payload["drag_to_x"] = int(action_data.get("drag_to_x"))
            payload["drag_to_y"] = int(action_data.get("drag_to_y"))
        if action_data.get("drag_ms") is not None:
            payload["drag_ms"] = int(action_data.get("drag_ms"))
        if action_data.get("key_name"):
            payload["key_name"] = str(action_data.get("key_name"))
        if action_data.get("hotkey_keys"):
            payload["hotkey_keys"] = list(action_data.get("hotkey_keys"))

        if target_hwnd is not None:
            try:
                cx, cy = win32gui.ScreenToClient(target_hwnd, (int(drop_x), int(drop_y)))
                payload["client_x"] = int(cx)
                payload["client_y"] = int(cy)
            except Exception:
                pass
            if payload.get("drag_to_x") is not None and payload.get("drag_to_y") is not None:
                try:
                    dcx, dcy = win32gui.ScreenToClient(
                        target_hwnd,
                        (int(payload.get("drag_to_x")), int(payload.get("drag_to_y")))
                    )
                    payload["drag_client_x"] = int(dcx)
                    payload["drag_client_y"] = int(dcy)
                except Exception:
                    pass

        action = ClickAction(ClickType.POSITION, **payload)
        self._add_action_to_selected_branch(action, int(branch_index))
        self.update_table()
        self.statusBar.showMessage(f"Added action '{choice_name}' at ({int(drop_x)}, {int(drop_y)})")
    
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
        if image_click_type == ClickType.IMAGE:
            mode = "Image Based"
        elif image_click_type == ClickType.IMAGE_DIRECT:
            mode = "Image Direct"
        else:
            mode = "Image Recognition"
        self._set_status_recording_style(True)
        self.statusBar.showMessage(f"[REC] {mode} recording started. Target: {self.selected_target_window.title}")
    
    def on_image_recorded(self, recorded: dict, total_count: int):
        """Handle one image+click position recorded and persist it immediately"""
        is_direct = self.pending_image_action_type == ClickType.IMAGE_DIRECT
        is_recognition = self.pending_image_action_type == ClickType.IMAGE_RECOGNITION
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
            scroll_clicks=recorded.get("scroll_clicks"),
            hold_ms=recorded.get("hold_ms"),
            drag_to_x=recorded.get("drag_to_x"),
            drag_to_y=recorded.get("drag_to_y"),
            drag_client_x=recorded.get("drag_client_x"),
            drag_client_y=recorded.get("drag_client_y"),
            drag_ms=recorded.get("drag_ms"),
            key_name=recorded.get("key_name"),
            hotkey_keys=recorded.get("hotkey_keys"),
            region_x1=recorded.get("region_x1"),
            region_y1=recorded.get("region_y1"),
            region_x2=recorded.get("region_x2"),
            region_y2=recorded.get("region_y2"),
            target_hwnd=recorded.get("target_hwnd"),
            target_title=recorded.get("target_title", ""),
            priority_level=1 if is_direct else 0,
            last_recognized_value="" if is_recognition else None,
            last_recognition_status="" if is_recognition else None,
            delay_ms=default_delay_ms
        )
        self._add_action_to_selected_branch(action, self.pending_branch_index)
        self.update_table()
        mode_label = "image recognition" if is_recognition else "image"
        self.statusBar.showMessage(f"Recorded {total_count} {mode_label} action(s). Continue selecting, press ESC to finish.")
    
    def on_image_recording_complete(self, recorded_images):
        """Handle image recording complete"""
        count = len(recorded_images) if recorded_images else 0
        if count > 0:
            self.statusBar.showMessage(f"Image recording finished. Total recorded: {count}")
        else:
            self.statusBar.showMessage("Image recording finished. No images recorded.")
        self._set_status_recording_style(False)
        self.pending_branch_index = None
        self._release_active_action_tool_button()
    
    def on_image_recording_cancelled(self):
        """Handle image recording cancelled"""
        self.statusBar.showMessage("Image recording cancelled")
        self._set_status_recording_style(False)
        self.pending_branch_index = None
        self._release_active_action_tool_button()

    
    def on_delete_selected_item(self):
        """Delete currently selected branch/action (selection-based, not checkbox-based)."""
        current_item = self.script_tree.currentItem()
        if not current_item:
            self.statusBar.showMessage("Select a branch or action to delete")
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
                    entry = actions[action_index]
                    action_id = entry.get("id")
                    if action_id:
                        # Remove selected action and all its descendants in this branch.
                        remove_ids = {str(action_id)}
                        changed = True
                        while changed:
                            changed = False
                            for e in actions:
                                pid = e.get("parent_id")
                                eid = e.get("id")
                                if pid and eid and str(pid) in remove_ids and str(eid) not in remove_ids:
                                    remove_ids.add(str(eid))
                                    changed = True
                        actions[:] = [e for e in actions if str(e.get("id")) not in remove_ids]
                    else:
                        actions.pop(action_index)
                    self.update_table()
                    self.statusBar.showMessage("Action removed")

    def on_script_tree_context_menu_requested(self, pos):
        """Show right-click context menu for selected tree item."""
        item = self.script_tree.itemAt(pos)
        if item is not None:
            self.script_tree.setCurrentItem(item)

        menu = QMenu(self)
        add_branch_action = menu.addAction("Add Branch")
        add_if_action = menu.addAction("Add IF")
        quick_if_menu = menu.addMenu("Quick IF")
        qif_num_gt = quick_if_menu.addAction("OCR Number > X  -> Stop")
        qif_num_gte = quick_if_menu.addAction("OCR Number >= X -> Stop")
        qif_num_lt = quick_if_menu.addAction("OCR Number < X  -> Stop")
        qif_num_lte = quick_if_menu.addAction("OCR Number <= X -> Stop")
        qif_num_eq = quick_if_menu.addAction("OCR Number == X -> Stop")
        qif_text_contains = quick_if_menu.addAction("OCR Text contains X -> Stop")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        clear_all_action = menu.addAction("Clear All")

        rename_action.setEnabled(item is not None)
        delete_action.setEnabled(item is not None)

        chosen = menu.exec(self.script_tree.viewport().mapToGlobal(pos))
        if chosen == add_branch_action:
            self.on_add_branch()
            return
        if chosen == add_if_action:
            self.on_add_if(item)
            return
        if chosen == qif_num_gt:
            self.on_add_quick_if(item, "number", "gt")
            return
        if chosen == qif_num_gte:
            self.on_add_quick_if(item, "number", "gte")
            return
        if chosen == qif_num_lt:
            self.on_add_quick_if(item, "number", "lt")
            return
        if chosen == qif_num_lte:
            self.on_add_quick_if(item, "number", "lte")
            return
        if chosen == qif_num_eq:
            self.on_add_quick_if(item, "number", "eq")
            return
        if chosen == qif_text_contains:
            self.on_add_quick_if(item, "text", "contains")
            return
        if chosen == rename_action:
            self.on_rename_selected()
            return
        if chosen == delete_action:
            self.on_delete_selected_item()
            return
        if chosen == clear_all_action:
            self.on_clear_all()

    def _collect_image_recognition_sources(self) -> list[dict]:
        """Collect IMAGE_RECOGNITION actions for Quick IF source."""
        options = []
        for gi, group in enumerate(self.script_groups):
            gname = str(group.get("name", f"Branch {gi+1}"))
            for ai, entry in enumerate(group.get("actions", [])):
                if not entry.get("id"):
                    entry["id"] = uuid.uuid4().hex
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                if action.type != ClickType.IMAGE_RECOGNITION:
                    continue
                options.append({
                    "id": str(entry.get("id") or ""),
                    "name": str(entry.get("name", f"Action {ai+1}")),
                    "group_index": gi,
                    "group_name": gname,
                    "action_index": ai,
                })
        return [x for x in options if x.get("id")]

    def _resolve_quick_if_source(self, context_item: QTreeWidgetItem | None) -> dict | None:
        """Resolve source IMAGE_RECOGNITION action from current context."""
        if context_item is not None:
            payload = context_item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(payload, tuple) and len(payload) >= 3 and payload[0] == "action":
                gi = int(payload[1])
                ai = int(payload[2])
                if 0 <= gi < len(self.script_groups):
                    actions = self.script_groups[gi].get("actions", [])
                    if 0 <= ai < len(actions):
                        entry = actions[ai]
                        action = entry.get("action")
                        if isinstance(action, ClickAction) and action.type == ClickType.IMAGE_RECOGNITION:
                            if not entry.get("id"):
                                entry["id"] = uuid.uuid4().hex
                            return {
                                "id": str(entry.get("id")),
                                "name": str(entry.get("name", f"Action {ai+1}")),
                                "group_index": gi,
                                "group_name": str(self.script_groups[gi].get("name", f"Branch {gi+1}")),
                                "action_index": ai,
                            }

        options = self._collect_image_recognition_sources()
        if not options:
            return None
        if len(options) == 1:
            return options[0]
        labels = [f"{o['name']} [{o['group_name']}]" for o in options]
        selected, ok = QInputDialog.getItem(
            self,
            "Quick IF Source",
            "Select IMAGE RECOGNITION source action:",
            labels,
            0,
            False,
        )
        if not ok:
            return None
        try:
            idx = labels.index(str(selected))
            return options[idx]
        except Exception:
            return None

    def on_add_quick_if(self, context_item: QTreeWidgetItem | None, value_type: str, operator: str):
        """Add Quick IF preset (OCR compare -> STOP)."""
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Cannot add IF while running")
            return

        source = self._resolve_quick_if_source(context_item)
        if not source:
            QMessageBox.information(
                self,
                "Quick IF",
                "No IMAGE RECOGNITION source found. Please add one first."
            )
            return

        compare_value = ""
        if str(value_type) == "number":
            number, ok = QInputDialog.getDouble(
                self,
                "Quick IF",
                "Enter X value:",
                0.0,
                -999999999.0,
                999999999.0,
                3,
            )
            if not ok:
                return
            compare_value = str(number)
        else:
            text, ok = QInputDialog.getText(self, "Quick IF", "Enter text X:")
            if not ok:
                return
            compare_value = str(text or "").strip()
            if not compare_value:
                QMessageBox.warning(self, "Quick IF", "Compare text cannot be empty.")
                return

        action = ClickAction(
            ClickType.IF,
            if_mode="if",
            if_condition_type="ocr_compare",
            if_ocr_value_type=str(value_type),
            if_ocr_operator=str(operator),
            if_ocr_compare_value=str(compare_value),
            source_action_id=str(source.get("id", "")),
            source_action_name=str(source.get("name", "")),
            then_action="stop",
            target_branch_index=None,
            target_action_id=None,
            target_action_name=None,
            priority_level=0,
            if_cooldown_ms=500,
            delay_ms=0,
        )
        new_entry = {
            "id": uuid.uuid4().hex,
            "parent_id": None,
            "max_executions": None,
            "name": f"QIF {sum(1 for g in self.script_groups for e in g.get('actions', []) if isinstance(e.get('action'), ClickAction) and e.get('action').type == ClickType.IF) + 1}",
            "enabled": True,
            "action": action,
        }
        inserted = False
        try:
            gi = int(source.get("group_index"))
            ai = int(source.get("action_index"))
            if 0 <= gi < len(self.script_groups):
                actions = self.script_groups[gi].setdefault("actions", [])
                if 0 <= ai < len(actions):
                    src_parent_id = actions[ai].get("parent_id")
                    new_entry["parent_id"] = src_parent_id
                    actions.insert(ai + 1, new_entry)
                    inserted = True
        except Exception:
            inserted = False
        if not inserted:
            self._insert_action_entry_at_context(new_entry, context_item)
        self.update_table()
        self.statusBar.showMessage("Added Quick IF (OCR compare -> STOP) below source Image Recognition")

    def on_add_if(self, context_item: QTreeWidgetItem | None):
        """Add IF/IF NOT row at context position in branch/action list."""
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Cannot add IF while running")
            return

        source_options = self._collect_image_action_sources()
        if not source_options:
            QMessageBox.information(
                self,
                "Add IF",
                "No image-related source action found.\nPlease add IMAGE / IMAGE DIRECT / IMAGE RECOGNITION first."
            )
            return

        if_data = self._show_if_dialog(source_options)
        if not if_data:
            return

        action = ClickAction(
            ClickType.IF,
            if_mode=str(if_data.get("if_mode", "if")),
            if_condition_type=str(if_data.get("if_condition_type", "image_visible")),
            if_ocr_value_type=str(if_data.get("if_ocr_value_type", "number")),
            if_ocr_operator=str(if_data.get("if_ocr_operator", "eq")),
            if_ocr_compare_value=str(if_data.get("if_ocr_compare_value", "")),
            source_action_id=str(if_data.get("source_action_id", "")),
            source_action_name=str(if_data.get("source_action_name", "")),
            then_action=str(if_data.get("then_action", "run_branch")),
            target_branch_index=if_data.get("target_branch_index"),
            target_action_id=if_data.get("target_action_id"),
            target_action_name=if_data.get("target_action_name"),
            priority_level=int(if_data.get("priority_level", 0) or 0),
            if_cooldown_ms=int(if_data.get("if_cooldown_ms", 500) or 0),
            delay_ms=0,
        )
        new_entry = {
            "id": uuid.uuid4().hex,
            "parent_id": None,
            "max_executions": None,
            "name": f"IF {sum(1 for g in self.script_groups for e in g.get('actions', []) if isinstance(e.get('action'), ClickAction) and e.get('action').type == ClickType.IF) + 1}",
            "enabled": True,
            "action": action,
        }
        self._insert_action_entry_at_context(new_entry, context_item)
        self.update_table()
        self.statusBar.showMessage("Added IF row")

    def _insert_action_entry_at_context(self, new_entry: dict, context_item: QTreeWidgetItem | None):
        """Insert action entry near right-clicked item (before action row, else append branch)."""
        branch_index = self._get_selected_branch_index(require_selection=False)
        insert_index = None
        parent_id_for_new = None
        if context_item is not None:
            payload = context_item.data(0, Qt.ItemDataRole.UserRole)
            if payload and payload[0] == "group":
                branch_index = int(payload[1])
            elif payload and payload[0] == "action":
                branch_index = int(payload[1])
                insert_index = int(payload[2])
                if 0 <= branch_index < len(self.script_groups):
                    actions = self.script_groups[branch_index].get("actions", [])
                    if 0 <= insert_index < len(actions):
                        parent_id_for_new = actions[insert_index].get("parent_id")

        if branch_index is None or branch_index < 0 or branch_index >= len(self.script_groups):
            self._ensure_default_group()
            branch_index = 0
        actions = self.script_groups[branch_index].setdefault("actions", [])
        new_entry["parent_id"] = parent_id_for_new
        if insert_index is None or insert_index < 0 or insert_index > len(actions):
            actions.append(new_entry)
        else:
            actions.insert(insert_index, new_entry)

    def _collect_image_action_sources(self) -> list[dict]:
        """Collect image-driven actions for IF source picker."""
        options = []
        for gi, group in enumerate(self.script_groups):
            gname = str(group.get("name", f"Branch {gi+1}"))
            for ai, entry in enumerate(group.get("actions", [])):
                if not entry.get("id"):
                    entry["id"] = uuid.uuid4().hex
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                if action.type not in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IMAGE_RECOGNITION):
                    continue
                action_id = str(entry.get("id") or "")
                if not action_id:
                    continue
                options.append({
                    "id": action_id,
                    "name": str(entry.get("name", f"Action {ai+1}")),
                    "group_index": gi,
                    "group_name": gname,
                    "action_index": ai,
                    "action_type": action.type.value,
                })
        return options

    def _show_if_dialog(self, source_options: list[dict]) -> dict | None:
        """Open dialog to configure IF/IF NOT rule."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Add IF")
        self._apply_always_on_top_to_dialog(dlg)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        mode_combo = QComboBox()
        mode_combo.addItem("IF")
        mode_combo.addItem("IF NOT")
        form.addRow("Mode:", mode_combo)

        source_combo = QComboBox()
        for opt in source_options:
            type_label = str(opt.get("action_type", "")).replace("_", " ").upper()
            source_combo.addItem(f"{opt['name']} [{opt['group_name']}] ({type_label})", opt)
        form.addRow("Source Action:", source_combo)

        condition_combo = QComboBox()
        condition_combo.addItem("Image Visible / Not Visible", "image_visible")
        condition_combo.addItem("OCR Value Compare", "ocr_compare")
        form.addRow("Condition:", condition_combo)

        ocr_type_combo = QComboBox()
        ocr_type_combo.addItem("Number", "number")
        ocr_type_combo.addItem("Text", "text")
        form.addRow("OCR Value Type:", ocr_type_combo)

        ocr_op_combo = QComboBox()
        form.addRow("Operator:", ocr_op_combo)

        ocr_value_edit = QLineEdit()
        ocr_value_edit.setPlaceholderText("Compare value")
        form.addRow("Compare Value:", ocr_value_edit)

        then_combo = QComboBox()
        then_combo.addItem("Run Branch", "run_branch")
        then_combo.addItem("Run Action", "run_action")
        then_combo.addItem("Stop", "stop")
        form.addRow("Then:", then_combo)

        target_combo = QComboBox()
        for gi, group in enumerate(self.script_groups):
            target_combo.addItem(str(group.get("name", f"Branch {gi+1}")), gi)
        form.addRow("Target Branch:", target_combo)

        target_action_combo = QComboBox()
        all_actions = []
        for gi, group in enumerate(self.script_groups):
            gname = str(group.get("name", f"Branch {gi+1}"))
            for ai, entry in enumerate(group.get("actions", [])):
                aid = str(entry.get("id") or "")
                if not aid:
                    continue
                name = str(entry.get("name", f"Action {ai+1}"))
                all_actions.append({
                    "id": aid,
                    "name": name,
                    "group_name": gname,
                    "group_index": gi,
                    "action_index": ai,
                })
        for opt in all_actions:
            target_action_combo.addItem(f"{opt['name']} [{opt['group_name']}]", opt)
        form.addRow("Target Action:", target_action_combo)

        priority_spin = QSpinBox()
        priority_spin.setRange(0, 20)
        priority_spin.setValue(0)
        form.addRow("Priority:", priority_spin)

        cooldown_spin = QSpinBox()
        cooldown_spin.setRange(0, 60000)
        cooldown_spin.setValue(500)
        form.addRow("Cooldown (ms):", cooldown_spin)

        def _sync_ocr_ops():
            ocr_op_combo.blockSignals(True)
            ocr_op_combo.clear()
            val_type = str(ocr_type_combo.currentData() or "number")
            if val_type == "number":
                ocr_op_combo.addItem(">", "gt")
                ocr_op_combo.addItem(">=", "gte")
                ocr_op_combo.addItem("<", "lt")
                ocr_op_combo.addItem("<=", "lte")
                ocr_op_combo.addItem("==", "eq")
                ocr_op_combo.addItem("!=", "neq")
            else:
                ocr_op_combo.addItem("contains", "contains")
                ocr_op_combo.addItem("not contains", "not_contains")
                ocr_op_combo.addItem("equals", "equals")
                ocr_op_combo.addItem("not equals", "not_equals")
            ocr_op_combo.blockSignals(False)

        def _sync_condition_state():
            is_ocr = str(condition_combo.currentData()) == "ocr_compare"
            ocr_type_combo.setEnabled(is_ocr)
            ocr_op_combo.setEnabled(is_ocr)
            ocr_value_edit.setEnabled(is_ocr)

        def _sync_then_state():
            then_mode = str(then_combo.currentData())
            target_combo.setEnabled(then_mode == "run_branch")
            target_action_combo.setEnabled(then_mode == "run_action")

        ocr_type_combo.currentIndexChanged.connect(_sync_ocr_ops)
        condition_combo.currentIndexChanged.connect(_sync_condition_state)
        then_combo.currentIndexChanged.connect(_sync_then_state)
        _sync_ocr_ops()
        _sync_condition_state()
        _sync_then_state()

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        source_opt = source_combo.currentData()
        if not isinstance(source_opt, dict):
            return None

        condition_type = str(condition_combo.currentData() or "image_visible")
        source_action_type = str(source_opt.get("action_type", ""))
        if condition_type == "ocr_compare" and source_action_type != ClickType.IMAGE_RECOGNITION.value:
            QMessageBox.warning(
                self,
                "Invalid IF Source",
                "OCR Value Compare requires source action type IMAGE RECOGNITION."
            )
            return None

        ocr_value = str(ocr_value_edit.text() or "").strip()
        if condition_type == "ocr_compare" and not ocr_value:
            QMessageBox.warning(self, "Invalid IF", "Please enter OCR compare value.")
            return None

        then_action = str(then_combo.currentData() or "run_branch")
        target_branch_index = int(target_combo.currentData()) if then_action == "run_branch" else None
        target_action_opt = target_action_combo.currentData() if then_action == "run_action" else None
        target_action_id = None
        target_action_name = None
        if then_action == "run_action":
            if not isinstance(target_action_opt, dict):
                QMessageBox.warning(self, "Invalid IF", "Please select a target action.")
                return None
            target_action_id = str(target_action_opt.get("id", ""))
            target_action_name = str(target_action_opt.get("name", ""))
            if not target_action_id:
                QMessageBox.warning(self, "Invalid IF", "Target action id is missing.")
                return None

        return {
            "if_mode": "if_not" if mode_combo.currentText().strip().upper() == "IF NOT" else "if",
            "if_condition_type": condition_type,
            "if_ocr_value_type": str(ocr_type_combo.currentData() or "number"),
            "if_ocr_operator": str(ocr_op_combo.currentData() or "eq"),
            "if_ocr_compare_value": ocr_value,
            "source_action_id": str(source_opt.get("id", "")),
            "source_action_name": str(source_opt.get("name", "")),
            "then_action": then_action,
            "target_branch_index": target_branch_index,
            "target_action_id": target_action_id,
            "target_action_name": target_action_name,
            "priority_level": int(priority_spin.value()),
            "if_cooldown_ms": int(cooldown_spin.value()),
        }
    
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
        
        if action.type not in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IF):
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
                checked = item.checkState(0) != Qt.CheckState.Unchecked
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
                checked = item.checkState(0) != Qt.CheckState.Unchecked
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

    def on_script_tree_order_changed(self):
        """Handle drag-drop reorder and sync tree order back to script data."""
        if self._updating_table:
            return
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Cannot reorder actions while running")
            self.update_table()
            return
        self._rebuild_groups_from_tree()
        self.update_table()
        self.statusBar.showMessage("Action order updated")

    def on_replace_action_requested(self, source_payload, target_payload):
        """Handle setting parent-child relation (drag source(s) onto target action)."""
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Cannot update parent-child while running")
            self.update_table()
            return

        if not (isinstance(target_payload, tuple) and len(target_payload) >= 3 and target_payload[0] == "action"):
            return
        try:
            tgt_gi, tgt_ai = int(target_payload[1]), int(target_payload[2])
        except Exception:
            return
        if tgt_gi < 0 or tgt_gi >= len(self.script_groups):
            return
        tgt_actions = self.script_groups[tgt_gi].get("actions", [])
        if tgt_ai < 0 or tgt_ai >= len(tgt_actions):
            return

        tgt_entry = tgt_actions[tgt_ai]
        tgt_id = str(tgt_entry.get("id") or uuid.uuid4().hex)
        tgt_entry["id"] = tgt_id

        # Normalize source payload(s).
        if isinstance(source_payload, list):
            raw_sources = source_payload
        else:
            raw_sources = [source_payload]
        source_items = []
        for sp in raw_sources:
            if not (isinstance(sp, tuple) and len(sp) >= 3 and sp[0] == "action"):
                continue
            try:
                sgi, sai = int(sp[1]), int(sp[2])
            except Exception:
                continue
            if sgi < 0 or sgi >= len(self.script_groups):
                continue
            actions = self.script_groups[sgi].get("actions", [])
            if sai < 0 or sai >= len(actions):
                continue
            src_entry = actions[sai]
            src_id = str(src_entry.get("id") or uuid.uuid4().hex)
            src_entry["id"] = src_id
            if src_id == tgt_id:
                continue
            source_items.append((sgi, sai, src_id))

        # De-duplicate by source id, keep stable order.
        dedup = []
        seen_ids = set()
        for sgi, sai, sid in sorted(source_items, key=lambda x: (x[0], x[1])):
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            dedup.append((sgi, sai, sid))
        source_items = dedup
        if not source_items:
            return

        def _find_action_location(action_id: str):
            for gi, group in enumerate(self.script_groups):
                actions = group.get("actions", [])
                for ai, entry in enumerate(actions):
                    if str(entry.get("id")) == str(action_id):
                        return gi, ai, entry
            return None, None, None

        moved_count = 0
        blocked_count = 0
        for _, _, src_id in source_items:
            current = _find_action_location(src_id)
            target_now = _find_action_location(tgt_id)
            if current[0] is None or target_now[0] is None:
                continue
            src_gi, src_ai, src_entry = current
            cur_tgt_gi, _, _ = target_now

            # Prevent cycle (target cannot be in source subtree).
            if src_gi == cur_tgt_gi:
                by_id = {str(e.get("id")): e for e in self.script_groups[src_gi].get("actions", []) if e.get("id")}
                cursor = str(tgt_id)
                cycle = False
                while cursor:
                    if cursor == str(src_id):
                        cycle = True
                        break
                    parent_entry = by_id.get(cursor)
                    cursor = str(parent_entry.get("parent_id")) if parent_entry and parent_entry.get("parent_id") else None
                if cycle:
                    blocked_count += 1
                    continue

            # Move across branches if needed.
            if src_gi != cur_tgt_gi:
                src_actions = self.script_groups[src_gi].get("actions", [])
                moved_entry = src_actions.pop(src_ai)
                self.script_groups[cur_tgt_gi].setdefault("actions", []).append(moved_entry)
                src_entry = moved_entry

            src_entry["parent_id"] = str(tgt_id)
            moved_count += 1

        self._last_selected_branch_index = tgt_gi
        self.update_table()
        if moved_count > 0 and blocked_count > 0:
            self.statusBar.showMessage(
                f"Parent-child updated: {moved_count} action(s) moved, {blocked_count} blocked by cycle"
            )
        elif moved_count > 0:
            self.statusBar.showMessage(f"Parent-child updated: {moved_count} action(s)")
        else:
            self.statusBar.showMessage("No actions moved")

    def _rebuild_groups_from_tree(self):
        """Rebuild script_groups based on current tree visual order."""
        old_groups = self.script_groups
        old_counts = self.action_counts.copy()
        new_groups: list[dict] = []
        new_counts: dict[tuple[int, int], int] = {}
        selected_branch = None

        for new_gi in range(self.script_tree.topLevelItemCount()):
            group_item = self.script_tree.topLevelItem(new_gi)
            payload = group_item.data(0, Qt.ItemDataRole.UserRole)
            old_gi = int(payload[1]) if payload and payload[0] == "group" else -1
            old_group = old_groups[old_gi] if 0 <= old_gi < len(old_groups) else {"actions": []}
            group_name = (group_item.text(0) or f"Branch {new_gi + 1}").strip() or f"Branch {new_gi + 1}"
            group_enabled = group_item.checkState(0) != Qt.CheckState.Unchecked

            actions = []
            new_ai = 0

            def walk_actions(parent_item, parent_action_id):
                nonlocal new_ai
                for i in range(parent_item.childCount()):
                    action_item = parent_item.child(i)
                    a_payload = action_item.data(0, Qt.ItemDataRole.UserRole)
                    if not a_payload or a_payload[0] != "action":
                        continue
                    src_gi = int(a_payload[1])
                    src_ai = int(a_payload[2])
                    if src_gi < 0 or src_gi >= len(old_groups):
                        continue
                    src_actions = old_groups[src_gi].get("actions", [])
                    if src_ai < 0 or src_ai >= len(src_actions):
                        continue
                    src_entry = src_actions[src_ai]
                    action_obj = src_entry.get("action")
                    if not isinstance(action_obj, ClickAction):
                        continue
                    entry_id = str(src_entry.get("id") or uuid.uuid4().hex)
                    new_entry = {
                        "id": entry_id,
                        "parent_id": parent_action_id,
                        "max_executions": src_entry.get("max_executions"),
                        "name": (action_item.text(0) or src_entry.get("name", f"Action {new_ai + 1}")).strip() or f"Action {new_ai + 1}",
                        "enabled": action_item.checkState(0) != Qt.CheckState.Unchecked,
                        "action": action_obj,
                    }
                    actions.append(new_entry)
                    new_counts[(new_gi, new_ai)] = int(old_counts.get((src_gi, src_ai), 0))
                    new_ai += 1
                    walk_actions(action_item, entry_id)

            walk_actions(group_item, None)

            new_groups.append({
                "name": group_name,
                "enabled": bool(group_enabled),
                "actions": actions
            })
            if group_item is self.script_tree.currentItem() or (
                self.script_tree.currentItem() and self.script_tree.currentItem().parent() is group_item
            ):
                selected_branch = new_gi

        self.script_groups = new_groups if new_groups else [{"name": "Branch 1", "enabled": True, "actions": []}]
        self.action_counts = new_counts
        if selected_branch is not None:
            self._last_selected_branch_index = int(selected_branch)
   
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

    def _on_limit_spin_changed(self, group_index: int, action_index: int, value: int):
        """Handle execution limit changes from per-action spinbox."""
        if self._updating_table:
            return
        if group_index < 0 or group_index >= len(self.script_groups):
            return
        actions = self.script_groups[group_index].get("actions", [])
        if action_index < 0 or action_index >= len(actions):
            return
        entry = actions[action_index]
        # 0 = Unlimited (specialValueText); >=1 = hard limit.
        entry["max_executions"] = None if int(value) <= 0 else int(value)
    
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
        left_click_icon = QIcon(self._resource_path(os.path.join("resource", "LeftClick.png")))
        right_click_icon = QIcon(self._resource_path(os.path.join("resource", "RightClick.png")))
        middle_click_icon = QIcon(self._resource_path(os.path.join("resource", "MiddleClick.png")))
        scroll_up_icon = QIcon(self._resource_path(os.path.join("resource", "ScrollUp.png")))
        scroll_down_icon = QIcon(self._resource_path(os.path.join("resource", "ScrollDown.png")))
        mouse_hold_left_icon = QIcon(self._resource_path(os.path.join("resource", "MouseHoldLeft.png")))
        mouse_hold_right_icon = QIcon(self._resource_path(os.path.join("resource", "MouseHoldRight.png")))
        drag_icon = QIcon(self._resource_path(os.path.join("resource", "DragAndDrop.png")))
        key_press_icon = QIcon(self._resource_path(os.path.join("resource", "KeyPress.png")))
        hotkey_icon = QIcon(self._resource_path(os.path.join("resource", "Hotkey.png")))
        key_hold_icon = QIcon(self._resource_path(os.path.join("resource", "KeyHold.png")))
        record_screen_icon = QIcon(self._resource_path(os.path.join("resource", "RecordScreen.png")))
        image_recognition_icon = QIcon(self._resource_path(os.path.join("resource", "ImageRecognition.png")))
        speed_up_icon = QIcon(self._resource_path(os.path.join("resource", "SpeedUp.png")))
        speed_down_icon = QIcon(self._resource_path(os.path.join("resource", "SpeedDown.png")))
        mouse_on_drag_pixmap = QPixmap(self._resource_path(os.path.join("resource", "MouseOnDrag.png")))
        return {
            "app": app_icon,
            "position": position_icon,
            "image": image_icon,
            "image_direct": image_direct_icon,
            "adv_left_click": left_click_icon,
            "adv_right_click": right_click_icon,
            "adv_middle_click": middle_click_icon,
            "adv_scroll_up": scroll_up_icon,
            "adv_scroll_down": scroll_down_icon,
            "adv_mouse_hold_left": mouse_hold_left_icon,
            "adv_mouse_hold_right": mouse_hold_right_icon,
            "adv_drag_left": drag_icon,
            "adv_key_press": key_press_icon,
            "adv_hotkey": hotkey_icon,
            "adv_key_hold_repeat": key_hold_icon,
            "record_screen": record_screen_icon,
            "image_recognition": image_recognition_icon,
            "speed_up": speed_up_icon,
            "speed_down": speed_down_icon,
            "mouse_on_drag": mouse_on_drag_pixmap,
        }

    def _apply_action_icon(self, item: QTreeWidgetItem, action: ClickAction):
        """Attach action-type icon to tree row."""
        if action.type == ClickType.POSITION:
            icon = self._icons.get("position")
        elif action.type == ClickType.IMAGE_DIRECT:
            icon = self._icons.get("image_direct")
        elif action.type == ClickType.IMAGE_RECOGNITION:
            icon = self._icons.get("image_recognition")
        elif action.type == ClickType.IF:
            icon = self._icons.get("adv_hotkey")
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
            "home": str(self.config.get("hotkey_home", "home")),
            "end": str(self.config.get("hotkey_end", "end")),
            "record": str(self.config.get("hotkey_record", "f10")),
        }
        return bindings

    def _update_record_hotkey_ui(self):
        """Refresh record-screen hotkey hints/tooltips."""
        key_text = self._to_hotkey_display(self.hotkey_bindings.get("record", "f10"))
        if self.btn_tool_record_screen:
            self.btn_tool_record_screen.setToolTip(
                "Record all keyboard/mouse actions on screen.\n"
                f"Press {key_text} to start recording, press {key_text} again to stop."
            )
    
    def _get_recording_hotkeys(self) -> dict:
        """Get recording hotkey mapping for listeners."""
        return {
            "page_up": self.hotkey_bindings["page_up"],
            "page_down": self.hotkey_bindings["page_down"],
        }
    
    def _update_run_button_states(self, running: bool):
        """Update Start/Stop button enabled state and visual style."""
        is_paused = bool(self.auto_clicker.is_paused) if running else False
        start_active = True
        stop_active = running
        
        self.btn_start.setEnabled(start_active)
        self.btn_stop.setEnabled(stop_active)
        self.btn_stop.setText(f"Stop ({self._to_hotkey_display(self.hotkey_bindings['end'])})")

        if not running:
            self.btn_start.setText(f"Start ({self._to_hotkey_display(self.hotkey_bindings['home'])})")
        elif is_paused:
            self.btn_start.setText("Resume")
        else:
            self.btn_start.setText("Pause")
        
        start_style = (
            (
                "QPushButton {"
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #56c46c, stop:1 #2f9f45);"
                "color: white; font-weight: 700; border: 1px solid #2a7f3b; border-bottom: 3px solid #1f5f2c;"
                "border-radius: 7px; padding: 6px 12px; }"
                "QPushButton:pressed { border-bottom: 1px solid #1f5f2c; padding-top: 8px; padding-bottom: 4px; }"
            ) if not running else (
                "QPushButton {"
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffd36f, stop:1 #e4a72d);"
                "color: #2f2f2f; font-weight: 700; border: 1px solid #b5831f; border-bottom: 3px solid #8f6518;"
                "border-radius: 7px; padding: 6px 12px; }"
                "QPushButton:pressed { border-bottom: 1px solid #8f6518; padding-top: 8px; padding-bottom: 4px; }"
            ) if not is_paused else (
                "QPushButton {"
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #7db5ff, stop:1 #4f86d8);"
                "color: white; font-weight: 700; border: 1px solid #3f6cae; border-bottom: 3px solid #315486;"
                "border-radius: 7px; padding: 6px 12px; }"
                "QPushButton:pressed { border-bottom: 1px solid #315486; padding-top: 8px; padding-bottom: 4px; }"
            )
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

    def _set_action_add_ui_visible(self, visible: bool):
        """Show/hide action-adding UI while script is running."""
        for button in self._action_tool_buttons:
            if button is not None:
                button.setVisible(bool(visible))
        if self._advanced_action_toolbar_widget is not None:
            self._advanced_action_toolbar_widget.setVisible(bool(visible))

    def _set_status_recording_style(self, recording: bool):
        """Highlight status bar when recording is active."""
        if recording:
            self.statusBar.setStyleSheet(
                "QStatusBar {"
                "background-color: #ffe9e9;"
                "border-top: 1px solid #d77;"
                "color: #9b1c1c;"
                "font-weight: 700;"
                "}"
            )
        else:
            self.statusBar.setStyleSheet("")
    
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
        if self._screen_record_armed or self._screen_recording_active:
            self.statusBar.showMessage("Stop/cancel Record Screen Action before starting auto click")
            return
        runtime_script, key_map = self._build_runtime_script_and_key_map()
        if len(runtime_script.get_actions()) == 0:
            QMessageBox.warning(self, "Warning", "No actions to execute!")
            return

        if not self._ensure_target_selected():
            return
        
        self._apply_selected_target_to_actions()
        self._reset_action_counts()
        self._clear_execution_highlight()
        self._running_action_key_map = key_map
        self.update_table()
        
        self.auto_clicker.execute_script(runtime_script)
        self._set_action_add_ui_visible(False)
        self._update_run_button_states(True)

    def on_start_pause_resume(self):
        """Start script or toggle pause/resume when already running."""
        if not self.auto_clicker.is_running:
            # Match HOME-hotkey behavior: quick-start should auto-finish any active recording
            # (including Image Recognition overlay) before starting execution.
            if self._is_recording_active():
                self._finish_recording_for_quick_start()
            self.on_start()
            return
        if self.auto_clicker.is_paused:
            self.auto_clicker.resume()
            self.statusBar.showMessage("Resumed")
        else:
            self.auto_clicker.pause()
            self.statusBar.showMessage("Paused")
        self._update_run_button_states(True)
    
    def on_stop(self):
        """Handle stop button"""
        self.auto_clicker.stop()
        self._set_action_add_ui_visible(True)
        self._clear_execution_highlight()
        self._update_run_button_states(False)
    
    def on_home_hotkey_pressed(self):
        """Handle HOME hotkey for Start/Pause/Resume."""
        if self._screen_recording_active or self._screen_record_armed:
            return
        if (not self.auto_clicker.is_running) and self._is_recording_active():
            self._finish_recording_for_quick_start()
        self.on_start_pause_resume()

    def on_end_hotkey_pressed(self):
        """Handle END hotkey for Stop."""
        if self.auto_clicker.is_running:
            self.on_stop()
    
    def on_delay_changed(self, value: int):
        """Handle delay changed"""
        self.auto_clicker.set_delay(value)
        self.config.set("click_delay_ms", value)

    def on_speed_step_changed(self, value: int):
        """Handle global speed-adjust step changed."""
        self.config.set("speed_adjust_step_ms", max(1, int(value)))

    def on_speed_up_clicked(self):
        """Speed up checked actions by reducing delay."""
        step = int(self.config.get("speed_adjust_step_ms", 100) or 100)
        self._adjust_checked_actions_delay(-abs(step))

    def on_speed_down_clicked(self):
        """Slow down checked actions by increasing delay."""
        step = int(self.config.get("speed_adjust_step_ms", 100) or 100)
        self._adjust_checked_actions_delay(abs(step))

    def _adjust_checked_actions_delay(self, delta_ms: int):
        """Apply delay delta to all checked actions in checked branches."""
        if self.auto_clicker.is_running:
            self.statusBar.showMessage("Stop auto click before adjusting delays")
            return
        if self._is_recording_active() or self._screen_record_armed:
            self.statusBar.showMessage("Finish/cancel recording before adjusting delays")
            return

        changed = 0
        for group in self.script_groups:
            if not group.get("enabled", True):
                continue
            for entry in group.get("actions", []):
                if not entry.get("enabled", True):
                    continue
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                current = int(action.data.get("delay_ms", self.config.get("click_delay_ms", 100)) or 0)
                action.data["delay_ms"] = max(0, current + int(delta_ms))
                changed += 1

        if changed <= 0:
            self.statusBar.showMessage("No checked actions to adjust delay")
            return

        self.update_table()
        direction = "increased" if delta_ms > 0 else "decreased"
        self.statusBar.showMessage(
            f"Delay {direction} by {abs(int(delta_ms))} ms for {changed} checked action(s)"
        )
    
    def on_priority_cooldown_changed(self, value: int):
        """Handle priority cooldown changed"""
        self.auto_clicker.set_priority_cooldown(value)
        self.config.set("priority_cooldown_ms", value)

    def on_ocr_language_changed(self, index: int):
        """Handle OCR language selection."""
        if not hasattr(self, "ocr_language_combo") or self.ocr_language_combo is None:
            return
        lang_code = str(self.ocr_language_combo.currentData() or "eng+vie").strip()
        if not lang_code:
            lang_code = "eng+vie"
        self.auto_clicker.set_ocr_language(lang_code)
        self.config.set("ocr_language", lang_code)
        self.statusBar.showMessage(f"OCR language set to: {lang_code}")

    def on_drag_mode_changed(self, index: int):
        """Handle drag mode changed."""
        mode = "hybrid"
        if int(index) == 1:
            mode = "background"
        elif int(index) == 2:
            mode = "real"
        self.auto_clicker.set_drag_mode(mode)
        self.config.set("drag_mode", mode)

    def on_use_real_mouse_changed(self, checked: bool):
        """Handle toggle for using real mouse for all actions."""
        enabled = bool(checked)
        self.auto_clicker.set_use_real_mouse(enabled)
        self.config.set("use_real_mouse", enabled)
        if enabled:
            self.statusBar.showMessage("Real mouse mode enabled: all actions will occupy mouse")
        else:
            self.statusBar.showMessage("Real mouse mode disabled: using non-occupy mode where supported")

    def is_always_on_top_enabled(self) -> bool:
        """Expose always-on-top state for child dialogs."""
        return bool(self._always_on_top_enabled)

    def _apply_always_on_top_to_dialog(self, dialog):
        """Apply always-on-top flag to a child dialog."""
        if dialog is None:
            return
        try:
            dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(self._always_on_top_enabled))
            dialog.show()
        except Exception:
            pass

    def _apply_always_on_top_to_main(self):
        """Apply always-on-top flag to main window."""
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(self._always_on_top_enabled))
        self.show()

    def on_always_on_top_changed(self, checked: bool):
        """Handle Always-on-top setting toggle."""
        self._always_on_top_enabled = bool(checked)
        self.config.set("always_on_top", self._always_on_top_enabled)
        self._apply_always_on_top_to_main()
        self.statusBar.showMessage(
            "Always on top enabled" if self._always_on_top_enabled else "Always on top disabled"
        )
    
    def on_hotkey_changed(self, logical_key: str, display_value: str):
        """Handle hotkey changed from settings."""
        if self._updating_table:
            return
        key_token = self._from_hotkey_display(display_value)
        if not key_token:
            return

        # Prevent duplicate bindings across configurable hotkeys.
        existing = {k: v for k, v in self.hotkey_bindings.items() if k != logical_key}
        if key_token in existing.values():
            self.statusBar.showMessage("Hotkey already in use by another function")
            # Restore previous selection
            self._updating_table = True
            try:
                combo = {
                    "page_up": self.hotkey_page_up_combo,
                    "page_down": self.hotkey_page_down_combo,
                    "home": self.hotkey_home_combo,
                    "end": self.hotkey_end_combo,
                    "record": self.hotkey_record_combo,
                }.get(logical_key)
                if combo:
                    combo.setCurrentText(self._to_hotkey_display(self.hotkey_bindings[logical_key]))
            finally:
                self._updating_table = False
            return
        
        self.hotkey_bindings[logical_key] = key_token
        self.config.set(f"hotkey_{logical_key}", key_token)
        if logical_key == "home":
            self.keyboard_listener.set_binding("home", key_token)
            self._update_run_button_states(self.auto_clicker.is_running)
        if logical_key == "end":
            self.keyboard_listener.set_binding("end", key_token)
            self.btn_stop.setText(f"Stop ({self._to_hotkey_display(key_token)})")
            self._update_run_button_states(self.auto_clicker.is_running)
        if logical_key == "record":
            self.keyboard_listener.set_binding("f10", key_token)
            self._update_record_hotkey_ui()
        self.statusBar.showMessage(f"Hotkey {logical_key} set to {self._to_hotkey_display(key_token)}")
    
    def on_status_changed(self, message: str):
        """Handle status changed"""
        self._set_status_recording_style(self._is_recording_active())
        self.statusBar.showMessage(message)
        if not self.auto_clicker.is_running:
            self._set_action_add_ui_visible(True)
            self._clear_execution_highlight()
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
            "id": uuid.uuid4().hex,
            "parent_id": None,
            "max_executions": None,
            "name": f"Action {len(actions) + 1}",
            "enabled": True,
            "action": action
        })
    
    def _build_runtime_script_and_key_map(self):
        """Build executable flat script from current tree hierarchy/check states."""
        script = ClickScript()
        key_map: list[tuple[int, int]] = []
        action_id_to_runtime_index: dict[str, int] = {}

        # Ensure each action has a stable id for later operations.
        for group in self.script_groups:
            for entry in group.get("actions", []):
                if not entry.get("id"):
                    entry["id"] = uuid.uuid4().hex

        def add_tree_action_node(item: QTreeWidgetItem, parent_runtime_index: int | None, ancestors_enabled: bool):
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if not (isinstance(payload, tuple) and len(payload) >= 3 and payload[0] == "action"):
                return

            group_index = int(payload[1])
            action_index = int(payload[2])
            if group_index < 0 or group_index >= len(self.script_groups):
                return
            actions = self.script_groups[group_index].get("actions", [])
            if action_index < 0 or action_index >= len(actions):
                return

            entry = actions[action_index]
            enabled_here = item.checkState(0) != Qt.CheckState.Unchecked
            if not ancestors_enabled or not enabled_here:
                return

            action = entry.get("action")
            if not isinstance(action, ClickAction):
                return

            runtime_action = ClickAction.from_dict(action.to_dict())
            if runtime_action.type == ClickType.IMAGE_RECOGNITION:
                # Avoid stale OCR value from previous Start run.
                runtime_action.data["last_recognized_value"] = ""
                runtime_action.data["last_recognition_status"] = ""
                runtime_action.data["last_recognized_at"] = 0.0
            if parent_runtime_index is not None:
                runtime_action.data["__parent_runtime_index"] = int(parent_runtime_index)
            runtime_action.data["__branch_index"] = int(group_index)
            max_exec = entry.get("max_executions")
            if max_exec is not None:
                try:
                    runtime_action.data["__max_executions"] = max(1, int(max_exec))
                except Exception:
                    pass

            runtime_index = len(script.get_actions())
            script.add_action(runtime_action)
            key_map.append((group_index, action_index))
            action_id = str(entry.get("id") or "")
            if action_id:
                action_id_to_runtime_index[action_id] = int(runtime_index)

            for i in range(item.childCount()):
                add_tree_action_node(item.child(i), runtime_index, True)

        for gi in range(self.script_tree.topLevelItemCount()):
            group_item = self.script_tree.topLevelItem(gi)
            if group_item is None:
                continue
            if group_item.checkState(0) == Qt.CheckState.Unchecked:
                continue

            # Traverse visible order in tree for deterministic runtime sequence.
            for i in range(group_item.childCount()):
                add_tree_action_node(group_item.child(i), None, True)

        # Resolve IF runtime references (source image path and branch runtime indices).
        runtime_actions = script.get_actions()
        branch_runtime_indices: dict[int, list[int]] = {}
        for r_idx, act in enumerate(runtime_actions):
            bidx = act.data.get("__branch_index")
            if bidx is None:
                # Inject branch index from key map for later IF run-branch.
                if 0 <= r_idx < len(key_map):
                    bidx = int(key_map[r_idx][0])
                    act.data["__branch_index"] = bidx
            if bidx is not None:
                branch_runtime_indices.setdefault(int(bidx), []).append(int(r_idx))

        id_to_image_path: dict[str, str] = {}
        for group in self.script_groups:
            for entry in group.get("actions", []):
                action = entry.get("action")
                if not isinstance(action, ClickAction):
                    continue
                if action.type not in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IMAGE_RECOGNITION):
                    continue
                aid = str(entry.get("id") or "")
                if not aid:
                    continue
                path = str(action.data.get("image_path", "") or "")
                if path:
                    id_to_image_path[aid] = path

        for r_idx, act in enumerate(runtime_actions):
            if act.type != ClickType.IF:
                continue
            source_id = str(act.data.get("source_action_id", "") or "")
            if_path = id_to_image_path.get(source_id, "")
            act.data["__if_image_path"] = if_path
            source_runtime_index = action_id_to_runtime_index.get(source_id)
            if source_runtime_index is not None:
                act.data["__if_source_runtime_index"] = int(source_runtime_index)
            target_bi = act.data.get("target_branch_index")
            try:
                target_bi_int = int(target_bi) if target_bi is not None else None
            except Exception:
                target_bi_int = None
            if target_bi_int is not None:
                indices = [int(x) for x in branch_runtime_indices.get(target_bi_int, []) if int(x) != int(r_idx)]
                act.data["__run_branch_runtime_indices"] = indices
            target_action_id = str(act.data.get("target_action_id", "") or "")
            if target_action_id:
                run_action_runtime_idx = action_id_to_runtime_index.get(target_action_id)
                if run_action_runtime_idx is not None and int(run_action_runtime_idx) != int(r_idx):
                    act.data["__run_action_runtime_index"] = int(run_action_runtime_idx)

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
                    "id": str(entry.get("id", uuid.uuid4().hex)),
                    "parent_id": entry.get("parent_id"),
                    "max_executions": entry.get("max_executions"),
                    "name": str(entry.get("name", "Action")),
                    "enabled": bool(entry.get("enabled", True)),
                    "action": action.to_dict()
                })
            groups.append(group_payload)
        payload = {"version": "2.1", "groups": groups}
        target_payload = self._build_target_window_payload()
        if target_payload:
            payload["target_window"] = target_payload
        return payload
    
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
                        "id": str(entry.get("id") or uuid.uuid4().hex),
                        "parent_id": entry.get("parent_id"),
                        "max_executions": entry.get("max_executions"),
                        "name": str(entry.get("name", f"Action {len(actions) + 1}")),
                        "enabled": bool(entry.get("enabled", True)),
                        "action": action
                    })
                loaded_groups.append({"name": name, "enabled": enabled, "actions": actions})
        else:
            # Legacy flat format.
            legacy = ClickScript.from_dict(data if isinstance(data, dict) else {})
            actions = [
                {
                    "id": uuid.uuid4().hex,
                    "parent_id": None,
                    "max_executions": None,
                    "name": f"Action {idx + 1}",
                    "enabled": True,
                    "action": action
                }
                for idx, action in enumerate(legacy.get_actions())
            ]
            loaded_groups.append({"name": "Branch 1", "enabled": True, "actions": actions})
        
        self.script_groups = loaded_groups
        self._ensure_default_group()
        self._load_target_window_payload(data if isinstance(data, dict) else {})
    
    def _build_action_details(self, action: ClickAction) -> str:
        """Build details text for one action."""
        if action.type == ClickType.IF:
            mode = str(action.data.get("if_mode", "if")).strip().lower()
            mode_txt = "IF NOT" if mode == "if_not" else "IF"
            source_name = str(action.data.get("source_action_name", "-"))
            cond_type = str(action.data.get("if_condition_type", "image_visible")).strip().lower()
            if cond_type == "ocr_compare":
                val_type = str(action.data.get("if_ocr_value_type", "number")).strip().lower()
                op = str(action.data.get("if_ocr_operator", "eq")).strip().lower()
                cmp_val = str(action.data.get("if_ocr_compare_value", "")).strip()
                op_map = {
                    "gt": ">",
                    "gte": ">=",
                    "lt": "<",
                    "lte": "<=",
                    "eq": "==",
                    "neq": "!=",
                    "contains": "contains",
                    "not_contains": "not contains",
                    "equals": "equals",
                    "not_equals": "not equals",
                }
                cond_txt = f"OCR[{val_type}] {op_map.get(op, op)} '{cmp_val}' from {source_name}"
            else:
                cond_txt = f"{source_name} image visible"
            then_action = str(action.data.get("then_action", "run_branch")).strip().lower()
            if then_action == "stop":
                then_txt = "STOP"
            elif then_action == "run_action":
                action_name = str(action.data.get("target_action_name", "") or "")
                then_txt = f"RUN ACTION {action_name or action.data.get('target_action_id', '-')}"
            else:
                tgt_idx = action.data.get("target_branch_index")
                tgt_name = ""
                try:
                    if tgt_idx is not None and 0 <= int(tgt_idx) < len(self.script_groups):
                        tgt_name = str(self.script_groups[int(tgt_idx)].get("name", f"Branch {int(tgt_idx)+1}"))
                except Exception:
                    tgt_name = ""
                then_txt = f"RUN BRANCH {tgt_name or str(tgt_idx)}"
            cooldown_ms = int(action.data.get("if_cooldown_ms", 500) or 0)
            return f"{mode_txt} [{cond_txt}] -> {then_txt} | Cooldown: {cooldown_ms}ms"

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

        if action.type == ClickType.IMAGE_RECOGNITION:
            image_path = action.data.get("image_path", "")
            target_title = action.data.get("target_title", "")
            target_part = f" | Target: {target_title}" if target_title else ""
            value = str(action.data.get("last_recognized_value", "") or "")
            status = str(action.data.get("last_recognition_status", "") or "")
            if status and status != "ok":
                value_part = f" | OCR: {status}"
            elif value:
                value_part = f" | OCR: {value}"
            else:
                value_part = " | OCR: (empty)"
            return f"Image Recognition: {os.path.basename(image_path)}{value_part}{target_part}"

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

    def _set_action_item_highlight(self, item: QTreeWidgetItem, highlighted: bool):
        """Apply/remove execution highlight color for one action row."""
        if item is None:
            return
        brush = QBrush(QColor("#fff3c4")) if highlighted else QBrush()
        for col in range(self.script_tree.columnCount()):
            item.setBackground(col, brush)
            widget = self.script_tree.itemWidget(item, col)
            if widget is None:
                continue
            base_style = widget.property("_base_style")
            if base_style is None:
                base_style = widget.styleSheet() or ""
                widget.setProperty("_base_style", base_style)
            if highlighted:
                extra = "background-color: #fff3c4;"
                widget.setStyleSheet(f"{base_style}; {extra}" if base_style else extra)
            else:
                widget.setStyleSheet(str(base_style))

    def _clear_execution_highlight(self):
        """Clear highlighted action row."""
        if self._highlighted_action_key is None:
            return
        prev_item = self._tree_action_items.get(self._highlighted_action_key)
        if prev_item:
            self._set_action_item_highlight(prev_item, False)
        self._highlighted_action_key = None
    
    def _on_action_executed_from_worker(self, action_index: int):
        """Forward worker-thread callback to Qt main thread."""
        self.action_executed_signal.emit(int(action_index))

    def _on_action_detail_changed_from_worker(self, action_index: int, detail_text: str):
        """Forward worker-thread detail callback to Qt main thread."""
        self.action_detail_changed_signal.emit(int(action_index), str(detail_text))

    def _on_status_changed_from_worker(self, message: str):
        """Forward worker-thread status callback to Qt main thread."""
        self.status_changed_signal.emit(str(message))
    
    def _on_action_executed_main_thread(self, action_index: int):
        """Increment and refresh one count cell in table."""
        if action_index < 0:
            return
        if action_index >= len(self._running_action_key_map):
            return
        
        key = self._running_action_key_map[action_index]
        self.action_counts[key] = int(self.action_counts.get(key, 0)) + 1

        if self._highlighted_action_key is not None and self._highlighted_action_key != key:
            prev_item = self._tree_action_items.get(self._highlighted_action_key)
            if prev_item:
                self._set_action_item_highlight(prev_item, False)

        self._highlighted_action_key = key
        item = self._tree_action_items.get(key)
        if not item:
            return

        self._updating_table = True
        try:
            item.setText(6, str(int(self.action_counts.get(key, 0))))
            self._set_action_item_highlight(item, True)
        finally:
            self._updating_table = False

    def _on_action_detail_changed_main_thread(self, action_index: int, detail_text: str):
        """Refresh one action row details from runtime updates (e.g. OCR result)."""
        if action_index < 0 or action_index >= len(self._running_action_key_map):
            return

        key = self._running_action_key_map[action_index]
        group_index, action_index_in_group = key
        if not (0 <= group_index < len(self.script_groups)):
            return
        actions = self.script_groups[group_index].get("actions", [])
        if not (0 <= action_index_in_group < len(actions)):
            return
        entry = actions[action_index_in_group]
        action = entry.get("action")
        if not isinstance(action, ClickAction):
            return
        if action.type != ClickType.IMAGE_RECOGNITION:
            return

        text = str(detail_text or "")
        if text.startswith("VALUE::"):
            action.data["last_recognition_status"] = "ok"
            action.data["last_recognized_value"] = str(text[7:])
        elif text.startswith("ERROR::"):
            action.data["last_recognition_status"] = str(text[7:])
            action.data["last_recognized_value"] = ""
        else:
            action.data["last_recognition_status"] = str(text)

        item = self._tree_action_items.get(key)
        if item:
            self._updating_table = True
            try:
                item.setText(7, self._build_action_details(action))
            finally:
                self._updating_table = False
    
    def _is_recording_active(self) -> bool:
        """Check whether any recording mode is active."""
        if self.position_recorder and self.position_recorder.is_recording:
            return True
        if self.image_recording_manager and self.image_recording_manager.is_recording:
            return True
        if self._screen_recording_active:
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
        if self._screen_recording_active:
            self._stop_screen_recording()
    
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
        self.on_refresh_target_geometry()
        self._update_target_label()
        self.statusBar.showMessage(f"Target selected: {selected.title}")

    def on_select_target_window_dropped(self, drop_x: int, drop_y: int):
        """Quick select target by dragging Select Target button onto a window."""
        try:
            hwnd = win32gui.WindowFromPoint((int(drop_x), int(drop_y)))
        except Exception:
            self.statusBar.showMessage("Cannot detect window at drop position")
            return
        if not hwnd:
            self.statusBar.showMessage("No window detected at drop position")
            return

        try:
            root_hwnd = win32gui.GetAncestor(int(hwnd), win32con.GA_ROOT)
            if not root_hwnd:
                root_hwnd = int(hwnd)
        except Exception:
            root_hwnd = int(hwnd)

        try:
            own_hwnd = int(self.winId())
        except Exception:
            own_hwnd = 0

        if int(root_hwnd) == own_hwnd:
            self.statusBar.showMessage("Drop onto target app window (not ITM AutoClicker)")
            return

        try:
            if not win32gui.IsWindow(int(root_hwnd)):
                self.statusBar.showMessage("Dropped window is not valid")
                return
            title = win32gui.GetWindowText(int(root_hwnd)) or "Untitled"
            class_name = win32gui.GetClassName(int(root_hwnd))
            self.selected_target_window = Window(int(root_hwnd), str(title), str(class_name))
            self.on_refresh_target_geometry()
            self._update_target_label()
            self.statusBar.showMessage(f"Target selected by drag: {title}")
        except Exception as e:
            self.statusBar.showMessage(f"Failed to select target by drag: {e}")
    
    def _update_target_label(self):
        """Update target info label in main tab"""
        if not self.target_info_label:
            return
        
        if self.selected_target_window:
            info = f"{self.selected_target_window.title} (hwnd={self.selected_target_window.hwnd})"
            rect = self._get_target_window_rect()
            if rect:
                x, y, w, h = rect
                info += f" [{x}, {y}, {w}x{h}]"
            self.target_info_label.setText(info)
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

    def _get_target_window_rect(self) -> tuple[int, int, int, int] | None:
        """Get target window rect as (x, y, w, h)."""
        if not self.selected_target_window:
            return None
        try:
            hwnd = int(self.selected_target_window.hwnd)
            if not win32gui.IsWindow(hwnd):
                return None
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = max(0, int(right - left))
            height = max(0, int(bottom - top))
            return int(left), int(top), int(width), int(height)
        except Exception:
            return None

    def on_refresh_target_geometry(self):
        """Read current target window geometry into X/Y/W/H controls."""
        rect = self._get_target_window_rect()
        if not rect:
            self.statusBar.showMessage("Cannot read target geometry. Please select a valid target window.")
            return
        x, y, w, h = rect
        if self.target_x_spin:
            self.target_x_spin.setValue(int(x))
        if self.target_y_spin:
            self.target_y_spin.setValue(int(y))
        if self.target_w_spin:
            self.target_w_spin.setValue(int(w))
        if self.target_h_spin:
            self.target_h_spin.setValue(int(h))
        self._update_target_label()
        self.statusBar.showMessage(f"Target geometry refreshed: ({x}, {y}, {w}x{h})")

    def on_fix_target_geometry(self):
        """Apply X/Y/W/H controls to target window."""
        if not self.selected_target_window:
            self.statusBar.showMessage("Please select target window first.")
            return
        try:
            hwnd = int(self.selected_target_window.hwnd)
            if not win32gui.IsWindow(hwnd):
                self.statusBar.showMessage("Selected target is no longer valid. Please reselect.")
                return

            x = int(self.target_x_spin.value()) if self.target_x_spin else 0
            y = int(self.target_y_spin.value()) if self.target_y_spin else 0
            w = int(self.target_w_spin.value()) if self.target_w_spin else 800
            h = int(self.target_h_spin.value()) if self.target_h_spin else 600
            w = max(100, w)
            h = max(100, h)

            win32gui.MoveWindow(hwnd, x, y, w, h, True)
            self.on_refresh_target_geometry()
            self.statusBar.showMessage(f"Target window fixed to ({x}, {y}, {w}x{h})")
        except Exception as e:
            QMessageBox.warning(self, "Fix Target Failed", f"Unable to move/resize target window:\n{e}")

    def _build_target_window_payload(self) -> dict | None:
        """Build target-window metadata for script save."""
        if not self.selected_target_window:
            return None
        payload = {
            "hwnd": int(self.selected_target_window.hwnd),
            "title": str(self.selected_target_window.title or ""),
        }
        if self.target_x_spin and self.target_y_spin and self.target_w_spin and self.target_h_spin:
            payload.update({
                "x": int(self.target_x_spin.value()),
                "y": int(self.target_y_spin.value()),
                "width": int(self.target_w_spin.value()),
                "height": int(self.target_h_spin.value()),
            })
        else:
            rect = self._get_target_window_rect()
            if rect:
                x, y, w, h = rect
                payload.update({"x": x, "y": y, "width": w, "height": h})
        return payload

    def _load_target_window_payload(self, data: dict):
        """Restore target-window metadata from loaded script."""
        target_data = data.get("target_window") if isinstance(data, dict) else None
        if not isinstance(target_data, dict):
            return

        hwnd = target_data.get("hwnd")
        title = str(target_data.get("title", "")).strip()
        restored_window = None
        try:
            if hwnd is not None and win32gui.IsWindow(int(hwnd)):
                class_name = win32gui.GetClassName(int(hwnd))
                live_title = win32gui.GetWindowText(int(hwnd)) or title
                restored_window = Window(int(hwnd), live_title, class_name)
        except Exception:
            restored_window = None

        # Fallback: auto-find by title when hwnd changed.
        if restored_window is None and title:
            try:
                windows = WindowPicker.get_windows()
                title_norm = title.casefold()
                exact = [w for w in windows if (w.title or "").strip().casefold() == title_norm]
                partial = [w for w in windows if title_norm and title_norm in (w.title or "").casefold()]
                found = exact[0] if exact else (partial[0] if partial else None)
                if found:
                    restored_window = found
            except Exception:
                restored_window = None

        if restored_window:
            self.selected_target_window = restored_window
        elif title or hwnd is not None:
            # Keep UI informative even if old hwnd is no longer valid.
            try:
                self.selected_target_window = Window(int(hwnd or 0), title or "Saved target", "")
            except Exception:
                self.selected_target_window = None

        x = target_data.get("x")
        y = target_data.get("y")
        width = target_data.get("width")
        height = target_data.get("height")
        try:
            if self.target_x_spin and "x" in target_data:
                self.target_x_spin.setValue(int(target_data.get("x", 0)))
            if self.target_y_spin and "y" in target_data:
                self.target_y_spin.setValue(int(target_data.get("y", 0)))
            if self.target_w_spin and "width" in target_data:
                self.target_w_spin.setValue(max(100, int(target_data.get("width", 100))))
            if self.target_h_spin and "height" in target_data:
                self.target_h_spin.setValue(max(100, int(target_data.get("height", 100))))
        except Exception:
            pass

        # Auto-fix target window geometry after load when window is found.
        if restored_window and all(v is not None for v in (x, y, width, height)):
            try:
                hwnd_int = int(restored_window.hwnd)
                if win32gui.IsWindow(hwnd_int):
                    win32gui.MoveWindow(
                        hwnd_int,
                        int(x),
                        int(y),
                        max(100, int(width)),
                        max(100, int(height)),
                        True,
                    )
            except Exception:
                pass

        self._update_target_label()
        if restored_window:
            if all(v is not None for v in (x, y, width, height)):
                self.statusBar.showMessage(f"Loaded target and fixed geometry: {restored_window.title}")
            else:
                self.statusBar.showMessage(f"Loaded target metadata: {restored_window.title}")
        else:
            self.statusBar.showMessage("Loaded target geometry from script. Please reselect target window if needed.")
    
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
                elif action.type in (ClickType.IMAGE, ClickType.IMAGE_DIRECT, ClickType.IMAGE_RECOGNITION):
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
        if mode == "mouse_scroll":
            steps = int(data.get("scroll_clicks", 0) or 0)
            if steps == 0:
                return "SCROLL"
            if steps > 0:
                return f"SCROLL UP x{steps}"
            return f"SCROLL DOWN x{abs(steps)}"
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
        if self._screen_recording_active:
            self._stop_screen_recording()
        self._screen_record_elapsed_timer.stop()
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
