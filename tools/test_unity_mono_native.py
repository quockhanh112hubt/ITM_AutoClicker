"""Exercise Mono adapter/IPC through a disposable native runtime, no real game."""
from pathlib import Path
import ctypes
import json
import mmap
import os
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.unity_bridge import UnityBridge, UnityBridgeError, kernel
from src.unity_profiles import inspect_client, ProfileStore, select_profile
import win32gui


def main():
    folder = ROOT / "build/unity_mono_fixture"
    folder.mkdir(parents=True, exist_ok=True)
    zig = ROOT / "build/tools/zig/ziglang/zig.exe"
    for name, flags in (("UnityPlayer.dll", ["-shared", "-DFIXTURE_PLAYER"]),
                        ("mono-2.0-bdwgc.dll", ["-shared"]), ("MonoClient.exe", ["-DFIXTURE_MAIN"])):
        subprocess.run([str(zig), "cc", "-O1", "-target", "x86_64-windows-gnu", "-DFIXTURE_MONO", *flags,
            str(ROOT / "native/unity_bridge/tests/fixture.c"), "-o", str(folder / name), "-luser32"], check=True)
    data = folder / "MonoClient_Data"
    data.mkdir(exist_ok=True)
    (data / "globalgamemanagers").write_bytes(b"\0" * 32 + b"6000.4.99f1\0")
    (data / "ScriptingAssemblies.json").write_text(json.dumps({"names": ["UnityEngine.InputLegacyModule.dll", "UnityEngine.UI.dll"]}))
    profiles = folder / "profiles.json"

    def launch(flag=None):
        env = dict(os.environ)
        if flag:
            env[flag] = "1"
        proc = subprocess.Popen([str(folder / "MonoClient.exe")], cwd=folder, env=env,
            stdout=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        pid, hwnd = map(int, proc.stdout.readline().split())
        return proc, pid, hwnd

    process, pid, hwnd = launch()
    bridge = observer = None
    try:
        info = inspect_client(hwnd)
        assert info.runtime == "mono" and not info.missing_exports, info
        assert select_profile(info, ProfileStore(profiles))["backend"] == "mono-legacy-ugui"
        bridge = UnityBridge(hwnd, allow_experimental=True, profile_store_path=profiles)
        observer = mmap.mmap(-1, 44, tagname=f"Local\\ITMUnityFixture_{pid}")
        values = lambda: struct.unpack_from("<iiiiffiiiii", observer)
        cursor, foreground = win32gui.GetCursorPos(), win32gui.GetForegroundWindow()
        bridge.mouse_action(30, 45)
        v = values()
        assert v[1:3] == (1, 1) and abs(v[4] - 40) < .01 and abs(v[5] - 660) < .01, v
        bridge.key_action("key_press", "esc")
        assert values()[7:10] == (1, 1, 0), values()
        bridge.key_action("key_hold_true", "esc", hold_ms=180)
        assert values()[7:10] == (2, 2, 0), values()
        bridge.key_action("key_hold", "esc", hold_ms=260)
        assert values()[7] >= 4 and values()[7] == values()[8] and values()[9] == 0, values()
        bridge.key_action("hotkey", hotkey_keys=["ctrl", "r"])
        assert values()[10] == 1, values()
        bridge._wait_ack(bridge._command(20, 20, 1, keys=[27]))
        bridge._stop.set()
        bridge._heartbeat_thread.join()
        before = values()
        bridge.shared.heartbeat = kernel.GetTickCount64() - 2000
        time.sleep(.12)
        v = values()
        assert v[6] == v[9] == 0 and v[8] == before[8] + 1, (before, v)
        bridge.close()
        bridge = UnityBridge(hwnd, allow_experimental=True, profile_store_path=profiles)
        bridge.key_action("key_press", "esc")
        assert values()[7] == values()[8], values()
        assert cursor == win32gui.GetCursorPos() and foreground == win32gui.GetForegroundWindow()
        print("Mono: scaled coordinates, click/up, key down/up, true hold, repeat, hotkey, heartbeat release, reconnect: OK", values(), flush=True)
    finally:
        if bridge: bridge.close()
        if observer: observer.close()
        process.terminate()
        process.wait(timeout=5)

    for flag in ("ITM_FIXTURE_BAD_FIELD", "ITM_FIXTURE_NEW_INPUT", "ITM_FIXTURE_NEW_INPUT_DERIVED"):
        process, pid, hwnd = launch(flag)
        bridge = None
        try:
            try:
                bridge = UnityBridge(hwnd, allow_experimental=True, profile_store_path=profiles)
                bridge.key_action("key_press", "esc")
                raise AssertionError("Incompatible input accepted")
            except UnityBridgeError:
                observer = mmap.mmap(-1, 44, tagname=f"Local\\ITMUnityFixture_{pid}")
                v = struct.unpack_from("<iiiiffiiiii", observer)
                observer.close()
                assert v[1] == v[7] == 0, v
                print(flag, "rejected before mouse/key press: OK", flush=True)
        finally:
            if bridge: bridge.close()
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
