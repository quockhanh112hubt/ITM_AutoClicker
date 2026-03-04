"""
Core module for Auto Clicker
Handles recording and playback of click actions
"""
import json
import os
from typing import List, Dict, Any, Optional
import pyautogui
import time
from enum import Enum


class ClickType(Enum):
    """Types of click actions"""
    POSITION = "position"  # Click at specific coordinates
    IMAGE = "image"        # Click at recorded point when image is found
    IMAGE_DIRECT = "image_direct"  # Click directly on matched image
    IMAGE_RECOGNITION = "image_recognition"  # OCR text from matched image region
    IF = "if"              # Conditional logic row


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
    
    def add_action(self, action: ClickAction) -> None:
        """
        Add a click action to the script
        
        Args:
            action: ClickAction to add
            
        Raises:
            ValueError: If action is None or not a ClickAction instance
        """
        if action is None:
            raise ValueError("action cannot be None")
        if not isinstance(action, ClickAction):
            raise ValueError(f"action must be a ClickAction instance, got {type(action).__name__}")
        self.actions.append(action)
    
    def remove_action(self, index: int) -> None:
        """
        Remove a click action by index
        
        Args:
            index: Index of action to remove
            
        Raises:
            ValueError: If index is not an integer
            IndexError: If index is out of range
        """
        if not isinstance(index, int):
            raise ValueError(f"index must be an integer, got {type(index).__name__}")
        if not (0 <= index < len(self.actions)):
            raise IndexError(f"Index {index} out of range (0-{len(self.actions)-1})")
        self.actions.pop(index)
    
    def clear(self) -> None:
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
    
    def save(self, filepath: str) -> None:
        """
        Save script to JSON file
        
        Args:
            filepath: Path where to save the script
            
        Raises:
            ValueError: If filepath is None or empty
            OSError: If file cannot be written
        """
        if not filepath:
            raise ValueError("filepath cannot be None or empty")
        if not isinstance(filepath, str):
            raise ValueError(f"filepath must be a string, got {type(filepath).__name__}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load(filepath: str) -> 'ClickScript':
        """
        Load script from JSON file with validation
        
        Args:
            filepath: Path to the script file
            
        Raises:
            ValueError: If filepath is None or empty
            FileNotFoundError: If script file doesn't exist
            ValueError: If JSON is invalid or structure is incorrect
        """
        if not filepath:
            raise ValueError("filepath cannot be None or empty")
        if not isinstance(filepath, str):
            raise ValueError(f"filepath must be a string, got {type(filepath).__name__}")
        
        # Validate file exists
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Script file not found: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in script file: {e}")
        
        # Validate data structure
        if not isinstance(data, dict):
            raise ValueError("Script file must contain a JSON object (dict)")
        
        if "actions" not in data:
            raise ValueError("Script must contain 'actions' field")
        
        if not isinstance(data["actions"], list):
            raise ValueError("'actions' field must be a list")
        
        return ClickScript.from_dict(data)
