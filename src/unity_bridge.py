"""Opt-in x64, in-process virtual mouse selected by Unity compatibility profile.

Loading the helper changes that game's runtime input handling. It never falls
back to global mouse input. Closing the connection restores normal input; the
inactive DLL remains resident until the game exits.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import mmap
from pathlib import Path
import secrets
import struct
import sys
import threading
import time

import win32api
import win32gui
import win32process
from src.unity_profiles import inspect_client, ProfileStore, require_profile, UnityProfileError
from src.unity_keys import unity_key_code


class UnityBridgeError(RuntimeError):
    pass


class UnityBridgeCancelled(UnityBridgeError):
    pass


class Shared(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_uint32), ("version", ctypes.c_uint32),
        ("hwnd", ctypes.c_uint64), ("owner_pid", ctypes.c_uint32), ("session", ctypes.c_uint32),
        *[(name, ctypes.c_int32) for name in ("seq", "ack", "enabled", "buttons", "x", "y", "wheel", "status")],
        ("heartbeat", ctypes.c_uint64),
        *[(name, ctypes.c_int32) for name in
          ("native_session", "frame", "position_reads", "button_reads", "updates", "focus_overrides", "error_code", "reserved")],
    ]


assert ctypes.sizeof(Shared) == 96

class MonoShared(Shared):
    _fields_ = [("keys", ctypes.c_uint32 * 16), *[(name, ctypes.c_int32) for name in
        ("key_reads", "client_width", "client_height", "render_width", "render_height", "padding")]]

assert ctypes.sizeof(MonoShared) == 184
PROTOCOL_VERSION = 2
MAPPING_PREFIX = "ITMUnityProfiles"
HELPER_NAME = "itm_unity_bridge_profiles.dll"

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
SIZE_T = ctypes.c_size_t
HANDLE = wintypes.HANDLE
for name, restype, args in (
    ("OpenProcess", HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
    ("CloseHandle", wintypes.BOOL, [HANDLE]),
    ("VirtualAllocEx", ctypes.c_void_p, [HANDLE, ctypes.c_void_p, SIZE_T, wintypes.DWORD, wintypes.DWORD]),
    ("VirtualFreeEx", wintypes.BOOL, [HANDLE, ctypes.c_void_p, SIZE_T, wintypes.DWORD]),
    ("WriteProcessMemory", wintypes.BOOL, [HANDLE, ctypes.c_void_p, ctypes.c_void_p, SIZE_T, ctypes.POINTER(SIZE_T)]),
    ("CreateRemoteThread", HANDLE, [HANDLE, ctypes.c_void_p, SIZE_T, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]),
    ("WaitForSingleObject", wintypes.DWORD, [HANDLE, wintypes.DWORD]),
    ("GetModuleHandleExW", wintypes.BOOL, [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(HANDLE)]),
    ("GetModuleFileNameW", wintypes.DWORD, [HANDLE, wintypes.LPWSTR, wintypes.DWORD]),
    ("CreateSemaphoreW", HANDLE, [ctypes.c_void_p, wintypes.LONG, wintypes.LONG, wintypes.LPCWSTR]),
    ("ReleaseSemaphore", wintypes.BOOL, [HANDLE, wintypes.LONG, ctypes.c_void_p]),
    ("GetTickCount64", ctypes.c_uint64, []),
):
    fn = getattr(kernel, name)
    fn.restype, fn.argtypes = restype, args


def _wincheck(value, operation):
    if not value:
        raise UnityBridgeError(f"{operation}: {ctypes.WinError(ctypes.get_last_error())}")
    return value


def _modules(process):
    return [(int(base), Path(win32process.GetModuleFileNameEx(process, base)))
            for base in win32process.EnumProcessModules(process)]


class ValidatedClient(tuple):
    def __new__(cls, info, profile):
        value = super().__new__(cls, (info.pid, Path(info.executable).parent))
        value.profile = profile
        return value


def validate_client(hwnd: int, profile_id="auto", allow_experimental=False, profile_store_path=None) -> tuple[int, Path]:
    """Detect and select a compatible profile before requesting write rights."""
    if struct.calcsize("P") != 8:
        raise UnityBridgeError("Unity virtual mouse requires 64-bit Python / a 64-bit application")
    try:
        info = inspect_client(hwnd)
        profile = require_profile(info, ProfileStore(profile_store_path), profile_id, allow_experimental)
        return ValidatedClient(info, profile)
    except (UnityProfileError, OSError) as exc:
        raise UnityBridgeError(str(exc)) from exc


def _load_helper(pid: int, path: Path):
    """Use the target's LoadLibraryW address; no fixed addresses or shellcode."""
    process = _wincheck(kernel.OpenProcess(0x0002 | 0x0400 | 0x0008 | 0x0020 | 0x0010, False, pid), "OpenProcess")
    remote = thread = None
    completed = False
    try:
        modules = _modules(process)
        if any(p.name.casefold() == "itm_unity_bridge.dll" for _, p in modules):
            raise UnityBridgeError("The previous MongThienKiem-only helper is loaded. Restart this game before using Unity profiles.")
        existing = [p for _, p in modules if p.name.casefold() == path.name.casefold()]
        if existing:
            if existing[0] != path:
                try:
                    with existing[0].open("rb") as first, path.open("rb") as second:
                        same = hashlib.file_digest(first, "sha256").digest() == hashlib.file_digest(second, "sha256").digest()
                except OSError:
                    same = False
                if not same:
                    raise UnityBridgeError("Another helper build is already loaded; restart the game before changing builds")
            return
        loader = ctypes.cast(kernel.LoadLibraryW, ctypes.c_void_p).value
        owner = HANDLE()
        _wincheck(kernel.GetModuleHandleExW(0x00000006, loader, ctypes.byref(owner)), "Resolve LoadLibraryW module")
        buf = ctypes.create_unicode_buffer(32768)
        _wincheck(kernel.GetModuleFileNameW(owner, buf, len(buf)), "Get loader module path")
        module_name = Path(buf.value).name.casefold()
        remote_owner = next((base for base, p in modules if p.name.casefold() == module_name), None)
        if remote_owner is None:
            raise UnityBridgeError("Cannot resolve the loader in the target process")
        remote_loader = remote_owner + loader - owner.value
        payload = ctypes.create_unicode_buffer(str(path))
        length = ctypes.sizeof(payload)
        remote = _wincheck(kernel.VirtualAllocEx(process, None, length, 0x3000, 0x04), "Allocate helper path")
        written = SIZE_T()
        _wincheck(kernel.WriteProcessMemory(process, remote, payload, length, ctypes.byref(written)), "Write helper path")
        if written.value != length:
            raise UnityBridgeError("Incomplete helper path transfer")
        thread = _wincheck(kernel.CreateRemoteThread(process, None, 0, remote_loader, remote, 0, None), "Load helper")
        result = kernel.WaitForSingleObject(thread, 10000)
        completed = result == 0
        if not completed:
            raise UnityBridgeError("Helper load did not finish within 10 seconds; no mouse fallback was used")
        if not any(p == path for _, p in _modules(process)):
            raise UnityBridgeError("The game did not load the helper DLL")
    finally:
        if thread:
            kernel.CloseHandle(thread)
        # On timeout the remote thread may still read its argument. Do not free
        # it underneath the loader; this small buffer is reclaimed on game exit.
        if remote and (not thread or completed):
            kernel.VirtualFreeEx(process, remote, 0, 0x8000)
        kernel.CloseHandle(process)


class UnityBridge:
    def __init__(self, hwnd: int, cancelled=lambda: False, *, profile_id="auto", allow_experimental=False, profile_store_path=None):
        self.hwnd = int(hwnd)
        self.cancelled = cancelled
        validated = validate_client(self.hwnd, profile_id, allow_experimental, profile_store_path)
        self.pid, self.client_dir = validated
        self.profile_id = getattr(validated, "profile", {}).get("id", profile_id)
        self._is_mono = getattr(validated, "profile", {}).get("backend") == "mono-legacy-ugui"
        shared_type = MonoShared if self._is_mono else Shared
        protocol = 3 if self._is_mono else PROTOCOL_VERSION
        prefix = "ITMUnityMono_v1" if self._is_mono else MAPPING_PREFIX
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._heartbeat_thread = None
        self._mapping = self.shared = None
        self._semaphore = None
        self._owns_semaphore = False
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        helper = (root / "resource/unity_bridge" / ("itm_unity_mono_v1.dll" if self._is_mono else HELPER_NAME)).resolve()
        if not helper.is_file():
            raise UnityBridgeError("Unity helper DLL is missing. Run: python tools/build_unity_bridge.py")
        try:
            self._semaphore = _wincheck(kernel.CreateSemaphoreW(None, 1, 1, f"Local\\{prefix}Control_{self.pid}"), "Create bridge lock")
            if kernel.WaitForSingleObject(self._semaphore, 0) != 0:
                raise UnityBridgeError("Another ITM session controls this game; stop it first")
            self._owns_semaphore = True
            self._mapping = mmap.mmap(-1, ctypes.sizeof(shared_type), tagname=f"Local\\{prefix}_{self.pid}")
            self.shared = shared_type.from_buffer(self._mapping)
            if self.shared.magic not in (0, 0x314D5449) or self.shared.version not in (0, protocol):
                raise UnityBridgeError("Incompatible helper IPC; restart the game")
            self.shared.magic, self.shared.version = 0x314D5449, protocol
            if self._is_mono:
                self.shared.keys[:] = [0] * 16
                _, _, self.shared.client_width, self.shared.client_height = win32gui.GetClientRect(self.hwnd)
            self.shared.enabled = self.shared.buttons = 0
            self.shared.hwnd = self.hwnd
            self.shared.owner_pid = win32api.GetCurrentProcessId()
            self.shared.session = secrets.randbelow(0x3fffffff) + 1
            # Recover an interrupted seqlock write from a terminated controller.
            self.shared.seq = (self.shared.seq + 2) & 0x3ffffffe
            self.shared.heartbeat = kernel.GetTickCount64()
            _load_helper(self.pid, helper)
            deadline = time.monotonic() + 10
            while self.shared.status != 2:
                if self.shared.status < 0:
                    reasons = {-1: "Unity runtime module missing", -2: "Unity runtime API missing", -3: "Unity domain unavailable",
                        -4: "Legacy Input or uGUI runtime layout does not match", -5: "Hook library unavailable",
                        -6: "An input function cannot be hooked", -7: "Hook activation failed", -8: "Runtime pointer or field validation failed",
                        -9: "The active UI uses New Input System, not Legacy Input"}
                    raise UnityBridgeError(f"Unity profile probe failed: {reasons.get(self.shared.status, 'unknown error')} "
                        f"(stage {self.shared.status}, code {self.shared.error_code}). No virtual input was enabled; restart game to retry.")
                if time.monotonic() > deadline:
                    raise UnityBridgeError("Unity helper initialization timed out; restart game before retrying")
                time.sleep(0.02)
            self._heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
            self._heartbeat_thread.start()
        except Exception:
            self.close()
            raise

    def _heartbeat(self):
        while not self._stop.wait(0.2):
            with self._lock:
                if self.shared is not None:
                    self.shared.heartbeat = kernel.GetTickCount64()

    def _command(self, x, y, buttons, wheel=0, enabled=True, keys=()):
        with self._lock:
            if self.shared is None:
                raise UnityBridgeError("Unity bridge is disconnected")
            state = self.shared
            bits = None
            if isinstance(state, MonoShared):
                bits = [0] * 16
                for key in keys:
                    if not 0 <= key < 512:
                        raise UnityBridgeError(f"Invalid Unity KeyCode: {key}")
                    bits[key // 32] |= 1 << (key % 32)
                if enabled:
                    _, _, width, height = win32gui.GetClientRect(self.hwnd)
            # This x64-only protocol has one writer (the named semaphore),
            # aligned 32-bit sequence stores, and x86 store ordering.
            state.seq += 1
            state.x, state.y = int(x), int(y)
            state.buttons, state.wheel = int(buttons), int(wheel)
            if bits is not None:
                state.keys[:] = bits
                if enabled:
                    state.client_width, state.client_height = width, height
            state.enabled = int(enabled)
            state.heartbeat = kernel.GetTickCount64()
            state.seq += 1
            return state.seq

    def _wait_ack(self, seq, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.cancelled():
                raise UnityBridgeCancelled("Unity action cancelled")
            if not win32gui.IsWindow(self.hwnd):
                raise UnityBridgeError("Game window was closed")
            with self._lock:
                if self.shared is None:
                    raise UnityBridgeError("Unity bridge was disconnected")
                if self.shared.status < 0:
                    raise UnityBridgeError("Unity runtime rejected this profile (stage " + str(self.shared.status) +
                        "). The active scene may use New Input System; export the client report for investigation.")
                if self.shared.ack == seq and self.shared.native_session == self.shared.session:
                    return
            time.sleep(0.005)
        raise UnityBridgeError("Unity did not consume the virtual mouse command; check game is running and not minimized")

    def _sleep(self, seconds):
        deadline = time.monotonic() + max(0, seconds)
        while time.monotonic() < deadline:
            if self.cancelled():
                raise UnityBridgeCancelled("Unity action cancelled")
            time.sleep(min(0.01, max(0, deadline - time.monotonic())))

    def mouse_action(self, x, y, button="left", mode="mouse_click", hold_ms=1000,
                     scroll_clicks=0, drag_to=None, drag_ms=500):
        if self.cancelled():
            raise UnityBridgeCancelled("Unity action cancelled")
        rect = win32gui.GetClientRect(self.hwnd)
        for px, py in [(x, y)] + ([drag_to] if drag_to else []):
            if not (0 <= px < rect[2] and 0 <= py < rect[3]):
                raise UnityBridgeError("Virtual mouse point is outside the game client area")
        if mode not in ("mouse_click", "mouse_hold", "mouse_scroll", "mouse_drag"):
            raise UnityBridgeError(f"Unsupported Unity virtual mouse action: {mode}")
        mask = {"left": 1, "right": 2, "middle": 4}.get(button)
        if mask is None:
            raise UnityBridgeError(f"Unsupported mouse button: {button}")
        if mode == "mouse_drag" and drag_to is None:
            raise UnityBridgeError("Unity drag destination is missing")
        before = self.diagnostics()
        try:
            self._wait_ack(self._command(x, y, 0))
            self._sleep(0.04)
            after = self.diagnostics()
            if after["position_reads"] <= before["position_reads"] or after["button_reads"] <= before["button_reads"]:
                raise UnityBridgeError("This scene did not read the virtual Legacy Input mouse. The profile is not compatible with its current input module.")
            if mode == "mouse_scroll":
                self._wait_ack(self._command(x, y, 0, wheel=scroll_clicks))
                self._sleep(0.04)
            else:
                self._wait_ack(self._command(x, y, mask))
                if mode == "mouse_drag":
                    self._sleep(0.05)
                    steps = max(2, min(120, int(drag_ms / 20)))
                    for step in range(1, steps + 1):
                        ratio = step / steps
                        nx = x + (drag_to[0] - x) * ratio
                        ny = y + (drag_to[1] - y) * ratio
                        self._wait_ack(self._command(nx, ny, mask))
                        self._sleep(max(0, drag_ms / 1000 / steps))
                    x, y = drag_to
                else:
                    self._sleep(max(0, hold_ms) / 1000 if mode == "mouse_hold" else 0.06)
            self._wait_ack(self._command(x, y, 0))
            self._sleep(0.04)
        finally:
            self.release()

    def release(self):
        with self._lock:
            if self.shared is not None:
                self._command(self.shared.x, self.shared.y, 0, enabled=False)

    def key_action(self, mode, key_name="", hotkey_keys=(), hold_ms=1000):
        if not self._is_mono:
            raise UnityBridgeError("Virtual keyboard currently requires a Unity Mono profile")
        if mode not in ("key_press", "key_hold", "key_hold_true", "hotkey"):
            raise UnityBridgeError(f"Unsupported Unity keyboard action: {mode}")
        try:
            codes = [unity_key_code(k) for k in (hotkey_keys if mode == "hotkey" else [key_name])]
        except ValueError as exc:
            raise UnityBridgeError(str(exc)) from exc
        if not codes:
            raise UnityBridgeError("Unity keyboard action has no keys")
        if self.cancelled():
            raise UnityBridgeCancelled("Unity action cancelled")
        state = self.shared
        x, y = state.x, state.y
        before = state.key_reads
        try:
            self._wait_ack(self._command(x, y, 0))
            self._sleep(0.04)
            if mode == "key_hold":
                deadline = time.monotonic() + max(0, hold_ms) / 1000
                while True:
                    self._wait_ack(self._command(x, y, 0, keys=codes))
                    self._sleep(0.06)
                    self._wait_ack(self._command(x, y, 0))
                    self._sleep(0.04)
                    if time.monotonic() >= deadline:
                        break
            else:
                self._wait_ack(self._command(x, y, 0, keys=codes))
                self._sleep(max(0.06, hold_ms / 1000) if mode == "key_hold_true" else 0.08)
            self._wait_ack(self._command(x, y, 0))
            self._sleep(0.04)
            if state.key_reads <= before:
                raise UnityBridgeError("This scene did not read Unity Legacy GetKey; its keyboard path is not supported")
        finally:
            self.release()

    def diagnostics(self):
        with self._lock:
            if self.shared is None:
                return {"connected": False}
            extra = {name: getattr(self.shared, name) for name in ("key_reads", "client_width", "client_height", "render_width", "render_height")} if isinstance(self.shared, MonoShared) else {}
            return {"connected": True, "profile_id": self.profile_id, **extra, **{name: getattr(self.shared, name) for name in
                    ("status", "frame", "ack", "position_reads", "button_reads", "updates", "focus_overrides")}}

    def close(self):
        self._stop.set()
        if self._heartbeat_thread and self._heartbeat_thread is not threading.current_thread():
            self._heartbeat_thread.join(timeout=1)
        with self._lock:
            self.release()
            self.shared = None
            if self._mapping is not None:
                self._mapping.close()
                self._mapping = None
            if self._semaphore:
                if self._owns_semaphore:
                    kernel.ReleaseSemaphore(self._semaphore, 1, None)
                kernel.CloseHandle(self._semaphore)
                self._semaphore = None
                self._owns_semaphore = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
