"""Build the x64 prototype using a local Zig toolchain and vendored MinHook.

Bootstrap, once: python -m pip install --target build/tools/zig ziglang==0.14.1
Build: python tools/build_unity_bridge.py
"""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    zig = os.environ.get("ITM_ZIG") or shutil.which("zig")
    if not zig:
        candidate = ROOT / "build/tools/zig/ziglang/zig.exe"
        if candidate.is_file():
            zig = str(candidate)
    if not zig:
        raise SystemExit("Install Zig: python -m pip install --target build/tools/zig ziglang==0.14.1")
    source = ROOT / "native/unity_bridge"
    vendor = source / "vendor/minhook"
    output = ROOT / "resource/unity_bridge"
    output.mkdir(parents=True, exist_ok=True)
    staging = ROOT / "build/unity_bridge_native"
    staging.mkdir(parents=True, exist_ok=True)
    command = [zig, "cc", "-target", "x86_64-windows-gnu", "-O2", "-Wall", "-Wextra",
               "-shared", "-o", str(staging / "itm_unity_bridge.dll"),
               "-I", str(vendor / "include"), str(source / "bridge.c"),
               *[str(vendor / "src" / name) for name in ("hook.c", "buffer.c", "trampoline.c")],
               str(vendor / "src/hde/hde64.c"), "-luser32"]
    subprocess.run(command, cwd=ROOT, check=True)
    try:
        shutil.copyfile(staging / "itm_unity_bridge.dll", output / "itm_unity_bridge.dll")
    except PermissionError:
        raise SystemExit("The helper is loaded in a game. Exit that game before replacing the DLL.")
    shutil.copyfile(vendor / "LICENSE.txt", output / "MINHOOK_LICENSE.txt")
    print(output / "itm_unity_bridge.dll")


if __name__ == "__main__":
    main()
