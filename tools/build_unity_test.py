"""Package the test application separately from the regular release artifact."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    helper = ROOT / "resource/unity_bridge/itm_unity_bridge.dll"
    if not helper.is_file():
        raise SystemExit("Build the native helper first: python tools/build_unity_bridge.py")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", "ITM_AutoClicker_Unity_Test",
        "--workpath", str(ROOT / "build/unity_test_pyinstaller"),
        "--specpath", str(ROOT / "build/unity_test_pyinstaller"),
        "--distpath", str(ROOT / "dist"),
        "--icon", str(ROOT / "resource/Icon.ico"),
        "--add-data", f"{ROOT / 'qt.conf'};.",
        "--add-data", f"{ROOT / 'resource'};resource",
        str(ROOT / "main.py"),
    ], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
