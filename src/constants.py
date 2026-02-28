"""
Application-wide constants for ITM AutoClicker
"""

# Default configuration values
DEFAULT_CLICK_DELAY_MS = 100
DEFAULT_PRIORITY_COOLDOWN_MS = 800
DEFAULT_IMAGE_CONFIDENCE = 0.8
DEFAULT_DRAG_MODE = "hybrid"

# Image matching constants
IMAGE_CONFIDENCE_MIN = 0.0
IMAGE_CONFIDENCE_MAX = 1.0
UNIFORM_COLOR_THRESHOLD = 2  # Standard deviation threshold for uniform color detection

# Mouse action constants
DEFAULT_HOLD_MS = 1000
DEFAULT_DRAG_MS = 500
DEFAULT_SCROLL_CLICKS = 0

# Window region selector constants
REGION_SELECTOR_MAX_CHILD_DEPTH = 10

# Keyboard listener constants
KEYBOARD_LISTENER_THREAD_SLEEP_MS = 50

# Action execution constants
DEFAULT_MAX_EXECUTIONS = None  # Unlimited
ACTION_EXECUTION_THREAD_TIMEOUT = 2  # seconds

# UI constants
DEFAULT_WINDOW_SIZE = (800, 600)
DEFAULT_FONT_SIZE = 10

# Mouse button constants
MOUSE_BUTTON_LEFT = "left"
MOUSE_BUTTON_RIGHT = "right"
MOUSE_BUTTON_MIDDLE = "middle"

# Action mode constants
ACTION_MODE_MOUSE_CLICK = "mouse_click"
ACTION_MODE_MOUSE_HOLD = "mouse_hold"
ACTION_MODE_MOUSE_SCROLL = "mouse_scroll"
ACTION_MODE_MOUSE_DRAG = "mouse_drag"
ACTION_MODE_KEY_PRESS = "key_press"
ACTION_MODE_HOTKEY = "hotkey"
ACTION_MODE_KEY_HOLD = "key_hold"
ACTION_MODE_KEY_HOLD_TRUE = "key_hold_true"

# File paths
CONFIG_FILE_PATH = "config/settings.json"
LOGS_DIR = "logs"
SCRIPTS_DIR = "scripts"
IMAGES_DIR = "scripts/images"
LOG_FILE_NAME = "itm_autoclicker.log"

# Logging constants
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
LOG_CONSOLE_LEVEL = "INFO"
LOG_FILE_LEVEL = "DEBUG"

# Validation constants
MIN_REGION_SIZE = 1  # Minimum width/height for region capture
MAX_IMAGE_CONFIDENCE = 1.0
MIN_IMAGE_CONFIDENCE = 0.0

# Time-related constants
KEYBOARD_LISTENER_START_TIMEOUT = 2
EXECUTION_THREAD_DAEMON = True
EXECUTION_WAIT_SLEEP_TIME = 0.05

# Window list dialog constants
WINDOW_DIALOG_WIDTH = 400
WINDOW_DIALOG_HEIGHT = 300
