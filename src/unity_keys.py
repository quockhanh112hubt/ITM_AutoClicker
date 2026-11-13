"""Action key names to UnityEngine.KeyCode, independent of Windows VK codes."""

def unity_key_code(name):
    key = str(name).strip().lower()
    aliases = {
        "backspace": 8, "tab": 9, "enter": 13, "return": 13, "pause": 19,
        "esc": 27, "escape": 27, "space": 32, "delete": 127,
        "up": 273, "down": 274, "right": 275, "left": 276, "insert": 277,
        "home": 278, "end": 279, "pageup": 280, "pagedown": 281,
        "numlock": 300, "capslock": 301, "scrolllock": 302,
        "rshift": 303, "right shift": 303, "shift": 304, "lshift": 304, "left shift": 304,
        "rctrl": 305, "right ctrl": 305, "ctrl": 306, "control": 306, "lctrl": 306, "left ctrl": 306,
        "ralt": 307, "right alt": 307, "alt": 308, "lalt": 308, "left alt": 308,
        "win": 311, "winleft": 311, "winright": 312,
        "multiply": 268, "add": 270, "subtract": 269, "divide": 267, "decimal": 266,
    }
    if key in aliases:
        return aliases[key]
    if len(key) == 1 and 32 <= ord(key) <= 126:
        return ord(key)
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 15:
        return 281 + int(key[1:])
    if len(key) == 4 and key.startswith("num") and key[-1].isdigit():
        return 256 + int(key[-1])
    raise ValueError(f"Unsupported Unity key: {name}")
