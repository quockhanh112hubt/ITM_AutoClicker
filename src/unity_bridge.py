"""Opt-in x64, in-process virtual mouse for one explicitly supported client build.

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
FINGERPRINTS = {
    "UnityPlayer.dll": "3fc09d493e387c33b2c0df29d9ec75803158a3a98ad885917b1039d13bfc6c6d",
    "GameAssembly.dll": "802f3a21bd70ca083b4f1cc748acc6a2c8c32cece75ce38c9ab656a27694cc2d",
}

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


def validate_client(hwnd: int) -> tuple[int, Path]:
    """Reject other games/builds before requesting write/thread process rights."""
    if struct.calcsize("P") != 8:
        raise UnityBridgeError("Unity virtual mouse requires 64-bit Python / a 64-bit application")
    if not win32gui.IsWindow(hwnd) or win32gui.GetClassName(hwnd) != "UnityWndClass":
        raise UnityBridgeError("Select the supported MongThienKiem client window first")
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
    try:
        executable = Path(win32process.GetModuleFileNameEx(process, 0))
        modules = _modules(process)
    finally:
        win32api.CloseHandle(process)
    if executable.name.casefold() != "mongthienkiem.exe":
        raise UnityBridgeError("This prototype supports MongThienKiem.exe only")
    root = executable.parent
    loaded = {p.name.casefold(): p for _, p in modules}
    for name, expected in FINGERPRINTS.items():
        path = root / name
        if loaded.get(name.casefold()) != path or not path.is_file():
            raise UnityBridgeError(f"Expected client module is not loaded: {name}")
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != expected:
            raise UnityBridgeError(f"Unsupported MongThienKiem build ({name} fingerprint differs); helper was not loaded")
    return pid, root


def _load_helper(pid: int, path: Path):
    """Use the target's LoadLibraryW address; no fixed addresses or shellcode."""
    process = _wincheck(kernel.OpenProcess(0x0002 | 0x0400 | 0x0008 | 0x0020 | 0x0010, False, pid), "OpenProcess")
    remote = thread = None
    completed = False
    try:
        modules = _modules(process)
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
    def __init__(self, hwnd: int, cancelled=lambda: False):
        self.hwnd = int(hwnd)
        self.cancelled = cancelled
        self.pid, self.client_dir = validate_client(self.hwnd)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._heartbeat_thread = None
        self._mapping = self.shared = None
        self._semaphore = None
        self._owns_semaphore = False
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        helper = (root / "resource/unity_bridge/itm_unity_bridge.dll").resolve()
        if not helper.is_file():
            raise UnityBridgeError("Unity helper DLL is missing. Run: python tools/build_unity_bridge.py")
        try:
            self._semaphore = _wincheck(kernel.CreateSemaphoreW(None, 1, 1, f"Local\\ITMUnityBridgeControl_{self.pid}"), "Create bridge lock")
            if kernel.WaitForSingleObject(self._semaphore, 0) != 0:
                raise UnityBridgeError("Another ITM session controls this game; stop it first")
            self._owns_semaphore = True
            self._mapping = mmap.mmap(-1, ctypes.sizeof(Shared), tagname=f"Local\\ITMUnityBridge_{self.pid}")
            self.shared = Shared.from_buffer(self._mapping)
            if self.shared.magic not in (0, 0x314D5449) or self.shared.version not in (0, 1):
                raise UnityBridgeError("Incompatible helper IPC; restart the game")
            self.shared.magic, self.shared.version = 0x314D5449, 1
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
                    raise UnityBridgeError(f"Unity helper initialization failed (stage {self.shared.status}, code {self.shared.error_code}); restart game to retry")
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

    def _command(self, x, y, buttons, wheel=0, enabled=True):
        with self._lock:
            if self.shared is None:
                raise UnityBridgeError("Unity bridge is disconnected")
            state = self.shared
            # This x64-only protocol has one writer (the named semaphore),
            # aligned 32-bit sequence stores, and x86 store ordering.
            state.seq += 1
            state.x, state.y = int(x), int(y)
            state.buttons, state.wheel = int(buttons), int(wheel)
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
        try:
            self._wait_ack(self._command(x, y, 0))
            self._sleep(0.04)
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

    def diagnostics(self):
        with self._lock:
            if self.shared is None:
                return {"connected": False}
            return {"connected": True, **{name: getattr(self.shared, name) for name in
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
