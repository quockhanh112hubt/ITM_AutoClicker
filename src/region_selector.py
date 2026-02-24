"""
Region selector for image-based clicks
"""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtCore import QPoint
from PIL import ImageGrab


class RegionSelectorWindow(QWidget):
    """Window for selecting a region on screen"""
    
    region_selected = pyqtSignal(int, int, int, int)  # x1, y1, x2, y2
    
    def __init__(self, callback=None):
        super().__init__()
        self.callback = callback
        self.setWindowTitle("Region Selector")
        self.setGeometry(0, 0, 1920, 1080)  # Assume max resolution
        
        # Fullscreen and transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Selection rectangle
        self.start_point = None
        self.end_point = None
        self.is_selecting = False
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        self.start_point = event.pos()
        self.is_selecting = True
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self.is_selecting:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.end_point = event.pos()
        self.is_selecting = False
        
        # Get selected region
        x1 = min(self.start_point.x(), self.end_point.x())
        y1 = min(self.start_point.y(), self.end_point.y())
        x2 = max(self.start_point.x(), self.end_point.x())
        y2 = max(self.start_point.y(), self.end_point.y())
        
        # Close window and call callback
        self.close()
        if self.callback:
            self.callback(x1, y1, x2, y2)
    
    def paintEvent(self, event):
        """Paint the selection rectangle"""
        if self.start_point and self.end_point and self.is_selecting:
            painter = QPainter(self)
            
            # Draw semi-transparent overlay
            painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
            
            # Draw selection rectangle
            rect = QRect(self.start_point, self.end_point)
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw dimensions
            width = abs(self.end_point.x() - self.start_point.x())
            height = abs(self.end_point.y() - self.start_point.y())
            painter.drawText(self.end_point.x() + 10, self.end_point.y() + 10, f"{width}x{height}")
    
    def keyPressEvent(self, event):
        """Handle key press - ESC to cancel"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
