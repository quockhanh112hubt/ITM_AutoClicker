"""
Window Picker - Select target window for image capture
Allows user to choose a window and capture regions within it
"""
import win32gui
import win32con
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QSpinBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from src.logger import AppLogger


class Window:
    """Represents a window on the system"""
    
    def __init__(self, hwnd: int, title: str, class_name: str):
        self.hwnd = hwnd
        self.title = title
        self.class_name = class_name
    
    def get_rect(self) -> Tuple[int, int, int, int]:
        """Get window rectangle (left, top, right, bottom)"""
        rect = win32gui.GetWindowRect(self.hwnd)
        return rect
    
    def get_client_rect(self) -> Tuple[int, int, int, int]:
        """Get client area rectangle"""
        rect = win32gui.GetClientRect(self.hwnd)
        return (0, 0, rect[2], rect[3])
    
    def is_visible(self) -> bool:
        """Check if window is visible"""
        return win32gui.IsWindowVisible(self.hwnd)
    
    def get_display_name(self) -> str:
        """Get display name for the window"""
        if self.title:
            return f"{self.title} ({self.class_name})"
        else:
            return f"[Unnamed] ({self.class_name})"
    
    def __repr__(self):
        return self.get_display_name()


class WindowPicker:
    """Utility to get list of windows"""
    
    @staticmethod
    def get_windows() -> List[Window]:
        """Get list of visible windows"""
        windows = []
        
        def enum_windows(hwnd, lParam):
            # Only get visible windows
            if win32gui.IsWindowVisible(hwnd):
                # Ignore some system windows
                class_name = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                
                # Skip empty titles and certain system classes
                if title and class_name not in ['Shell_TrayWnd', 'Button']:
                    window = Window(hwnd, title, class_name)
                    windows.append(window)
            return True
        
        win32gui.EnumWindows(enum_windows, None)
        return windows


class WindowPickerDialog(QDialog):
    """Dialog to select target window"""
    
    window_selected = pyqtSignal(Window)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Target Window")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        self.selected_window: Optional[Window] = None
        
        self.setup_ui()
        self.refresh_windows()
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Select a window to capture images from:")
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Window list
        self.window_list = QListWidget()
        self.window_list.itemDoubleClicked.connect(self.on_window_double_clicked)
        layout.addWidget(self.window_list)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Refresh button
        btn_refresh = QPushButton("Refresh Windows")
        btn_refresh.clicked.connect(self.refresh_windows)
        button_layout.addWidget(btn_refresh)
        
        button_layout.addStretch()
        
        # Dialog buttons
        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.on_accept)
        dialog_buttons.rejected.connect(self.reject)
        button_layout.addWidget(dialog_buttons)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def refresh_windows(self):
        """Refresh the list of windows"""
        self.window_list.clear()
        windows = WindowPicker.get_windows()
        AppLogger.debug(f"Found {len(windows)} windows")
        
        for i, window in enumerate(windows):
            # Safely print window info (handle Unicode)
            try:
                safe_title = window.title.encode('utf-8', errors='replace').decode('utf-8')
                AppLogger.debug(f"  [{i}] hwnd={window.hwnd}, title={safe_title}")
            except:
                AppLogger.debug(f"  [{i}] hwnd={window.hwnd}")
            
            item = QListWidgetItem(window.get_display_name())
            item.setData(Qt.ItemDataRole.UserRole, window)
            self.window_list.addItem(item)
    
    def on_window_double_clicked(self, item):
        """Handle window double-clicked"""
        AppLogger.debug(f"Window double-clicked: {item.text()}")
        self.on_accept()
    
    def on_accept(self):
        """Handle OK button"""
        current_item = self.window_list.currentItem()
        AppLogger.debug(f"on_accept called, currentItem={current_item}")
        
        if current_item:
            self.selected_window = current_item.data(Qt.ItemDataRole.UserRole)
            try:
                safe_title = self.selected_window.title.encode('utf-8', errors='replace').decode('utf-8')
                AppLogger.debug(f"Selected window: hwnd={self.selected_window.hwnd}, title={safe_title}")
            except:
                AppLogger.debug(f"Selected window: hwnd={self.selected_window.hwnd}")
            self.window_selected.emit(self.selected_window)
            self.accept()
        else:
            AppLogger.debug(f"No window selected!")
            # Show error - but we'll let accept handle it
            self.accept()
    
    def get_selected_window(self) -> Optional[Window]:
        """Get the selected window"""
        return self.selected_window
