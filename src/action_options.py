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
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
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


def _ask_scroll_steps(parent):
    options = ["1 notch", "3 notches", "5 notches", "Custom..."]
    dialog = _create_dialog(parent, "Scroll Amount", "Select scroll amount:", options)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    choice = dialog.textValue()
    if choice == "1 notch":
        return 1
    if choice == "3 notches":
        return 3
    if choice == "5 notches":
        return 5
    value, ok = QInputDialog.getInt(parent, "Custom Scroll", "Scroll notches:", 3, 1, 100, 1)
    if not ok:
        return None
    return int(value)


def _ask_drag_ms(parent):
    options = ["300ms", "500ms", "1000ms", "Custom..."]
    dialog = _create_dialog(parent, "Drag Duration", "Select drag duration:", options)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    choice = dialog.textValue()
    if choice == "300ms":
        return 300
    if choice == "500ms":
        return 500
    if choice == "1000ms":
        return 1000
    value, ok = QInputDialog.getInt(parent, "Custom Drag", "Drag duration (ms):", 500, 50, 60000, 50)
    if not ok:
        return None
    return int(value)


def _ask_drag_target_with_enter(parent, start_x: int, start_y: int):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Select Drag Target")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(f"Start point: ({int(start_x)}, {int(start_y)})"))
    layout.addWidget(QLabel("Move mouse to drop point, then press ENTER to confirm."))
    coords_label = QLabel("")
    layout.addWidget(coords_label)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    pos = QCursor.pos()
    dialog.move(pos.x() + 12, pos.y() + 12)

    def update_coords():
        p = QCursor.pos()
        coords_label.setText(f"Current mouse: ({int(p.x())}, {int(p.y())})")

    timer = QTimer(dialog)
    timer.timeout.connect(update_coords)
    timer.start(60)
    update_coords()

    sc_return = QShortcut(QKeySequence("Return"), dialog)
    sc_enter = QShortcut(QKeySequence("Enter"), dialog)
    sc_return.activated.connect(dialog.accept)
    sc_enter.activated.connect(dialog.accept)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    p = QCursor.pos()
    return int(p.x()), int(p.y())


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


def choose_advanced_action(parent, start_x: int | None = None, start_y: int | None = None):
    """
    Open action chooser near cursor.
    Returns a dict describing the selected action or None if cancelled.
    """
    options = [
        "Right Click",
        "Middle Click",
        "Scroll Up",
        "Scroll Down",
        "Mouse Hold Left",
        "Mouse Hold Right",
        "Drag Left",
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
    if choice == "Scroll Up":
        steps = _ask_scroll_steps(parent)
        if steps is None:
            return None
        return {"action_mode": "mouse_scroll", "scroll_clicks": int(steps)}
    if choice == "Scroll Down":
        steps = _ask_scroll_steps(parent)
        if steps is None:
            return None
        return {"action_mode": "mouse_scroll", "scroll_clicks": -int(steps)}
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
    if choice == "Drag Left":
        if start_x is None or start_y is None:
            p = QCursor.pos()
            start_x, start_y = int(p.x()), int(p.y())
        target = _ask_drag_target_with_enter(parent, int(start_x), int(start_y))
        if not target:
            return None
        drag_to_x, drag_to_y = target
        drag_ms = _ask_drag_ms(parent)
        if drag_ms is None:
            return None
        return {
            "action_mode": "mouse_drag",
            "mouse_button": "left",
            "drag_to_x": int(drag_to_x),
            "drag_to_y": int(drag_to_y),
            "drag_ms": int(drag_ms),
        }
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
