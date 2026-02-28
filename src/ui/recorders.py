"""
Recorder components for position and image-based click recording
"""
from pynput import mouse
from src.keyboard_listener import KeyboardListener


class PositionRecorder:
    """Helper class for recording positions
    
    Records mouse positions using keyboard bindings (Page Up/Page Down/ESC).
    Supports custom action selection via callbacks.
    """
    
    def __init__(self, on_position_recorded=None, on_cancel=None, on_choose_action=None, key_bindings=None):
        """
        Initialize the position recorder
        
        Args:
            on_position_recorded: Callback when position is recorded - called with count
            on_cancel: Callback when recording cancelled - called with positions list
            on_choose_action: Callback to choose custom action - called with (x, y) or ()
            key_bindings: Dictionary mapping logical keys to physical keys
        """
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
    """Helper class for recording image-based clicks
    
    Records image regions and click positions using keyboard bindings.
    """
    
    def __init__(self, on_image_saved=None, on_cancel=None):
        """
        Initialize the image recorder
        
        Args:
            on_image_saved: Callback when image is saved
            on_cancel: Callback when recording cancelled - called with images list
        """
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
