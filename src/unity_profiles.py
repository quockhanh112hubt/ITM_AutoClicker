"""Read-only Unity detection and data-only compatibility profiles.

Static detection establishes eligibility for a runtime probe, not that a game
has accepted a click. No game input or process modification occurs here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct
import sys
import tempfile
import os

import win32api
import win32gui
import win32process

BACKEND = "il2cpp-legacy-ugui"
REQUIRED_EXPORTS = frozenset("il2cpp_" + name for name in (
    "domain_get", "thread_attach", "thread_detach", "domain_get_assemblies",
    "assembly_get_image", "image_get_name", "class_from_name", "class_get_method_from_name",
    "class_get_field_from_name", "field_get_offset", "field_get_type", "type_get_type",
    "class_instance_size", "resolve_icall",
    "object_get_class", "class_get_name", "class_get_namespace",
    "class_get_parent",
))


class UnityProfileError(ValueError):
    pass


@dataclass
class ClientInfo:
    hwnd: int
    pid: int
    title: str
    executable: str
    window_class: str = ""
    architecture: str = "unknown"
    unity_version: str = "unknown"
    runtime: str = "not-unity"
    input_system: str = "unknown"
    has_ugui: bool = False
    legacy_calls: bool = False
    fingerprints: dict[str, str] = field(default_factory=dict)
    missing_exports: list[str] = field(default_factory=list)
    assemblies: list[str] = field(default_factory=list)
    modules: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def report(self):
        return asdict(self)


def pe_info(path: Path, read_exports=False) -> tuple[str, set[str]]:
    """Small bounded PE reader; avoids adding pefile to the app dependencies."""
    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            def unpack(fmt, at):
                if at < 0 or at + struct.calcsize(fmt) > len(data):
                    raise UnityProfileError(f"Invalid PE structure: {path.name}")
                return struct.unpack_from(fmt, data, at)
            if data[:2] != b"MZ":
                raise UnityProfileError(f"Not a Windows executable: {path.name}")
            offset, = unpack("<I", 0x3c)
            if data[offset:offset + 4] != b"PE\0\0":
                raise UnityProfileError(f"Invalid PE signature: {path.name}")
            machine, sections = unpack("<HH", offset + 4)
            architecture = {0x8664: "x64", 0x14c: "x86", 0xaa64: "arm64"}.get(machine, "unknown")
            if not read_exports:
                return architecture, set()
            optional_size, = unpack("<H", offset + 20)
            optional = offset + 24
            magic, = unpack("<H", optional)
            directory_offset = {0x20b: 112, 0x10b: 96}.get(magic)
            if directory_offset is None or sections > 96:
                raise UnityProfileError(f"Unsupported PE layout: {path.name}")
            table = optional + optional_size
            ranges = []
            for index in range(sections):
                virtual_size, rva, raw_size, raw = unpack("<IIII", table + index * 40 + 8)
                ranges.append((rva, min(virtual_size or raw_size, raw_size), raw))
            def location(rva, length=1):
                for start, size, raw in ranges:
                    if start <= rva and rva + length <= start + size and raw + rva - start + length <= len(data):
                        return raw + rva - start
                raise UnityProfileError(f"PE address outside file sections: {path.name}")
            export_rva, export_size = unpack("<II", optional + directory_offset)
            if not export_rva or not export_size:
                return architecture, set()
            export = location(export_rva, 40)
            count, = unpack("<I", export + 24)
            names_rva, = unpack("<I", export + 32)
            if count > 100000:
                raise UnityProfileError(f"Unreasonable export table: {path.name}")
            names = location(names_rva, count * 4) if count else 0
            found = set()
            for i in range(count):
                name_rva, = unpack("<I", names + 4 * i)
                at = location(name_rva)
                end = data.find(b"\0", at, min(at + 512, len(data)))
                if end < 0:
                    raise UnityProfileError(f"Invalid export name: {path.name}")
                found.add(data[at:end].decode("ascii", errors="replace"))
            return architecture, found


def _version(player: Path, data_dir: Path):
    try:
        for language, codepage in win32api.GetFileVersionInfo(str(player), "\\VarFileInfo\\Translation"):
            value = win32api.GetFileVersionInfo(str(player),
                f"\\StringFileInfo\\{language:04x}{codepage:04x}\\ProductVersion")
            match = re.search(r"\b\d{4}\.\d+\.\d+[abfp]\d+", str(value))
            if match:
                return match.group(0)
    except Exception:
        pass
    asset = data_dir / "globalgamemanagers"
    if asset.is_file():
        with asset.open("rb") as stream:
            match = re.search(rb"\d{4}\.\d+\.\d+[abfp]\d+", stream.read(256))
            if match:
                return match.group(0).decode("ascii")
    return "unknown"


def inspect_files(executable: Path, modules: dict[str, str], *, hwnd=0, pid=0, title="", window_class=""):
    """Inspectable without a live process, also used by isolated fixtures."""
    executable = Path(executable)
    info = ClientInfo(hwnd, pid, title, str(executable), window_class)
    info.modules = {name.casefold(): str(Path(value)) for name, value in modules.items()}
    info.architecture, _ = pe_info(executable)
    player_path = info.modules.get("unityplayer.dll")
    if not player_path:
        info.notes.append("No loaded UnityPlayer.dll was found.")
        return info
    player = Path(player_path)
    root = executable.parent
    if player.parent != root:
        info.notes.append("UnityPlayer.dll is not beside the selected executable; this layout is not supported yet.")
    data_dir = root / (executable.stem + "_Data")
    info.unity_version = _version(player, data_dir)
    assembly_path = info.modules.get("gameassembly.dll")
    mono = any(name.startswith("mono") and name.endswith(".dll") for name in info.modules)
    info.runtime = "il2cpp" if assembly_path else ("mono" if mono else "unknown")
    assembly_json = data_dir / "ScriptingAssemblies.json"
    if assembly_json.is_file():
        try:
            if assembly_json.stat().st_size > 2 * 1024 * 1024:
                raise UnityProfileError("Assembly list is too large")
            payload = json.loads(assembly_json.read_text(encoding="utf-8-sig"))
            names = payload.get("names", []) if isinstance(payload, dict) else []
            info.assemblies = sorted({str(name) for name in names if isinstance(name, str)})
        except (ValueError, OSError) as exc:
            info.notes.append(f"Cannot read assembly list: {exc}")
    else:
        managed = data_dir / "Managed"
        if managed.is_dir():
            info.assemblies = sorted(p.name for p in managed.glob("*.dll"))
    if not info.assemblies and assembly_path:
        metadata = data_dir / "il2cpp_data/Metadata/global-metadata.dat"
        if metadata.is_file() and metadata.stat().st_size:
            # Only look for null-terminated assembly identifiers, not guessed
            # metadata table offsets (which differ between Unity releases).
            with metadata.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as binary:
                for name in ("UnityEngine.InputLegacyModule", "Unity.InputSystem", "UnityEngine.UI"):
                    if any(binary.find(term) >= 0 for term in (name.encode() + b"\0", name.encode() + b".dll\0")):
                        info.assemblies.append(name + ".dll")
            info.notes.append("Assembly evidence came from metadata identifiers; runtime behavior still needs testing.")
    names = {name.casefold() for name in info.assemblies}
    legacy = "unityengine.inputlegacymodule.dll" in names
    new_input = "unity.inputsystem.dll" in names
    info.has_ugui = "unityengine.ui.dll" in names
    info.input_system = "both" if legacy and new_input else "legacy" if legacy else "new" if new_input else "unknown"
    if assembly_path:
        assembly = Path(assembly_path)
        arch, exports = pe_info(assembly, read_exports=True)
        if arch != info.architecture or pe_info(player)[0] != info.architecture:
            info.notes.append("The executable and Unity native modules have different architectures.")
        info.missing_exports = sorted(REQUIRED_EXPORTS - exports)
        with assembly.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as binary:
            info.legacy_calls = all(binary.find(term) >= 0 for term in (
                b"UnityEngine.Input::get_mousePosition_Injected(UnityEngine.Vector3&)",
                b"UnityEngine.Input::GetMouseButtonDown(System.Int32)",
                b"UnityEngine.Input::GetMouseButtonUp(System.Int32)",
                b"UnityEngine.Input::GetMouseButton(System.Int32)",
            ))
        if assembly.parent != root:
            info.notes.append("GameAssembly.dll is not beside the selected executable; this layout is not supported yet.")
        for name, path in (("UnityPlayer.dll", player), ("GameAssembly.dll", assembly)):
            with path.open("rb") as stream:
                info.fingerprints[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return info


def inspect_client(hwnd: int) -> ClientInfo:
    """Read module paths, on-disk metadata and hashes using read-only rights."""
    if not win32gui.IsWindow(hwnd):
        raise UnityProfileError("The selected window is no longer available")
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    process = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
    try:
        executable = Path(win32process.GetModuleFileNameEx(process, 0))
        modules = {}
        for base in win32process.EnumProcessModules(process):
            path = Path(win32process.GetModuleFileNameEx(process, base))
            modules[path.name.casefold()] = str(path)
    finally:
        win32api.CloseHandle(process)
    info = inspect_files(executable, modules, hwnd=int(hwnd), pid=int(pid),
        title=win32gui.GetWindowText(hwnd), window_class=win32gui.GetClassName(hwnd))
    if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid:
        raise UnityProfileError("The target changed while inspecting it; select it again")
    return info


def eligibility(info: ClientInfo) -> str:
    """An empty reason means eligible for a native runtime probe, not verified."""
    if info.runtime == "not-unity":
        return "This window does not have a loaded UnityPlayer.dll."
    if info.architecture != "x64":
        return f"Detected {info.architecture}; virtual mouse currently supports x64 only."
    if info.runtime != "il2cpp":
        return f"Detected {info.runtime}; a {info.runtime} input backend is not implemented yet."
    if not re.match(r"^(2019|2020|2021|2022|2023|6000)\.", info.unity_version):
        return f"Unity {info.unity_version} is outside the engine families supported by this test backend."
    if any("not supported" in note or "different architectures" in note for note in info.notes):
        return " ".join(info.notes)
    if info.missing_exports:
        return "IL2CPP runtime does not expose all required APIs: " + ", ".join(info.missing_exports)
    if info.input_system == "new":
        return "New Input System detected; this backend handles Legacy Input/uGUI only."
    if not info.legacy_calls:
        return "The expected Legacy Input bindings were not found in GameAssembly.dll."
    if not info.has_ugui:
        return "Cannot confirm the Unity uGUI assembly; no compatible UI backend is available."
    return ""


def default_store_path():
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    return root / "config/unity_profiles.json"


class ProfileStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_store_path()
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        payload = json.loads((resource_root / "resource/unity_bridge/profiles.json").read_text(encoding="utf-8-sig"))
        self.builtins = payload["profiles"]
        self.custom = []
        self.load_error = ""
        if self.path.is_file():
            try:
                if self.path.stat().st_size > 1024 * 1024:
                    raise UnityProfileError("Profile file is too large")
                saved = json.loads(self.path.read_text(encoding="utf-8-sig"))
                if saved.get("version") != 1 or not isinstance(saved.get("profiles"), list):
                    raise UnityProfileError("Invalid profile format")
                if len(saved["profiles"]) > 200:
                    raise UnityProfileError("Too many saved profiles")
                ids = {p["id"] for p in self.builtins}
                for p in saved["profiles"]:
                    self._validate_saved(p)
                    if p["id"] in ids:
                        raise UnityProfileError("Duplicate profile id")
                    ids.add(p["id"])
                    self.custom.append(p)
            except (ValueError, TypeError, AttributeError, OSError) as exc:
                self.load_error = str(exc)
                self.custom = []

    @staticmethod
    def _validate_saved(p):
        if not isinstance(p, dict) or p.get("backend") != BACKEND:
            raise UnityProfileError("Unknown saved backend")
        if not re.fullmatch(r"client-[a-f0-9]{20}", str(p.get("id", ""))):
            raise UnityProfileError("Invalid saved profile id")
        if p.get("status") not in ("experimental", "user-tested"):
            raise UnityProfileError("Saved profiles cannot claim built-in verification")
        if not isinstance(p.get("name"), str) or not 1 <= len(p["name"]) <= 120:
            raise UnityProfileError("Invalid profile name")
        if not isinstance(p.get("executable"), str) or Path(p["executable"]).name != p["executable"]:
            raise UnityProfileError("Invalid executable name")
        hashes = p.get("fingerprints", {})
        if not isinstance(hashes, dict) or set(hashes) != {"UnityPlayer.dll", "GameAssembly.dll"}:
            raise UnityProfileError("Saved profiles need both native module fingerprints")
        if any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in hashes.values()):
            raise UnityProfileError("Invalid saved fingerprint")
        if p.get("id") != _saved_id(p["executable"], hashes):
            raise UnityProfileError("Saved profile id does not match its build fingerprints")

    @property
    def profiles(self):
        return [*self.builtins, *self.custom]

    def save_client(self, info: ClientInfo, name: str, tested=False):
        reason = eligibility(info)
        if reason:
            raise UnityProfileError(reason)
        if self.load_error:
            raise UnityProfileError(f"Fix the saved profile file before saving: {self.load_error}")
        profile = {"id": _saved_id(Path(info.executable).name, info.fingerprints),
            "name": name.strip(), "status": "user-tested" if tested else "experimental",
            "backend": BACKEND, "executable": Path(info.executable).name,
            "unity_version": info.unity_version, "fingerprints": dict(info.fingerprints)}
        self._validate_saved(profile)
        previous = next((p for p in self.custom if p["id"] == profile["id"]), None)
        if previous and previous["status"] == "user-tested" and not tested:
            profile["status"] = "user-tested"
        updated = [p for p in self.custom if p["id"] != profile["id"]] + [profile]
        if len(updated) > 200:
            raise UnityProfileError("Too many saved profiles")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"version": 1, "profiles": updated}, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        self.custom = updated
        return profile


def _saved_id(executable, fingerprints):
    payload = executable.casefold() + "|" + "|".join(fingerprints[key] for key in sorted(fingerprints))
    return "client-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def profile_matches(profile, info):
    if profile.get("fingerprints"):
        return (profile.get("executable", "").casefold() == Path(info.executable).name.casefold()
                and profile["fingerprints"] == info.fingerprints)
    try:
        major = int(info.unity_version.split(".")[0])
    except ValueError:
        return False
    return major in profile.get("unity_majors", [])


def select_profile(info: ClientInfo, store: ProfileStore, profile_id="auto"):
    reason = eligibility(info)
    if reason:
        raise UnityProfileError(reason)
    if profile_id != "auto":
        profile = next((p for p in store.profiles if p["id"] == profile_id), None)
        if profile is None:
            raise UnityProfileError("Selected profile is missing; choose Auto detect or refresh profiles.")
        if not profile_matches(profile, info):
            raise UnityProfileError("Selected profile does not match this client build. Choose Auto detect to inspect the new build.")
        return profile
    matches = [p for p in store.profiles if profile_matches(p, info)]
    if not matches:
        raise UnityProfileError(f"Detected Unity {info.unity_version}; no profile covers this engine version yet.")
    ranks = {"verified": 0, "user-tested": 1, "experimental": 2}
    return min(matches, key=lambda p: (ranks.get(p["status"], 9), not bool(p.get("fingerprints"))))


def require_profile(info, store, profile_id="auto", allow_experimental=False):
    profile = select_profile(info, store, profile_id)
    if profile["status"] == "experimental" and not allow_experimental:
        raise UnityProfileError(f"{profile['name']} is untested for this build. Enable 'Allow experimental Unity profiles' to try it.")
    return profile
