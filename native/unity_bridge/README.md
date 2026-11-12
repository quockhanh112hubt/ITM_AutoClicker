# ITM Unity virtual mouse prototype

This opt-in helper is specific to the MongThienKiem Unity 6000.3.25f1 x64 build
fingerprinted in `src/unity_bridge.py`. Other builds fail validation before loading.
It does not patch files on disk. It loads a DLL into the selected game's process
and installs runtime detours; Stop disables the virtual input, while the inactive
helper remains resident until game exit. Reconnect reuses that helper.

## Build

From the repository root, using 64-bit Python:

```powershell
.\.venv\Scripts\python.exe -m pip install --target build/tools/zig ziglang==0.14.1
.\.venv\Scripts\python.exe tools/build_unity_bridge.py
```

Zig is installed only into the ignored `build/tools/zig` directory. A system `zig`
or `ITM_ZIG` executable override is also supported. Exit the game before replacing
a loaded helper binary. The packaged app includes `resource/unity_bridge` through
the existing PyInstaller resource rule. Compiler outputs stay in `build`; only the
DLL and its third-party license are copied into resources.

To package a separate test executable with the existing PyInstaller environment:

```powershell
.\.venv\Scripts\python.exe tools/build_unity_test.py
```

Output: `dist/ITM_AutoClicker_Unity_Test.exe`.

## Design and limits

- MinHook detours Unity's native Legacy Input position, scroll and button getters.
- The EventSystem.Update detour temporarily supplies focus only to that Unity
  EventSystem while it runs; it does not activate the Windows window.
- Down/Up state is consistent across all consumers in a Unity frame. The native
  side acknowledges a command after an EventSystem update, which is not proof
  of a particular UI result.
- Screen conversion uses the current client and Unity render dimensions. Points
  outside the client fail before a gesture is sent.
- A local shared-memory protocol has one controller at a time. Disabled mode
  forwards to original engine functions. A 1.2-second expired heartbeat supplies
  one virtual release frame and then forwards to the original functions.
- No SetCursorPos, SendInput, global keyboard input or foreground-window fallback
  is used by the virtual mouse backend.
- The prototype handles mouse click/hold/scroll/drag. Keyboard actions and Full
  Screen targeting are rejected. Minimized game windows are not supported.
- Do not treat this as a general Unity/game backend. A different executable build
  requires investigation and validation before extending the fingerprint list.

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B tools/test_unity_bridge_native.py
```

The second command compiles and launches a hidden, disposable fixture process.
It tests actual DLL loading, detours, IPC, coordinate mapping, focus substitution,
reconnect and lost-heartbeat release without accessing the real game.

```powershell
# Verify client build; does not load a helper or send input:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py
# Explicitly load and inspect; no gesture:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py --connect
```

`--click X Y` sends one click in **client** coordinates. It requires the cursor
outside the game and a different foreground application. Choose a harmless menu
button using the current window layout; coordinates are not universal.

## Third-party source

`vendor/minhook` contains only the C sources/headers and license from
[TsudaKageyu/minhook v1.3.4](https://github.com/TsudaKageyu/minhook/tree/v1.3.4),
downloaded from the official release tag. Keep the included `LICENSE.txt`,
which includes the licenses for MinHook's components, when redistributing.
