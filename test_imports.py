"""
Simple test to verify the application structure
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

try:
    from src.click_script import ClickScript, ClickAction, ClickType
    from src.keyboard_listener import KeyboardListener
    from src.config import Config
    from src.auto_clicker import AutoClicker
    
    print("✓ All imports successful!")
    
    # Test ClickScript
    script = ClickScript()
    action1 = ClickAction(ClickType.POSITION, x=100, y=200)
    script.add_action(action1)
    print(f"✓ Created script with {len(script.get_actions())} action(s)")
    
    # Test Config
    config = Config()
    delay = config.get("click_delay_ms", 100)
    print(f"✓ Config loaded: delay={delay}ms")
    
    # Test AutoClicker
    clicker = AutoClicker(delay)
    print(f"✓ AutoClicker initialized with {delay}ms delay")
    
    print("\n✅ All tests passed! Application structure is correct.")
    print("\nTo run the GUI application:")
    print("  python main.py")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
