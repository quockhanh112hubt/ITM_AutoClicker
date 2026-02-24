"""
Keyboard listener for global hotkeys
Monitors Page Up, ESC, and END keys without blocking mouse
"""
from pynput import keyboard
from typing import Callable, Optional
import threading


class KeyboardListener:
    """Global keyboard listener for hotkeys"""
    
    def __init__(self):
        self.listener: Optional[keyboard.Listener] = None
        self.callbacks = {
            'page_up': [],
            'esc': [],
            'end': []
        }
        self._lock = threading.Lock()
    
    def on_press(self, key):
        """Handle key press events"""
        try:
            with self._lock:
                if key == keyboard.Key.page_up:
                    for callback in self.callbacks['page_up']:
                        callback()
                elif key == keyboard.Key.esc:
                    for callback in self.callbacks['esc']:
                        callback()
                elif key == keyboard.Key.end:
                    for callback in self.callbacks['end']:
                        callback()
        except AttributeError:
            pass
    
    def register_callback(self, key: str, callback: Callable):
        """Register a callback for a specific key"""
        if key in self.callbacks:
            self.callbacks[key].append(callback)
    
    def unregister_callback(self, key: str, callback: Callable):
        """Unregister a callback"""
        if key in self.callbacks and callback in self.callbacks[key]:
            self.callbacks[key].remove(callback)
    
    def start(self):
        """Start listening to keyboard events"""
        if self.listener is None:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()
    
    def stop(self):
        """Stop listening to keyboard events"""
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
    
    def is_running(self) -> bool:
        """Check if listener is running"""
        return self.listener is not None and self.listener.is_alive()
