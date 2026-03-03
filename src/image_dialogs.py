"""
Image Recording Dialog - Shows captured image for user confirmation
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, pyqtSignal
import cv2
import numpy as np


class ImageConfirmationDialog(QDialog):
    """Dialog to show captured image and ask for confirmation"""
    
    image_confirmed = pyqtSignal()
    image_rejected = pyqtSignal()
    
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Captured Image")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        try:
            if parent and hasattr(parent, "is_always_on_top_enabled") and parent.is_always_on_top_enabled():
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception:
            pass
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel("Please review the captured image.\nClick OK to continue or Cancel to retake.")
        layout.addWidget(instructions)
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load and display image
        try:
            # Read image with OpenCV
            img = cv2.imread(image_path)
            if img is not None:
                # Convert BGR to RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                
                # Convert to QImage
                h, w, ch = img_rgb.shape
                bytes_per_line = ch * w
                qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                # Scale to fit dialog
                pixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaledToWidth(550, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            self.image_label.setText(f"Error loading image: {e}")
        
        layout.addWidget(self.image_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        btn_ok = QPushButton("OK - Use This Image")
        btn_ok.clicked.connect(self.on_ok)
        button_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("Cancel - Retake")
        btn_cancel.clicked.connect(self.on_cancel)
        button_layout.addWidget(btn_cancel)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_ok(self):
        """User confirmed the image"""
        self.image_confirmed.emit()
        self.accept()
    
    def on_cancel(self):
        """User wants to retake the image"""
        self.image_rejected.emit()
        self.reject()


class ClickPositionDialog(QDialog):
    """Dialog to ask user to position mouse for click location"""
    
    position_confirmed = pyqtSignal()
    recording_cancelled = pyqtSignal()
    
    def __init__(self, image_num: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Click Position for Image {image_num}")
        self.setModal(False)  # Non-modal so keyboard listener can still work
        self.setMinimumWidth(500)
        try:
            if parent and hasattr(parent, "is_always_on_top_enabled") and parent.is_always_on_top_enabled():
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception:
            pass
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(
            f"Image {image_num} captured!\n\n"
            "Now position your mouse at the click location and press PAGE UP to record Left Click.\n"
            "Press PAGE DOWN to choose advanced action and record.\n"
            "You can click anywhere on the screen - it doesn't have to be on the image.\n\n"
            "Press ESC to cancel recording."
        )
        layout.addWidget(instructions)
        
        # Info label
        self.info_label = QLabel("Waiting for PAGE UP...")
        layout.addWidget(self.info_label)
        
        # Close button
        btn_close = QPushButton("Close This Dialog (still recording)")
        btn_close.clicked.connect(self.on_close_clicked)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
    
    def on_close_clicked(self):
        """User clicked close button"""
        self.close()
    
    def update_position(self, x: int, y: int, mouse_button: str = "left"):
        """Update display with recorded position"""
        button_label = "RIGHT" if str(mouse_button).lower() == "right" else "LEFT"
        self.info_label.setText(f"OK - {button_label} position recorded: ({x}, {y})")
        self.position_confirmed.emit()
        # Auto-close after position confirmed
        self.accept()
    
    def on_recording_cancelled(self):
        """Recording was cancelled with ESC"""
        self.recording_cancelled.emit()
        self.reject()

