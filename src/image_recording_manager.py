"""
Image Recording Manager - Handles the complete flow of image-based click recording
"""
from typing import Callable, List, Tuple, Optional
import os
import time
import re
from PyQt6.QtWidgets import QMessageBox
from src.keyboard_listener import KeyboardListener
from src.image_matcher import ImageMatcher
from src.window_picker import WindowPickerDialog, Window
from src.window_region_selector import WindowRegionSelector
from src.image_dialogs import ImageConfirmationDialog, ClickPositionDialog
from pynput import mouse
from PIL import Image
import win32gui


class ImageRecordingManager:
    """Manages the complete image recording workflow"""
    
    def __init__(
        self,
        on_complete: Callable = None,
        on_cancel: Callable = None,
        on_image_recorded: Callable = None,
        parent=None
    ):
        """
        Initialize image recording manager
        
        Args:
            on_complete: Callback when recording is complete
            on_cancel: Callback when recording is cancelled
            parent: Parent widget for dialogs
        """
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.on_image_recorded = on_image_recorded
        self.parent = parent
        
        self.recorded_images: List[dict] = []
        self.is_recording = False
        self.current_image_num = 0
        
        self.keyboard_listener = KeyboardListener()
        self.region_selector: Optional[WindowRegionSelector] = None
        self.image_dialogs = []
        self.target_window: Optional[Window] = None
        
    def start(self, target_window: Optional[Window] = None):
        """Start image recording process"""
        self.is_recording = True
        self.recorded_images.clear()
        self.current_image_num = self._get_last_image_index()
        self.target_window = target_window
        
        # Register keyboard callbacks
        self.keyboard_listener.register_callback('esc', self._on_esc)
        self.keyboard_listener.register_callback('page_up', self._on_page_up)
        self.keyboard_listener.start()
        
        # Use pre-selected target if provided, otherwise ask user.
        if self.target_window:
            self._start_next_image()
        else:
            self._show_window_picker()
    
    def _get_last_image_index(self) -> int:
        """Get the highest existing image index in scripts/images."""
        images_dir = "scripts/images"
        if not os.path.isdir(images_dir):
            return 0
        
        max_index = 0
        pattern = re.compile(r"^image_(\d+)\.png$", re.IGNORECASE)
        for filename in os.listdir(images_dir):
            match = pattern.match(filename)
            if match:
                idx = int(match.group(1))
                if idx > max_index:
                    max_index = idx
        return max_index
    
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
        
        # Use Qt signal only to avoid duplicate callbacks.
        self.region_selector = WindowRegionSelector(self.target_window.hwnd)
        
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
            # Continue with next image capture
            self._start_next_image()

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
            click_client_x = None
            click_client_y = None
            target_hwnd = None
            target_title = ""
            if self.target_window:
                target_hwnd = int(self.target_window.hwnd)
                target_title = self.target_window.title
                try:
                    click_client_x, click_client_y = win32gui.ScreenToClient(target_hwnd, (int(x), int(y)))
                except Exception:
                    click_client_x = None
                    click_client_y = None

            recorded = {
                "image_path": self._waiting_image_path,
                "click_x": int(x),
                "click_y": int(y),
                "click_client_x": click_client_x,
                "click_client_y": click_client_y,
                "target_hwnd": target_hwnd,
                "target_title": target_title
            }
            self.recorded_images.append(recorded)
            
            self._waiting_for_click_position = False
            current_count = len(self.recorded_images)
            
            # Update dialog if it exists
            if self.image_dialogs:
                last_dialog = self.image_dialogs[-1]
                if isinstance(last_dialog, ClickPositionDialog):
                    last_dialog.update_position(int(x), int(y))
                    last_dialog.close()
            
            # Immediately persist each captured item through callback.
            if self.on_image_recorded:
                try:
                    self.on_image_recorded(recorded, current_count)
                except Exception as e:
                    print(f"[WARN] on_image_recorded callback failed: {e}")
            
            # Continue recording loop until user presses ESC.
            self._start_next_image()
    
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
