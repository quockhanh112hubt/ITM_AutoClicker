"""
Core module for Auto Clicker
Handles recording and playback of click actions
"""
import json
import os
from typing import List, Dict, Any
import pyautogui
import time
from enum import Enum


class ClickType(Enum):
    """Types of click actions"""
    POSITION = "position"  # Click at specific coordinates
    IMAGE = "image"        # Click at recorded point when image is found
    IMAGE_DIRECT = "image_direct"  # Click directly on matched image


class ClickAction:
    """Represents a single click action"""
    
    def __init__(self, action_type: ClickType, **kwargs):
        self.type = action_type
        self.data = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type.value,
            "data": self.data
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ClickAction':
        """Create ClickAction from dictionary"""
        action_type = ClickType(data["type"])
        return ClickAction(action_type, **data["data"])


class ClickScript:
    """Manages a collection of click actions"""
    
    def __init__(self):
        self.actions: List[ClickAction] = []
    
    def add_action(self, action: ClickAction):
        """Add a click action to the script"""
        self.actions.append(action)
    
    def remove_action(self, index: int):
        """Remove a click action by index"""
        if 0 <= index < len(self.actions):
            self.actions.pop(index)
    
    def clear(self):
        """Clear all actions"""
        self.actions.clear()
    
    def get_actions(self) -> List[ClickAction]:
        """Get all actions"""
        return self.actions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert script to dictionary"""
        return {
            "version": "1.0",
            "actions": [action.to_dict() for action in self.actions]
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ClickScript':
        """Create ClickScript from dictionary"""
        script = ClickScript()
        for action_data in data.get("actions", []):
            script.add_action(ClickAction.from_dict(action_data))
        return script
    
    def save(self, filepath: str):
        """Save script to JSON file"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load(filepath: str) -> 'ClickScript':
        """Load script from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ClickScript.from_dict(data)
