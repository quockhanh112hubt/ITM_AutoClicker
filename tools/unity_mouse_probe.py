"""One-shot diagnostic/test for the opt-in MongThienKiem virtual mouse."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import win32gui
from src.unity_bridge import UnityBridge
from src.unity_profiles import inspect_client, ProfileStore, select_profile, UnityProfileError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connect", action="store_true", help="Load/inspect the helper without clicking")
    parser.add_argument("--click", nargs=2, type=int, metavar=("X", "Y"), help="One click at game client coordinates")
    parser.add_argument("--window-title", default="MongThienKiem", help="Exact title of the selected Unity client")
    parser.add_argument("--profile", default="auto", help="Profile id or auto")
    parser.add_argument("--allow-experimental", action="store_true", help="Enable eligible untested family profiles")
    parser.add_argument("--report", type=Path, help="Write a read-only JSON client inspection report")
    args = parser.parse_args()
    matches = []
    win32gui.EnumWindows(lambda h, _: matches.append(h)
        if win32gui.GetWindowText(h).casefold() == args.window_title.casefold() else None, None)
    if len(matches) != 1:
        parser.error("Open exactly one client matching --window-title for this probe")
    hwnd = matches[0]
    info = inspect_client(hwnd)
    payload = {"client": info.report()}
    try:
        payload["profile"] = select_profile(info, ProfileStore(), args.profile)
    except UnityProfileError as exc:
        payload["selection_error"] = str(exc)
    print(json.dumps(payload, ensure_ascii=False))
    if args.report:
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.connect and args.click is None:
        print("Read-only detection complete. Use --connect to probe the selected profile or --click X Y for one gesture.")
        return
    cursor, foreground = win32gui.GetCursorPos(), win32gui.GetForegroundWindow()
    if args.click:
        if win32gui.IsIconic(hwnd):
            parser.error("Restore the game window before testing")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if foreground == hwnd or left <= cursor[0] < right and top <= cursor[1] < bottom:
            parser.error("For an independent-cursor test, keep the game in background and cursor outside it")
    with UnityBridge(hwnd, profile_id=args.profile, allow_experimental=args.allow_experimental) as bridge:
        if args.click:
            bridge.mouse_action(*args.click)
        print(json.dumps(bridge.diagnostics()))
    print(json.dumps({"cursor_before": cursor, "cursor_after": win32gui.GetCursorPos(),
                      "foreground_before": foreground, "foreground_after": win32gui.GetForegroundWindow()}))


if __name__ == "__main__":
    main()
