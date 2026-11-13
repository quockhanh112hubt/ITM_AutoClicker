# ITM Unity virtual mouse compatibility profiles

The opt-in helper uses profiles in `resource/unity_bridge/profiles.json` plus
user-saved exact-build profiles. MongThienKiem has a fingerprinted, verified client
profile. Other eligible IL2CPP x64 / Legacy Input / uGUI clients from Unity
2019–2023 and Unity 6 (6000.x) use explicitly experimental engine-family profiles.
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

Output: `dist/ITM_AutoClicker_Unity_Profiles_Test.exe`.
Native DLL: `resource/unity_bridge/itm_unity_bridge_profiles.dll` (protocol 2).
The old MongThienKiem-only helper must not already be loaded; restart the game
once when moving from the previous test build. DLLs from different builds are
never stacked on top of each other.

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
- Detection reads the selected process's module paths and on-disk PE/Unity
  metadata. Selecting/refreshing/exporting a client never loads the helper.
- Exact profile identity includes executable name and both native DLL hashes.
  A game update does not inherit the previous user test result.
- Native initialization validates the EventSystem fields' types/offsets against
  the runtime instance size and verifies that hook addresses are executable and
  belong to the expected Unity modules before enabling any detour.
- If the active EventSystem uses InputSystemUIInputModule, the helper rejects the
  profile before a button press. A scene that never reads virtual Legacy Input
  also fails the first gesture's hover probe.
- Family matches are eligibility checks, not a guarantee that a game accepts
  input. Mono, x86, ARM and New Input System-only clients remain unsupported.

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B tools/test_unity_bridge_native.py
```

The second command compiles and launches a hidden, disposable, renamed fixture
with separate fake UnityPlayer/GameAssembly modules. It exercises real detection,
experimental opt-in, DLL loading, pointer validation, detours, IPC, coordinates,
focus substitution, saved profiles, reconnect and lost-heartbeat release.
Additional fixture processes verify rejection of New Input System UI and an
incompatible field layout before a button press. These are synthetic runtime
tests, not evidence that real Unity 2022 games were tested.

```powershell
# Inspect a selected client; does not load a helper or send input:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py
# Inspect another title / export a report:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py --window-title "Other game" --report client.json
# Explicitly load and inspect; no gesture:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py --connect
# Allow an eligible, untested engine-family profile:
.\.venv\Scripts\python.exe tools/unity_mouse_probe.py --window-title "Other game" --allow-experimental --connect
```

`--click X Y` sends one click in **client** coordinates. It requires the cursor
outside the game and a different foreground application. Choose a harmless menu
button using the current window layout; coordinates are not universal.

## Third-party source

`vendor/minhook` contains only the C sources/headers and license from
[TsudaKageyu/minhook v1.3.4](https://github.com/TsudaKageyu/minhook/tree/v1.3.4),
downloaded from the official release tag. Keep the included `LICENSE.txt`,
which includes the licenses for MinHook's components, when redistributing.
