"""Build and run an isolated native hook/IPC/heartbeat smoke test (no real game)."""
from pathlib import Path
import ctypes
import mmap
import os
import struct
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.unity_bridge import UnityBridge, UnityBridgeError, kernel
import win32gui


def main():
    zig = str(ROOT / "build/tools/zig/ziglang/zig.exe")
    folder = ROOT / "build/unity_bridge_fixture"
    folder.mkdir(parents=True, exist_ok=True)
    source = ROOT / "native/unity_bridge/tests/fixture.c"
    for filename, flags in (("GameAssembly.dll", ["-shared"]), ("fixture.exe", ["-DFIXTURE_MAIN"])):
        subprocess.run([zig, "cc", "-O1", "-target", "x86_64-windows-gnu", *flags,
                        str(source), "-o", str(folder / filename), "-luser32"], check=True)
    process = subprocess.Popen([str(folder / "fixture.exe")], cwd=folder, stdout=subprocess.PIPE,
                               text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    bridge = None
    try:
        line = process.stdout.readline().strip()
        if not line:
            raise RuntimeError("Fixture failed to start")
        pid, hwnd = map(int, line.split())
        with patch("src.unity_bridge.validate_client", return_value=(pid, folder)):
            bridge = UnityBridge(hwnd)
            try:
                UnityBridge(hwnd)
                raise AssertionError("Second controller acquired a busy game")
            except UnityBridgeError as exc:
                assert "Another ITM session" in str(exc), str(exc)
        observer = mmap.mmap(-1, 28, tagname=f"Local\\ITMUnityFixture_{pid}")
        cursor, foreground = win32gui.GetCursorPos(), win32gui.GetForegroundWindow()
        bridge.mouse_action(25, 39)
        values = struct.unpack_from("<iiiiffi", observer)
        print("Fixture",pid,hwnd,"diagnostics",bridge.diagnostics(),"observer",values,flush=True)
        assert values[1:3] == (1, 1), values
        assert abs(values[4] - 25) < 0.01 and abs(values[5] - 681) < 0.01, values
        assert values[6] == 0, values
        assert bridge.diagnostics()["focus_overrides"] > 0
        print("Click/Up, Unity coordinates, background focus and controller exclusivity: OK", values)
        bridge.close()
        with patch("src.unity_bridge.validate_client", return_value=(pid, folder)):
            bridge = UnityBridge(hwnd)
        bridge.mouse_action(30, 40)
        values = struct.unpack_from("<iiiiffi", observer)
        assert values[1:3] == (2, 2), values
        print("Reconnect to resident helper: OK")
        bridge._wait_ack(bridge._command(40, 50, 1))
        bridge._stop.set()
        bridge._heartbeat_thread.join()
        bridge.shared.heartbeat = kernel.GetTickCount64() - 2000
        time.sleep(0.1)
        values = struct.unpack_from("<iiiiffi", observer)
        assert values[6] == 0 and values[2] == 3, values
        print("Lost heartbeat releases held button: OK", values)
        print("Cursor:", cursor, "->", win32gui.GetCursorPos(), "foreground:", foreground, "->", win32gui.GetForegroundWindow())
        observer.close()
        bridge.close()
        bridge = None
    finally:
        if bridge:
            bridge.close()
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
