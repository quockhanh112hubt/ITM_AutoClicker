"""Build and execute the isolated absolute Mono JIT hook regression."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    vendor = ROOT / "native/unity_bridge/vendor/minhook"
    output = ROOT / "build/unity_bridge_fixture/far_hook.exe"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ROOT / "build/tools/zig/ziglang/zig.exe"), "cc", "-target", "x86_64-windows-gnu",
        "-O2", "-Wall", "-Wextra", "-DMONO_BACKEND", "-I", str(vendor / "include"),
        str(ROOT / "native/unity_bridge/tests/far_hook.c"),
        *[str(vendor / "src" / n) for n in ("hook.c", "buffer.c", "trampoline.c", "hde/hde64.c")],
        "-luser32", "-o", str(output)], check=True)
    subprocess.run([str(output)], check=True)

if __name__ == "__main__":
    main()
