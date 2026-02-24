#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITM AutoClicker - Quick Start Guide
Run this file to see step-by-step instructions
"""

import sys
import io

# Set stdout encoding for Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_section(title, content):
    """Print a formatted section"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(content)

def main():
    print_section(
        "🖱️  ITM AutoClicker - Quick Start Guide",
        """
Welcome to ITM AutoClicker!

This guide will help you get started with the application.
        """
    )
    
    print_section(
        "📋 Table of Contents",
        """
1. Installation
2. Running the Application
3. Creating Your First Script
4. Using Position-Based Clicks
5. Using Image-Based Clicks
6. Troubleshooting
        """
    )
    
    print_section(
        "1️⃣  Installation",
        """
Prerequisites:
  • Python 3.8 or higher
  • Windows, macOS, or Linux

Step 1: Create Virtual Environment
  python -m venv .venv
  
Step 2: Activate Virtual Environment
  Windows: .venv\\Scripts\\activate
  Mac/Linux: source .venv/bin/activate
  
Step 3: Install Dependencies
  pip install -r requirements.txt
  
Step 4: Verify Installation
  python test_imports.py
  
Expected output: ✅ All tests passed!
        """
    )
    
    print_section(
        "2️⃣  Running the Application",
        """
From the project directory:
  
  python main.py
  
The GUI window should appear with two tabs:
  • Main: For creating and running scripts
  • Settings: For configuring delay and other options
        """
    )
    
    print_section(
        "3️⃣  Creating Your First Script",
        """
Step 1: Open the Application
  python main.py
  
Step 2: Add an Action
  Click "Add Action" button
  
Step 3: Choose Type
  • "Position Based Click" for coordinate clicks
  • "Image Based Click" for template matching
  
Step 4: Save the Script
  Click "Save Script" button
  Choose location and filename (e.g., my_script.json)
  
Step 5: Run the Script
  Click "Start" button or press END
  
Step 6: Stop the Script
  Click "Stop" button or press END again
        """
    )
    
    print_section(
        "4️⃣  Using Position-Based Clicks",
        """
This mode records clicks at specific coordinates.

How to Record:
  1. Click "Add Action" → "Position Based Click"
  2. Move mouse to the first position
  3. Press PAGE UP to record position
  4. Move to next position and press PAGE UP again
  5. Repeat for all positions
  6. Press ESC when finished
  
Advantages:
  ✓ Fast and reliable
  ✓ Works with any application
  ✓ No image processing needed
  
Disadvantages:
  ✗ Breaks if UI elements move
  ✗ Resolution dependent
        """
    )
    
    print_section(
        "5️⃣  Using Image-Based Clicks",
        """
This mode finds and clicks on images on screen.

How to Record:
  1. Click "Add Action" → "Image Based Click"
  2. Region selector window opens
  3. Drag to select an image area (green rectangle)
  4. Release mouse - image is captured
  5. Move mouse to click position
  6. Press PAGE UP to record click position
  7. Choose Yes to add another image or No to finish
  8. Repeat for more images
  9. Press ESC when done
  
Advantages:
  ✓ Works even if UI moves
  ✓ More reliable with dynamic content
  ✓ Resolution independent
  
Disadvantages:
  ✗ Slower than position clicks
  ✗ Needs good image quality
  ✗ May fail with similar-looking elements
        """
    )
    
    print_section(
        "⌨️  Keyboard Shortcuts",
        """
Global Hotkeys (work even when app is not focused):
  
  PAGE UP   → Record position or confirm click position
  ESC       → Exit recording mode
  END       → Toggle Start/Stop execution
  
These hotkeys can be used to control the app from any window!
        """
    )
    
    print_section(
        "⚙️  Settings",
        """
Click on "Settings" tab to configure:
  
  • Click Delay (ms): Time between consecutive clicks
    - Default: 100ms
    - Increase if website is slow
    - Decrease for faster execution
    
Settings are saved automatically to: config/settings.json
        """
    )
    
    print_section(
        "💾 Managing Scripts",
        """
Save Script:
  1. Configure your click actions
  2. Click "Save Script"
  3. Choose location and name
  4. File is saved as JSON
  
Load Script:
  1. Click "Load Script"
  2. Select previously saved script
  3. Script is loaded into editor
  4. Can be modified and saved again
  
Clear/Remove Actions:
  • "Clear All": Remove all actions
  • "Remove Action": Remove selected action
        """
    )
    
    print_section(
        "🐛 Troubleshooting",
        """
Problem: Clicks not working
  Solution: Run as Administrator
           Disable antivirus temporarily
           
Problem: Image not found
  Solution: Increase Click Delay
           Check image quality
           Ensure exact match is visible
           
Problem: Hotkeys not responding
  Solution: Restart application
           Check for key conflicts with other apps
           Run as Administrator
           
Problem: Import errors
  Solution: Reinstall dependencies
           python -m pip install --upgrade pip
           pip install -r requirements.txt --force-reinstall
           
Problem: Template matching is slow
  Solution: Use smaller image regions
           Increase confidence threshold in code
           Use position-based clicks instead
        """
    )
    
    print_section(
        "📚 More Examples",
        """
For more examples, check:
  • example.py: Creating scripts programmatically
  • DEVELOPMENT.md: Developer documentation
  • README.md: Full user documentation
        """
    )
    
    print_section(
        "❓ FAQ",
        """
Q: Can I use multiple scripts?
A: Yes! Create different files and load them as needed.

Q: Will this work with my application?
A: Usually yes, but some applications block automation.

Q: Is this safe?
A: Yes, it only clicks where you tell it to click.

Q: Can I edit coordinates manually?
A: Not yet, but you can edit the JSON script files directly.

Q: What about mouse movement speed?
A: Currently uses instant clicks. Can be enhanced later.

Q: Can I add delays before/after clicks?
A: Not yet, but this can be added in future versions.

Q: How do I uninstall?
A: Just delete the folder. All data is stored locally.
        """
    )
    
    print_section(
        "🚀 Next Steps",
        """
1. Follow the installation guide
2. Run your first test: python test_imports.py
3. Launch the GUI: python main.py
4. Create your first simple script
5. Try both position and image-based clicks
6. Save and load scripts to get comfortable with the interface
7. Experiment with different delay values
8. Explore the settings and configuration

Happy automating! 🎉
        """
    )

if __name__ == "__main__":
    main()
    print("\n" * 2)
