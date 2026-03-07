"""
GitHub release update checker.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass

from src.app_info import APP_VERSION, GITHUB_REPO, GITHUB_RELEASES_URL


@dataclass
class UpdateInfo:
    update_available: bool
    current_version: str
    latest_version: str
    release_url: str
    release_name: str
    asset_name: str = ""
    asset_download_url: str = ""
    error: str = ""
    no_release: bool = False


def _normalize_version(value: str) -> str:
    raw = str(value or "").strip()
    while raw.lower().startswith("v"):
        raw = raw[1:]
    return raw.strip()


def _version_key(value: str) -> tuple:
    normalized = _normalize_version(value)
    if not normalized:
        return (0,)
    parts = []
    for piece in normalized.replace("-", ".").split("."):
        if piece.isdigit():
            parts.append((0, int(piece)))
        else:
            parts.append((1, piece.casefold()))
    return tuple(parts)


def is_newer_version(latest_version: str, current_version: str) -> bool:
    return _version_key(latest_version) > _version_key(current_version)


def check_github_update(
    current_version: str = APP_VERSION,
    github_repo: str = GITHUB_REPO,
) -> UpdateInfo:
    """Check latest GitHub release tag for update availability."""
    api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ITM-AutoClicker-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if int(exc.code) == 404:
            return UpdateInfo(
                update_available=False,
                current_version=_normalize_version(current_version),
                latest_version="",
                release_url=GITHUB_RELEASES_URL,
                release_name="",
                asset_name="",
                asset_download_url="",
                error="",
                no_release=True,
            )
        return UpdateInfo(
            update_available=False,
            current_version=_normalize_version(current_version),
            latest_version="",
            release_url=GITHUB_RELEASES_URL,
            release_name="",
            asset_name="",
            asset_download_url="",
            error=f"HTTP {exc.code}",
            no_release=False,
        )
    except Exception as exc:
        return UpdateInfo(
            update_available=False,
            current_version=_normalize_version(current_version),
            latest_version="",
            release_url=GITHUB_RELEASES_URL,
            release_name="",
            asset_name="",
            asset_download_url="",
            error=str(exc),
            no_release=False,
        )

    latest_tag = str(payload.get("tag_name") or payload.get("name") or "").strip()
    latest_version = _normalize_version(latest_tag)
    release_url = str(payload.get("html_url") or GITHUB_RELEASES_URL)
    release_name = str(payload.get("name") or latest_tag or latest_version)
    asset_name = ""
    asset_download_url = ""
    for asset in payload.get("assets", []) or []:
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if name.lower().endswith(".exe") and url:
            asset_name = name
            asset_download_url = url
            break

    return UpdateInfo(
        update_available=is_newer_version(latest_version, current_version),
        current_version=_normalize_version(current_version),
        latest_version=latest_version,
        release_url=release_url,
        release_name=release_name,
        asset_name=asset_name,
        asset_download_url=asset_download_url,
        error="",
        no_release=False,
    )
