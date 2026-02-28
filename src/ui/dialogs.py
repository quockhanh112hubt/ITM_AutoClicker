"""
Dialog components for the GUI
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup, QDialogButtonBox
)
from src.click_script import ClickType


class SettingsDialog(QDialog):
    """Dialog for configuring click type
    
    Allows user to select between Position-based, Image-based, or Direct Image click modes.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the settings dialog
        
        Args:
            parent: Parent widget
        """
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
        """
        Get selected click type
        
        Returns:
            ClickType: Selected click type (POSITION, IMAGE, or IMAGE_DIRECT)
        """
        if self.radio_position.isChecked():
            return ClickType.POSITION
        elif self.radio_image_direct.isChecked():
            return ClickType.IMAGE_DIRECT
        else:
            return ClickType.IMAGE
