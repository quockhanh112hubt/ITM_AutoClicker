"""Profile identity, capability gates, persistence and bounded PE parsing."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from src.unity_profiles import (ClientInfo, ProfileStore, UnityProfileError,
    eligibility, select_profile, require_profile, pe_info)
from src.unity_bridge import UnityBridge, UnityBridgeError, _load_helper, HELPER_NAME


def candidate(executable="OtherGame.exe", version="6000.3.25f1"):
    return ClientInfo(123, 456, "Other Unity game", str(Path("C:/Games") / executable),
        "UnityWndClass", "x64", version, "il2cpp", "legacy", True, True,
        {"UnityPlayer.dll": "a" * 64, "GameAssembly.dll": "b" * 64})


class UnityProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "profiles.json"
        self.store = ProfileStore(self.path)

    def known_client(self):
        info = candidate("MongThienKiem.exe")
        info.fingerprints = dict(self.store.builtins[0]["fingerprints"])
        return info

    def test_builtin_exact_build_is_verified_without_trial_opt_in(self):
        self.assertEqual(require_profile(self.known_client(), self.store)["status"], "verified")

    def test_other_unity6_game_uses_experimental_family(self):
        info = candidate()
        self.assertEqual(select_profile(info, self.store)["id"], "unity6-legacy-x64")
        with self.assertRaisesRegex(UnityProfileError, "untested"):
            require_profile(info, self.store)
        self.assertEqual(require_profile(info, self.store, allow_experimental=True)["status"], "experimental")

    def test_unity2022_uses_its_own_family(self):
        self.assertEqual(select_profile(candidate(version="2022.3.40f1"), self.store)["id"], "unity-legacy-lts-x64")

    def test_game_update_never_inherits_old_verification(self):
        info = self.known_client()
        info.fingerprints["GameAssembly.dll"] = "c" * 64
        self.assertEqual(select_profile(info, self.store)["status"], "experimental")
        with self.assertRaisesRegex(UnityProfileError, "does not match"):
            select_profile(info, self.store, self.store.builtins[0]["id"])

    def test_runtime_and_capability_rejections_cannot_be_bypassed_by_trial(self):
        for key, value in (("runtime", "mono"), ("runtime", "not-unity"),
                           ("architecture", "x86"), ("architecture", "arm64"),
                           ("input_system", "new"), ("legacy_calls", False),
                           ("has_ugui", False), ("unity_version", "unknown"),
                           ("unity_version", "2018.4.1f1"), ("missing_exports", ["il2cpp_resolve_icall"])):
            with self.subTest(key=key, value=value):
                info = candidate()
                setattr(info, key, value)
                with self.assertRaises(UnityProfileError):
                    require_profile(info, self.store, allow_experimental=True)

    def test_mixed_input_is_eligible_but_not_verified(self):
        info = candidate()
        info.input_system = "both"
        self.assertEqual(select_profile(info, self.store)["status"], "experimental")

    def test_saved_test_result_is_bound_to_both_dll_hashes(self):
        info = candidate()
        saved = self.store.save_client(info, "My game", tested=True)
        loaded = ProfileStore(self.path)
        self.assertEqual(require_profile(info, loaded)["id"], saved["id"])
        info.fingerprints["UnityPlayer.dll"] = "c" * 64
        self.assertEqual(select_profile(info, loaded)["status"], "experimental")
        with self.assertRaises(UnityProfileError):
            select_profile(info, loaded, saved["id"])

    def test_saved_unverified_client_still_requires_opt_in(self):
        saved = self.store.save_client(candidate(), "Not yet tested")
        self.assertEqual(select_profile(candidate(), self.store)["id"], saved["id"])
        with self.assertRaisesRegex(UnityProfileError, "untested"):
            require_profile(candidate(), self.store)

    def test_resaving_does_not_silently_erase_user_test_result(self):
        self.store.save_client(candidate(), "Tested", tested=True)
        self.store.save_client(candidate(), "Renamed")
        self.assertEqual(self.store.custom[0]["status"], "user-tested")
        self.assertEqual(len(self.store.custom), 1)

    def test_renamed_executable_is_not_an_exact_build_match(self):
        info = self.known_client()
        info.executable = str(Path(info.executable).with_name("Renamed.exe"))
        self.assertEqual(select_profile(info, self.store)["status"], "experimental")

    def test_bad_store_is_not_overwritten_and_builtin_still_available(self):
        self.path.write_text("{invalid JSON")
        broken = ProfileStore(self.path)
        self.assertTrue(broken.load_error)
        self.assertEqual(require_profile(self.known_client(), broken)["status"], "verified")
        with self.assertRaises(UnityProfileError):
            broken.save_client(candidate(), "Example")
        self.assertEqual(self.path.read_text(), "{invalid JSON")

    def test_unknown_backend_and_fake_verified_status_are_rejected(self):
        profile = self.store.save_client(candidate(), "Example")
        for field, value in (("backend", "load-arbitrary-dll"), ("status", "verified"), ("id", "client-" + "0" * 20)):
            with self.subTest(field=field):
                bad = deepcopy(profile)
                bad[field] = value
                self.path.write_text(json.dumps({"version": 1, "profiles": [bad]}))
                broken = ProfileStore(self.path)
                self.assertTrue(broken.load_error)
                self.assertFalse(broken.custom)

    def test_unknown_explicit_profile_does_not_silently_fall_back(self):
        with self.assertRaisesRegex(UnityProfileError, "missing"):
            select_profile(candidate(), self.store, "deleted-profile")

    def test_unapproved_trial_never_reaches_loader(self):
        with patch("src.unity_bridge.inspect_client", return_value=candidate()), \
             patch("src.unity_bridge._load_helper") as load:
            with self.assertRaisesRegex(UnityBridgeError, "untested"):
                UnityBridge(123, profile_store_path=self.path)
        load.assert_not_called()

    def test_old_resident_helper_requires_restart_before_v2_loading(self):
        with patch("src.unity_bridge.kernel.OpenProcess", return_value=1), \
             patch("src.unity_bridge.kernel.CloseHandle"), \
             patch("src.unity_bridge._modules", return_value=[(100, Path("C:/Old/itm_unity_bridge.dll"))]), \
             patch("src.unity_bridge.kernel.CreateRemoteThread") as load:
            with self.assertRaisesRegex(UnityBridgeError, "Restart"):
                _load_helper(123, Path("C:/New") / HELPER_NAME)
            load.assert_not_called()

    def test_pe_named_exports_use_name_pointer_table_not_function_table(self):
        data = bytearray(1024)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3c, 0x80)
        data[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HH", data, 0x84, 0x8664, 1)
        struct.pack_into("<H", data, 0x94, 0xf0)
        optional = 0x98
        struct.pack_into("<H", data, optional, 0x20b)
        struct.pack_into("<II", data, optional + 112, 0x1000, 40)
        struct.pack_into("<IIII", data, optional + 0xf0 + 8, 512, 0x1000, 512, 512)
        struct.pack_into("<I", data, 512 + 24, 2)
        struct.pack_into("<I", data, 512 + 28, 0x1050)  # function addresses (not names)
        struct.pack_into("<I", data, 512 + 32, 0x1060)
        struct.pack_into("<II", data, 512 + 0x60, 0x1080, 0x1090)
        data[640:644] = b"one\0"
        data[656:660] = b"two\0"
        path = Path(self.temp.name) / "test.dll"
        path.write_bytes(data)
        self.assertEqual(pe_info(path, read_exports=True), ("x64", {"one", "two"}))
        path.write_bytes(b"MZ")
        with self.assertRaises(UnityProfileError):
            pe_info(path, read_exports=True)


if __name__ == "__main__":
    unittest.main()
