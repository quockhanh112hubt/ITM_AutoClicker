"""Build and run an isolated native hook/IPC/heartbeat smoke test (no real game)."""
from pathlib import Path
import ctypes
import mmap
import os
import json
import struct
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.unity_bridge import UnityBridge, UnityBridgeError, kernel
from src.unity_profiles import inspect_client, ProfileStore, select_profile
import win32gui


def main():
    zig = str(ROOT / "build/tools/zig/ziglang/zig.exe")
    folder = ROOT / "build/unity_bridge_fixture"
    folder.mkdir(parents=True, exist_ok=True)
    source = ROOT / "native/unity_bridge/tests/fixture.c"
    for filename, flags in (("UnityPlayer.dll", ["-shared", "-DFIXTURE_PLAYER"]),
                            ("GameAssembly.dll", ["-shared"]), ("OtherUnityClient.exe", ["-DFIXTURE_MAIN"])):
        subprocess.run([zig, "cc", "-O1", "-target", "x86_64-windows-gnu", *flags,
                        str(source), "-o", str(folder / filename), "-luser32"], check=True)
    data_dir=folder / "OtherUnityClient_Data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "globalgamemanagers").write_bytes(b"\0" * 32 + b"2022.3.99f1\0")
    (data_dir / "ScriptingAssemblies.json").write_text(json.dumps({"names": ["UnityEngine.InputLegacyModule.dll", "UnityEngine.UI.dll"]}))
    profiles=folder / "test_profiles.json"
    if profiles.exists(): profiles.unlink()
    process = subprocess.Popen([str(folder / "OtherUnityClient.exe")], cwd=folder, stdout=subprocess.PIPE,
                               text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    bridge = None
    try:
        line = process.stdout.readline().strip()
        if not line:
            raise RuntimeError("Fixture failed to start")
        pid, hwnd = map(int, line.split())
        info=inspect_client(hwnd)
        assert info.runtime=="il2cpp" and info.unity_version=="2022.3.99f1",info
        assert select_profile(info,ProfileStore(profiles))["id"]=="unity-legacy-lts-x64"
        try:
            UnityBridge(hwnd,profile_store_path=profiles)
            raise AssertionError("Experimental profile was enabled without opt-in")
        except UnityBridgeError as exc:
            assert "untested" in str(exc),str(exc)
        bridge = UnityBridge(hwnd,allow_experimental=True,profile_store_path=profiles)
        try:
            UnityBridge(hwnd,allow_experimental=True,profile_store_path=profiles)
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
        ProfileStore(profiles).save_client(info,"Other Unity fixture",tested=True)
        assert select_profile(info,ProfileStore(profiles))["status"]=="user-tested"
        bridge = UnityBridge(hwnd,profile_store_path=profiles)
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
    for flag, expected in (("ITM_FIXTURE_NEW_INPUT", "runtime rejected"),
                           ("ITM_FIXTURE_NEW_INPUT_DERIVED", "runtime rejected"),
                           ("ITM_FIXTURE_BAD_FIELD", "Runtime pointer or field validation failed")):
        env = dict(os.environ)
        env[flag] = "1"
        process = subprocess.Popen([str(folder / "OtherUnityClient.exe")], cwd=folder,
            stdout=subprocess.PIPE, text=True, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        bridge = None
        try:
            pid, hwnd = map(int, process.stdout.readline().split())
            try:
                bridge = UnityBridge(hwnd, allow_experimental=True, profile_store_path=profiles)
                bridge.mouse_action(25, 39)
                raise AssertionError(f"{flag} should have rejected input")
            except UnityBridgeError as exc:
                assert expected in str(exc), str(exc)
            observer = mmap.mmap(-1, 28, tagname=f"Local\\ITMUnityFixture_{pid}")
            values = struct.unpack_from("<iiiiffi", observer)
            assert values[1:3] == (0, 0), values
            observer.close()
            print(flag, "rejected before a button press: OK")
        finally:
            if bridge:
                bridge.close()
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
