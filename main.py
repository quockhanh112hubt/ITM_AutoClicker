"""
Main entry point for ITM AutoClicker
"""
import sys
import os
import ctypes

# Suppress Qt DPI warnings on Windows
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.window=false'

# Ensure coordinate systems are consistent across Win32 + pynput + Qt.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from src.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = os.path.join(os.path.dirname(__file__), "resource", "Icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
