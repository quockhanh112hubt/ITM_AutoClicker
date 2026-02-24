"""
Window-based Region Selector - Select regions within a specific window
"""
import win32gui
import win32con
from typing import Callable, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt6.QtCore import QTimer
from PIL import ImageGrab
import os


class WindowRegionSelector(QWidget):
    """Overlay to select regions within a specific window"""
    
    region_selected = pyqtSignal(int, int, int, int)  # x1, y1, x2, y2
    
    def __init__(self, window_hwnd: int, on_region_selected: Callable = None):
        super().__init__()
        
        self.window_hwnd = window_hwnd
        self.on_region_selected = on_region_selected
        
        # Get window position and size - use screen coordinates
        rect = win32gui.GetWindowRect(window_hwnd)
        window_x1, window_y1, window_x2, window_y2 = rect
        
        print(f"[DEBUG WindowRegionSelector] Window hwnd={window_hwnd}")
        print(f"[DEBUG WindowRegionSelector] Window rect from GetWindowRect: ({window_x1}, {window_y1}, {window_x2}, {window_y2})")
        
        # Store original window rect (with negative coords if any)
        # These will be used for capture coordinates
        self.window_x1_orig = window_x1
        self.window_y1_orig = window_y1
        self.window_x2_orig = window_x2
        self.window_y2_orig = window_y2
        
        # Calculate size (always positive)
        window_width = window_x2 - window_x1
        window_height = window_y2 - window_y1
        
        # For widget positioning, clamp top-left to valid range but keep size
        self.window_x1 = max(0, window_x1)
        self.window_y1 = max(0, window_y1)
        
        # Size stays the same (not clamped individually)
        self.window_width = window_width
        self.window_height = window_height
        
        print(f"[DEBUG WindowRegionSelector] Window size: {self.window_width}x{self.window_height}")
        print(f"[DEBUG WindowRegionSelector] Widget position: ({self.window_x1}, {self.window_y1})")
        
        # Selection state
        self.start_pos: Optional[QPoint] = None
        self.end_pos: Optional[QPoint] = None
        self.is_selecting = False
        
        # Setup widget to overlay on window
        self.setGeometry(
            self.window_x1,
            self.window_y1,
            self.window_width,
            self.window_height
        )
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Styling - completely transparent background
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        
        # Enable mouse tracking to capture all mouse events
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.raise_()
        self.activateWindow()
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = True
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self.is_selecting:
            self.end_pos = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_pos = event.pos()
            self.on_selection_complete()
    
    def keyPressEvent(self, event):
        """Handle key press"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
    
    def paintEvent(self, event):
        """Draw selection rectangle"""
        painter = QPainter(self)
        
        # Enable anti-aliasing for smoother graphics
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Draw semi-transparent background to indicate selectable area
        # Use very light overlay so we can see the window underneath
        overlay_color = QColor(0, 0, 0, 15)  # Very light, nearly invisible
        painter.fillRect(self.rect(), overlay_color)
        
        if self.start_pos and self.end_pos and self.is_selecting:
            # Draw selection rectangle
            x1 = min(self.start_pos.x(), self.end_pos.x())
            y1 = min(self.start_pos.y(), self.end_pos.y())
            x2 = max(self.start_pos.x(), self.end_pos.x())
            y2 = max(self.start_pos.y(), self.end_pos.y())
            
            width = x2 - x1
            height = y2 - y1
            
            # Draw selection box with bright green outline
            rect = QRect(x1, y1, width, height)
            
            # Draw outer green border
            pen = QPen(QColor(0, 255, 0), 4)
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw inner white border for better visibility
            pen_inner = QPen(QColor(255, 255, 255), 1)
            painter.setPen(pen_inner)
            painter.drawRect(rect.adjusted(2, 2, -2, -2))
            
            # Draw dimensions text with background
            if width > 0 and height > 0:
                text = f"{width} x {height}"
                font = QFont()
                font.setPointSize(14)
                font.setBold(True)
                painter.setFont(font)
                
                # Draw text background
                text_rect = painter.fontMetrics().boundingRect(text)
                text_x = x1 + 8
                text_y = y1 + 30
                text_rect.moveTo(text_x - 4, text_y - 18)
                text_rect.adjust(-4, -2, 4, 2)
                
                # Background for text
                painter.fillRect(text_rect, QColor(0, 255, 0, 200))
                
                # Draw text
                painter.setPen(QPen(QColor(0, 0, 0)))
                painter.drawText(text_x, text_y, text)
    
    def on_selection_complete(self):
        """Handle selection complete"""
        if self.start_pos and self.end_pos:
            x1 = min(self.start_pos.x(), self.end_pos.x())
            y1 = min(self.start_pos.y(), self.end_pos.y())
            x2 = max(self.start_pos.x(), self.end_pos.x())
            y2 = max(self.start_pos.y(), self.end_pos.y())
            
            # Convert to global coordinates using ORIGINAL window rect
            # (window_x1_orig may be negative due to DPI scaling, that's OK)
            global_x1 = self.window_x1_orig + x1
            global_y1 = self.window_y1_orig + y1
            global_x2 = self.window_x1_orig + x2
            global_y2 = self.window_y1_orig + y2
            
            print(f"[DEBUG] Window rect (original): ({self.window_x1_orig}, {self.window_y1_orig}, {self.window_x2_orig}, {self.window_y2_orig})")
            print(f"[DEBUG] Selection local: ({x1}, {y1}, {x2}, {y2})")
            print(f"[DEBUG] Selection global: ({global_x1}, {global_y1}, {global_x2}, {global_y2})")
            
            # Debug: Save a test screenshot of the entire window
            try:
                from PIL import ImageGrab
                test_window = ImageGrab.grab(bbox=(self.window_x1, self.window_y1, self.window_x2, self.window_y2))
                test_window.save("test_window_capture.png")
                print(f"[DEBUG] Saved test_window_capture.png - size: {test_window.size}")
                
                test_region = ImageGrab.grab(bbox=(global_x1, global_y1, global_x2, global_y2))
                test_region.save("test_region_capture.png")
                print(f"[DEBUG] Saved test_region_capture.png - size: {test_region.size}")
            except Exception as e:
                print(f"[DEBUG] Error saving test images: {e}")
            
            # Close overlay IMMEDIATELY to allow capture
            self.close()
            
            # Now call the callback AFTER closing the overlay
            self.region_selected.emit(global_x1, global_y1, global_x2, global_y2)
            
            if self.on_region_selected:
                self.on_region_selected(global_x1, global_y1, global_x2, global_y2)
