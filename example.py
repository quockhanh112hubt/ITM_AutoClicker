"""
Example: Creating and Running a Click Script
"""
from src.click_script import ClickScript, ClickAction, ClickType
import json

def create_example_script():
    """Create an example click script"""
    
    # Create a new script
    script = ClickScript()
    
    # Example 1: Add position-based clicks
    print("Adding position-based clicks...")
    script.add_action(ClickAction(
        ClickType.POSITION,
        x=500,
        y=300,
        description="Click button 1"
    ))
    
    script.add_action(ClickAction(
        ClickType.POSITION,
        x=700,
        y=400,
        description="Click button 2"
    ))
    
    script.add_action(ClickAction(
        ClickType.POSITION,
        x=900,
        y=500,
        description="Click button 3"
    ))
    
    # Example 2: Add image-based clicks (if images exist)
    print("Adding image-based click...")
    script.add_action(ClickAction(
        ClickType.IMAGE,
        image_path="scripts/images/screenshot.png",
        offset_x=0,
        offset_y=0,
        click_x=100,
        click_y=100,
        description="Click on found image"
    ))
    
    return script


def save_example_script():
    """Save example script to file"""
    script = create_example_script()
    
    # Save script
    save_path = "scripts/example_script.json"
    script.save(save_path)
    print(f"✓ Script saved to {save_path}")
    
    # Print script contents
    print("\n📋 Script contents:")
    print(json.dumps(script.to_dict(), indent=2, ensure_ascii=False))


def load_example_script():
    """Load and display example script"""
    try:
        script = ClickScript.load("scripts/example_script.json")
        print(f"✓ Loaded {len(script.get_actions())} actions")
        
        for i, action in enumerate(script.get_actions(), 1):
            print(f"\n  Action {i}:")
            print(f"    Type: {action.type.value}")
            print(f"    Data: {action.data}")
    except FileNotFoundError:
        print("❌ Example script not found. Run save_example_script() first.")


if __name__ == "__main__":
    print("ITM AutoClicker - Example Script\n")
    print("=" * 50)
    
    # Create and save example
    print("\n1️⃣  Creating and saving example script...")
    save_example_script()
    
    # Load and display
    print("\n\n2️⃣  Loading and displaying example script...")
    print("=" * 50)
    load_example_script()
    
    print("\n\n✅ Example complete!")
    print("\nTo run the GUI application:")
    print("  python main.py")
