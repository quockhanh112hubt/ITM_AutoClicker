"""
Main entry point for ITM AutoClicker
"""
import sys
import os

# Suppress Qt DPI warnings on Windows
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
os.environ['QT_LOGGING_RULES'] = 'qt.qpa.window=false'

from src.main_window import MainWindow
from PyQt6.QtWidgets import QApplication


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
