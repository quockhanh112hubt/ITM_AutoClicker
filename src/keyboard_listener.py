"""
Keyboard listener for global hotkeys
Monitors Page Up, ESC, and END keys without blocking mouse
"""
from pynput import keyboard
from typing import Callable, Optional
import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt


class KeyboardListener(QObject):
    """Global keyboard listener for hotkeys"""
    _page_up_signal = pyqtSignal()
    _esc_signal = pyqtSignal()
    _end_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.listener: Optional[keyboard.Listener] = None
        self.callbacks = {
            'page_up': [],
            'esc': [],
            'end': []
        }
        self._lock = threading.Lock()
        self._page_up_signal.connect(self._dispatch_page_up, Qt.ConnectionType.QueuedConnection)
        self._esc_signal.connect(self._dispatch_esc, Qt.ConnectionType.QueuedConnection)
        self._end_signal.connect(self._dispatch_end, Qt.ConnectionType.QueuedConnection)
    
    def on_press(self, key):
        """Handle key press events"""
        try:
            if key == keyboard.Key.page_up:
                self._page_up_signal.emit()
            elif key == keyboard.Key.esc:
                self._esc_signal.emit()
            elif key == keyboard.Key.end:
                self._end_signal.emit()
        except AttributeError:
            pass
    
    def _run_callbacks(self, key: str):
        with self._lock:
            callbacks = list(self.callbacks.get(key, []))
        for callback in callbacks:
            callback()
    
    @pyqtSlot()
    def _dispatch_page_up(self):
        self._run_callbacks('page_up')
    
    @pyqtSlot()
    def _dispatch_esc(self):
        self._run_callbacks('esc')
    
    @pyqtSlot()
    def _dispatch_end(self):
        self._run_callbacks('end')
    
    def register_callback(self, key: str, callback: Callable):
        """Register a callback for a specific key"""
        if key in self.callbacks:
            with self._lock:
                if callback not in self.callbacks[key]:
                    self.callbacks[key].append(callback)
    
    def unregister_callback(self, key: str, callback: Callable):
        """Unregister a callback"""
        if key in self.callbacks:
            with self._lock:
                if callback in self.callbacks[key]:
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
