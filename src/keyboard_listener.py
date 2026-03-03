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
    _page_down_signal = pyqtSignal()
    _esc_signal = pyqtSignal()
    _home_signal = pyqtSignal()
    _end_signal = pyqtSignal()
    _f10_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.listener: Optional[keyboard.Listener] = None
        self.key_bindings = {
            'page_up': 'page_up',
            'page_down': 'page_down',
            'esc': 'esc',
            'home': 'home',
            'end': 'end',
            'f10': 'f10'
        }
        self.callbacks = {
            'page_up': [],
            'page_down': [],
            'esc': [],
            'home': [],
            'end': [],
            'f10': []
        }
        self._lock = threading.Lock()
        self._page_up_signal.connect(self._dispatch_page_up, Qt.ConnectionType.QueuedConnection)
        self._page_down_signal.connect(self._dispatch_page_down, Qt.ConnectionType.QueuedConnection)
        self._esc_signal.connect(self._dispatch_esc, Qt.ConnectionType.QueuedConnection)
        self._home_signal.connect(self._dispatch_home, Qt.ConnectionType.QueuedConnection)
        self._end_signal.connect(self._dispatch_end, Qt.ConnectionType.QueuedConnection)
        self._f10_signal.connect(self._dispatch_f10, Qt.ConnectionType.QueuedConnection)
    
    def on_press(self, key):
        """Handle key press events"""
        try:
            pressed = self._normalize_pressed_key(key)
            if not pressed:
                return
            if pressed == self.key_bindings.get('page_up'):
                self._page_up_signal.emit()
            elif pressed == self.key_bindings.get('page_down'):
                self._page_down_signal.emit()
            elif pressed == self.key_bindings.get('esc'):
                self._esc_signal.emit()
            elif pressed == self.key_bindings.get('home'):
                self._home_signal.emit()
            elif pressed == self.key_bindings.get('end'):
                self._end_signal.emit()
            elif pressed == self.key_bindings.get('f10'):
                self._f10_signal.emit()
        except AttributeError:
            pass

    def _normalize_pressed_key(self, key) -> str:
        """Normalize pressed key from pynput to internal key token."""
        # Special keys
        name = getattr(key, "name", None)
        if isinstance(name, str) and name:
            return name.lower()
        # Character keys
        ch = getattr(key, "char", None)
        if isinstance(ch, str) and ch:
            return ch.lower()
        return ""

    def _normalize_key_name(self, key_name: str) -> str:
        """Normalize user key input to internal token format."""
        value = str(key_name or "").strip().lower()
        value = value.replace(" ", "_").replace("-", "_")
        return value

    def set_binding(self, callback_key: str, key_name: str) -> bool:
        """
        Set a physical key binding for a logical callback key.
        Returns True when applied, False when invalid.
        """
        if callback_key not in self.key_bindings:
            return False
        value = self._normalize_key_name(key_name)
        if not value:
            return False
        if len(value) == 1:
            self.key_bindings[callback_key] = value
            return True
        if hasattr(keyboard.Key, value):
            self.key_bindings[callback_key] = value
            return True
        return False

    def get_binding(self, callback_key: str) -> str:
        """Get current physical key binding for callback key."""
        return str(self.key_bindings.get(callback_key, ""))
    
    def _run_callbacks(self, key: str):
        with self._lock:
            callbacks = list(self.callbacks.get(key, []))
        for callback in callbacks:
            callback()
    
    @pyqtSlot()
    def _dispatch_page_up(self):
        self._run_callbacks('page_up')
    
    @pyqtSlot()
    def _dispatch_page_down(self):
        self._run_callbacks('page_down')
    
    @pyqtSlot()
    def _dispatch_esc(self):
        self._run_callbacks('esc')

    @pyqtSlot()
    def _dispatch_home(self):
        self._run_callbacks('home')
    
    @pyqtSlot()
    def _dispatch_end(self):
        self._run_callbacks('end')

    @pyqtSlot()
    def _dispatch_f10(self):
        self._run_callbacks('f10')
    
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
