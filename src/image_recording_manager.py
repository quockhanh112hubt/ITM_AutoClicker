"""
Image Recording Manager - Handles the complete flow of image-based click recording
"""
from typing import Callable, List, Tuple, Optional
import os
import time
from PyQt6.QtWidgets import QMessageBox
from src.keyboard_listener import KeyboardListener
from src.image_matcher import ImageMatcher
from src.window_picker import WindowPickerDialog, Window
from src.window_region_selector import WindowRegionSelector
from src.image_dialogs import ImageConfirmationDialog, ClickPositionDialog
from pynput import mouse
from PIL import Image


class ImageRecordingManager:
    """Manages the complete image recording workflow"""
    
    def __init__(self, on_complete: Callable = None, on_cancel: Callable = None, parent=None):
        """
        Initialize image recording manager
        
        Args:
            on_complete: Callback when recording is complete
            on_cancel: Callback when recording is cancelled
            parent: Parent widget for dialogs
        """
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.parent = parent
        
        self.recorded_images: List[Tuple[str, int, int]] = []  # (image_path, click_x, click_y)
        self.is_recording = False
        self.current_image_num = 0
        
        self.keyboard_listener = KeyboardListener()
        self.region_selector: Optional[WindowRegionSelector] = None
        self.image_dialogs = []
        self.target_window: Optional[Window] = None
        
    def start(self):
        """Start image recording process"""
        self.is_recording = True
        self.recorded_images.clear()
        self.current_image_num = 0
        
        # Register keyboard callbacks
        self.keyboard_listener.register_callback('esc', self._on_esc)
        self.keyboard_listener.register_callback('page_up', self._on_page_up)
        self.keyboard_listener.start()
        
        # First, let user select target window
        self._show_window_picker()
    
    def _show_window_picker(self):
        """Show window picker dialog"""
        dialog = WindowPickerDialog(parent=self.parent)
        
        if dialog.exec():
            self.target_window = dialog.get_selected_window()
            if self.target_window:
                # Start recording in selected window
                self._start_next_image()
            else:
                # User didn't select a window
                self._finish_recording(cancelled=True)
        else:
            # User cancelled the window picker
            self._finish_recording(cancelled=True)
    
    def _start_next_image(self):
        """Start recording next image"""
        if not self.is_recording or not self.target_window:
            return
        
        self.current_image_num += 1
        self._show_region_selector()
    
    def _show_region_selector(self):
        """Show region selector within target window"""
        if not self.target_window:
            return
        
        self.region_selector = WindowRegionSelector(
            self.target_window.hwnd,
            on_region_selected=self._on_region_selected
        )
        
        # Connect signal and show
        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.show()
    
    def _on_region_selected(self, x1: int, y1: int, x2: int, y2: int):
        """Handle region selected from overlay"""
        if not self.is_recording:
            return
        
        print(f"[DEBUG] Region selected: ({x1}, {y1}) to ({x2}, {y2})")
        
        # Create images directory
        images_dir = "scripts/images"
        os.makedirs(images_dir, exist_ok=True)
        
        # Save captured image
        image_path = os.path.join(images_dir, f"image_{self.current_image_num}.png")
        print(f"[DEBUG] Capturing region and saving to: {image_path}")
        ImageMatcher.capture_region(x1, y1, x2, y2, image_path)
        print(f"[DEBUG] Image saved successfully")
        
        # Show confirmation dialog
        self._show_confirmation_dialog(image_path)
    
    def _show_confirmation_dialog(self, image_path: str):
        """Show dialog to confirm captured image"""
        # Use non-modal dialog so keyboard listener remains active
        dialog = ImageConfirmationDialog(image_path, parent=self.parent)

        def on_confirmed():
            try:
                dialog.close()
            except:
                pass
            # Proceed to ask for click position
            self._show_click_position_dialog(image_path)

        def on_rejected():
            try:
                dialog.close()
            except:
                pass
            # Delete the rejected image and retake
            try:
                os.remove(image_path)
            except:
                pass
            self._start_next_image()

        dialog.image_confirmed.connect(on_confirmed)
        dialog.image_rejected.connect(on_rejected)

        self.image_dialogs.append(dialog)
        dialog.show()
    
    def _show_click_position_dialog(self, image_path: str):
        """Show dialog asking user to set click position"""
        if not self.is_recording:
            return
        # Non-modal click-position dialog so global keyboard listener can work
        dialog = ClickPositionDialog(self.current_image_num, parent=self.parent)
        self.image_dialogs.append(dialog)

        # Store current image path and dialog
        self._waiting_for_click_position = True
        self._waiting_image_path = image_path

        # If the dialog emits that recording was cancelled, handle it
        def on_cancelled():
            try:
                dialog.close()
            except:
                pass
            self._waiting_for_click_position = False
            # remove the last image saved (if exists)
            try:
                os.remove(image_path)
            except:
                pass
            # Ask whether to continue
            self._ask_continue_recording()

        dialog.recording_cancelled.connect(on_cancelled)

        dialog.show()
    
    def _on_page_up(self):
        """Handle PAGE UP key press"""
        if not self.is_recording:
            return
        
        # Get mouse position
        mouse_controller = mouse.Controller()
        x, y = mouse_controller.position
        
        # If waiting for click position, record it
        if hasattr(self, '_waiting_for_click_position') and self._waiting_for_click_position:
            # Store the image with click position
            self.recorded_images.append((
                self._waiting_image_path,
                int(x),
                int(y)
            ))
            
            self._waiting_for_click_position = False
            
            # Update dialog if it exists
            if self.image_dialogs:
                last_dialog = self.image_dialogs[-1]
                if isinstance(last_dialog, ClickPositionDialog):
                    last_dialog.update_position(int(x), int(y))
                    last_dialog.close()
            
            # Ask if user wants to continue with more images
            self._ask_continue_recording()
    
    def _ask_continue_recording(self):
        """Ask user if they want to record more images"""
        from PyQt6.QtWidgets import QMessageBox, QApplication
        
        # Get the main window
        app = QApplication.instance()
        if app is None:
            return
        
        reply = QMessageBox.question(
            None,
            "Continue Recording?",
            f"Image {self.current_image_num} recorded successfully!\n\n"
            f"Do you want to record another image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._start_next_image()
        else:
            self._finish_recording()
    
    def _on_esc(self):
        """Handle ESC key press"""
        if self.is_recording:
            self._finish_recording()
    
    def _finish_recording(self, cancelled: bool = False):
        """Finish recording and clean up"""
        self.is_recording = False
        
        # Unregister callbacks
        self.keyboard_listener.unregister_callback('esc', self._on_esc)
        self.keyboard_listener.unregister_callback('page_up', self._on_page_up)
        self.keyboard_listener.stop()
        
        # Close dialogs
        for dialog in self.image_dialogs:
            try:
                dialog.close()
            except:
                pass
        self.image_dialogs.clear()
        
        # Call completion callback
        if self.on_complete:
            self.on_complete(self.recorded_images)
    
    def cancel(self):
        """Cancel recording"""
        self.is_recording = False
        
        # Cleanup
        self.keyboard_listener.unregister_callback('esc', self._on_esc)
        self.keyboard_listener.unregister_callback('page_up', self._on_page_up)
        self.keyboard_listener.stop()
        
        for dialog in self.image_dialogs:
            try:
                dialog.close()
            except:
                pass
        self.image_dialogs.clear()
        
        # Call cancel callback
        if self.on_cancel:
            self.on_cancel()
