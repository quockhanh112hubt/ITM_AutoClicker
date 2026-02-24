"""
Installation and Development Guide
"""

# ITM AutoClicker - Developer Guide 🛠️

## 🔧 Installation

### Option 1: Quick Start (Recommended)

```bash
# Clone the repository
git clone https://github.com/quockhanh112hubt/ITM_AutoClicker.git
cd ITM_AutoClicker

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Option 2: Manual Installation

```bash
# Install PyQt6
pip install PyQt6==6.6.1

# Install keyboard/mouse listener
pip install pynput==1.7.6

# Install mouse automation
pip install pyautogui==0.9.53

# Install computer vision
pip install opencv-python==4.8.1.78

# Install image processing
pip install Pillow==12.1.1

# Install numpy (required by OpenCV)
pip install "numpy<2"
```

## 📦 Project Structure

```
ITM_AutoClicker/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── test_imports.py           # Test script for verifying imports
│
├── src/                       # Main source code
│   ├── __init__.py           # Package initializer
│   ├── main_window.py        # Main GUI window (PyQt6)
│   ├── click_script.py       # Click script management
│   ├── auto_clicker.py       # Auto clicking engine
│   ├── keyboard_listener.py  # Global keyboard hook
│   ├── image_matcher.py      # Template matching (OpenCV)
│   ├── region_selector.py    # Region selection UI
│   └── config.py             # Configuration management
│
├── scripts/                   # User data directory
│   ├── *.json                # Saved click scripts
│   └── images/               # Screenshot templates
│
├── config/                    # Application configuration
│   └── settings.json         # Application settings
│
├── README.md                  # User documentation
└── LICENSE                    # MIT License
```

## 🎯 Module Overview

### 1. **main.py** - Entry Point
- Initializes PyQt6 application
- Creates and shows main window

### 2. **main_window.py** - GUI (PyQt6)
- Implements main application window
- Contains two tabs:
  - **Main Tab**: Script editing and execution
  - **Settings Tab**: Application preferences
- Manages user interactions and event handling

### 3. **click_script.py** - Script Management
- `ClickType` enum: Defines action types (POSITION, IMAGE)
- `ClickAction` class: Represents a single click action
- `ClickScript` class: Container for multiple actions
- Handles JSON serialization/deserialization

### 4. **auto_clicker.py** - Execution Engine
- `AutoClicker` class: Manages script execution
- Runs clicks in separate thread
- Supports pause/resume
- Configurable delay between clicks

### 5. **keyboard_listener.py** - Global Hotkeys
- `KeyboardListener` class: Listens for global keyboard events
- Monitors: PAGE_UP, ESC, END
- Does not block mouse/keyboard for other applications

### 6. **image_matcher.py** - Template Matching
- `ImageMatcher` class: Finds and clicks on images
- Uses OpenCV template matching
- Configurable confidence threshold
- Captures screen regions as templates

### 7. **region_selector.py** - UI for Region Selection
- `RegionSelectorWindow` class: Fullscreen region selector
- Allows drag-to-select functionality
- Shows selection rectangle with dimensions

### 8. **config.py** - Settings Management
- `Config` class: Manages application configuration
- Persists settings to JSON file
- Supports default values

## 🚀 Usage Examples

### Example 1: Position-Based Click Script

```python
from src.click_script import ClickScript, ClickAction, ClickType

# Create a script
script = ClickScript()

# Add position-based clicks
script.add_action(ClickAction(ClickType.POSITION, x=100, y=200))
script.add_action(ClickAction(ClickType.POSITION, x=300, y=400))

# Save to file
script.save("scripts/my_script.json")

# Load from file
loaded_script = ClickScript.load("scripts/my_script.json")
```

### Example 2: Auto-Execute Script

```python
from src.auto_clicker import AutoClicker
from src.click_script import ClickScript

# Load script
script = ClickScript.load("scripts/my_script.json")

# Create auto clicker with 200ms delay
clicker = AutoClicker(delay_ms=200)

# Execute script
clicker.execute_script(script)

# Stop after some time
import time
time.sleep(10)
clicker.stop()
```

### Example 3: Listen to Keyboard Events

```python
from src.keyboard_listener import KeyboardListener

def on_page_up():
    print("PAGE UP pressed!")

listener = KeyboardListener()
listener.register_callback('page_up', on_page_up)
listener.start()

# Do something...

listener.stop()
```

## 🔍 Key Features Implementation

### Global Keyboard Listening (Non-Blocking)
- Uses `pynput` library for global keyboard monitoring
- Runs in separate thread
- Does not interfere with mouse or other keyboard input

### Template Matching
- Uses OpenCV `matchTemplate` function
- Compares image regions with confidence threshold
- Returns pixel coordinates of match

### Automatic Screen Capture
- Uses `PIL.ImageGrab` to capture regions
- Stores templates for later matching

## 📝 Configuration File Format

**File**: `config/settings.json`

```json
{
  "click_delay_ms": 100,
  "image_confidence": 0.8,
  "auto_save": true,
  "last_script": null
}
```

## 💾 Script File Format

**File**: `scripts/*.json`

```json
{
  "version": "1.0",
  "actions": [
    {
      "type": "position",
      "data": {
        "x": 100,
        "y": 200
      }
    },
    {
      "type": "image",
      "data": {
        "image_path": "scripts/images/image_1.png",
        "offset_x": 0,
        "offset_y": 0,
        "click_x": 150,
        "click_y": 250
      }
    }
  ]
}
```

## 🧪 Testing

Run the test script to verify all imports:

```bash
python test_imports.py
```

Expected output:
```
✓ All imports successful!
✓ Created script with 1 action(s)
✓ Config loaded: delay=100ms
✓ AutoClicker initialized with 100ms delay

✅ All tests passed! Application structure is correct.
```

## 🐛 Troubleshooting

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'cv2'`

**Solution**: 
```bash
pip install opencv-python
pip install "numpy<2"
```

**Error**: `ModuleNotFoundError: No module named 'PyQt6'`

**Solution**:
```bash
pip install PyQt6
```

### Runtime Errors

**Error**: Template matching not finding images

**Solution**:
- Increase `click_delay_ms` in settings
- Lower `image_confidence` threshold
- Verify image quality

**Error**: Keyboard hotkeys not responding

**Solution**:
- Check if another application is using the same hotkeys
- Restart the application
- Run as administrator

## 🔄 Development Workflow

1. **Make changes** to source files in `src/`
2. **Test imports** with `test_imports.py`
3. **Run GUI** with `python main.py`
4. **Commit changes** to git

## 📚 Additional Resources

- PyQt6 Documentation: https://www.riverbankcomputing.com/static/Docs/PyQt6/
- OpenCV Documentation: https://docs.opencv.org/
- pynput Documentation: https://pynput.readthedocs.io/

## 📄 License

MIT License - See LICENSE file for details

---

Happy coding! 🚀
