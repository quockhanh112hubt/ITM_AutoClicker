"""One-shot diagnostic/test for the opt-in MongThienKiem virtual mouse."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import win32gui
from src.unity_bridge import UnityBridge, validate_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connect", action="store_true", help="Load/inspect the helper without clicking")
    parser.add_argument("--click", nargs=2, type=int, metavar=("X", "Y"), help="One click at game client coordinates")
    args = parser.parse_args()
    matches = []
    win32gui.EnumWindows(lambda h, _: matches.append(h)
        if win32gui.GetWindowText(h).casefold() == "mongthienkiem" else None, None)
    if len(matches) != 1:
        parser.error("Open exactly one MongThienKiem client for this probe")
    hwnd = matches[0]
    pid, root = validate_client(hwnd)
    print(json.dumps({"hwnd": hwnd, "pid": pid, "client": str(root)}, ensure_ascii=False))
    if not args.connect and args.click is None:
        print("Supported build. Use --connect to load the helper or --click X Y for one gesture.")
        return
    cursor, foreground = win32gui.GetCursorPos(), win32gui.GetForegroundWindow()
    if args.click:
        if win32gui.IsIconic(hwnd):
            parser.error("Restore the game window before testing")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if foreground == hwnd or left <= cursor[0] < right and top <= cursor[1] < bottom:
            parser.error("For an independent-cursor test, keep the game in background and cursor outside it")
    with UnityBridge(hwnd) as bridge:
        if args.click:
            bridge.mouse_action(*args.click)
        print(json.dumps(bridge.diagnostics()))
    print(json.dumps({"cursor_before": cursor, "cursor_after": win32gui.GetCursorPos(),
                      "foreground_before": foreground, "foreground_after": win32gui.GetForegroundWindow()}))


if __name__ == "__main__":
    main()
