"""Utilities for selecting advanced recorded actions via PAGE DOWN."""
from PyQt6.QtWidgets import (
    QInputDialog,
    QDialog,
    QMessageBox,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QKeySequenceEdit,
)
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QCursor


def _create_dialog(parent, title: str, label: str, items=None):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setOkButtonText("OK")
    dialog.setCancelButtonText("Cancel")
    if items is not None:
        dialog.setComboBoxItems(items)
        if items:
            dialog.setTextValue(items[0])
    pos = QCursor.pos()
    dialog.move(pos.x() + 12, pos.y() + 12)
    return dialog


def _normalize_key_name(name: str) -> str:
    key = name.strip().lower()
    alias = {
        "control": "ctrl",
        "ctl": "ctrl",
        "escape": "esc",
        "return": "enter",
        "del": "delete",
        "pgup": "pageup",
        "pgdn": "pagedown",
        "pgup.": "pageup",
        "pgdn.": "pagedown",
        "cmd": "win",
        "meta": "win",
        "windows": "win",
    }
    return alias.get(key, key)


def _ask_hold_ms(parent):
    options = ["1s", "2s", "3s", "Custom..."]
    dialog = _create_dialog(parent, "Hold Duration", "Select hold duration:", options)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    choice = dialog.textValue()
    if choice == "1s":
        return 1000
    if choice == "2s":
        return 2000
    if choice == "3s":
        return 3000
    value, ok = QInputDialog.getInt(parent, "Custom Hold", "Hold duration (ms):", 1000, 100, 60000, 100)
    if not ok:
        return None
    return int(value)


def _ask_key(parent, title: str, label: str, single_char: bool = False):
    while True:
        dialog = _create_dialog(parent, title, label)
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        raw = dialog.textValue().strip()
        if not raw:
            return None
        if single_char:
            if len(raw) != 1:
                QMessageBox.warning(parent, title, "Please enter exactly 1 character.")
                continue
            return raw.lower()
        key = _normalize_key_name(raw)
        if not key:
            return None
        return key


def _ask_hotkey(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Hotkey")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Press your hotkey combination:"))
    key_edit = QKeySequenceEdit(dialog)
    layout.addWidget(key_edit)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    pos = QCursor.pos()
    dialog.move(pos.x() + 12, pos.y() + 12)
    
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    raw = key_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
    if not raw:
        return None
    tokens = [token.strip() for token in raw.replace(",", "+").split("+") if token.strip()]
    keys = [_normalize_key_name(k) for k in tokens]
    if not keys:
        return None
    return keys


def choose_advanced_action(parent):
    """
    Open action chooser near cursor.
    Returns a dict describing the selected action or None if cancelled.
    """
    options = [
        "Right Click",
        "Middle Click",
        "Mouse Hold Left",
        "Mouse Hold Right",
        "Key Press",
        "Hotkey",
        "Key Hold (Repeat)",
        "Key Hold (True)",
    ]
    dialog = _create_dialog(parent, "Choose Action", "Select action for current position:", options)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    choice = dialog.textValue()

    if choice == "Right Click":
        return {"action_mode": "mouse_click", "mouse_button": "right"}
    if choice == "Middle Click":
        return {"action_mode": "mouse_click", "mouse_button": "middle"}
    if choice == "Mouse Hold Left":
        hold_ms = _ask_hold_ms(parent)
        if hold_ms is None:
            return None
        return {"action_mode": "mouse_hold", "mouse_button": "left", "hold_ms": hold_ms}
    if choice == "Mouse Hold Right":
        hold_ms = _ask_hold_ms(parent)
        if hold_ms is None:
            return None
        return {"action_mode": "mouse_hold", "mouse_button": "right", "hold_ms": hold_ms}
    if choice == "Key Press":
        key = _ask_key(parent, "Key Press", "Enter exactly 1 character (example: A, 5):", single_char=True)
        if not key:
            return None
        return {"action_mode": "key_press", "key_name": key}
    if choice == "Hotkey":
        keys = _ask_hotkey(parent)
        if not keys:
            return None
        return {"action_mode": "hotkey", "hotkey_keys": keys}
    if choice == "Key Hold (Repeat)":
        key = _ask_key(parent, "Key Hold", "Enter exactly 1 character to hold:", single_char=True)
        if not key:
            return None
        hold_ms = _ask_hold_ms(parent)
        if hold_ms is None:
            return None
        return {"action_mode": "key_hold", "key_name": key, "hold_ms": hold_ms}
    if choice == "Key Hold (True)":
        key = _ask_key(parent, "Key Hold (True)", "Enter exactly 1 character to hold:", single_char=True)
        if not key:
            return None
        hold_ms = _ask_hold_ms(parent)
        if hold_ms is None:
            return None
        return {"action_mode": "key_hold_true", "key_name": key, "hold_ms": hold_ms}

    return None
