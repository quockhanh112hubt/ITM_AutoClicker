"""Build the x64 prototype using a local Zig toolchain and vendored MinHook.

Bootstrap, once: python -m pip install --target build/tools/zig ziglang==0.14.1
Build: python tools/build_unity_bridge.py
"""
from pathlib import Path
import os
import shutil
import subprocess
import argparse

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("all", "il2cpp", "mono"), default="all")
    args = parser.parse_args()
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
               "-shared", "-o", str(staging / "itm_unity_bridge_profiles.dll"),
               "-I", str(vendor / "include"), str(source / "bridge.c"),
               *[str(vendor / "src" / name) for name in ("hook.c", "buffer.c", "trampoline.c")],
               str(vendor / "src/hde/hde64.c"), "-luser32"]
    for backend in (("il2cpp", "mono") if args.backend == "all" else (args.backend,)):
        filename = "itm_unity_mono_v1.dll" if backend == "mono" else "itm_unity_bridge_profiles.dll"
        build = list(command)
        build[build.index("-o") + 1] = str(staging / filename)
        if backend == "mono":
            build.append("-DMONO_BACKEND")
        subprocess.run(build, cwd=ROOT, check=True)
        try:
            shutil.copyfile(staging / filename, output / filename)
        except PermissionError:
            raise SystemExit(f"{filename} is loaded in a game. Exit that game before replacing the DLL.")
        print(output / filename)
    shutil.copyfile(vendor / "LICENSE.txt", output / "MINHOOK_LICENSE.txt")


if __name__ == "__main__":
    main()
