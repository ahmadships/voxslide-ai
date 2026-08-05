"""GitHub Releases auto-update engine for VoxSlide AI.

Checks the latest GitHub Release, compares semver against the installed
version, downloads the installer asset with progress + integrity checks,
and launches it.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from version import __version__

# Optional dependency — listed in requirements.txt
try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


ProgressCallback = Callable[[int, int], None]  # received_bytes, total_bytes


class UpdateError(Exception):
    """Base class for updater failures the UI can display."""


class NetworkUnavailableError(UpdateError):
    """No internet / DNS / connection failure."""


class DownloadError(UpdateError):
    """Download failed or was incomplete."""


class CorruptDownloadError(UpdateError):
    """Downloaded file failed size or checksum verification."""


class UpdateCancelled(UpdateError):
    """User cancelled an in-progress download."""


@dataclass(frozen=True)
class UpdateInfo:
    """Metadata for an available update."""

    version: str
    tag_name: str
    release_notes: str
    download_url: str
    asset_name: str
    asset_size: int
    sha256: Optional[str] = None
    html_url: str = ""


_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<pre>.*)?$",
    re.IGNORECASE,
)


def parse_version(value: str) -> tuple:
    """Parse a version / tag string into a comparable tuple.

    Examples: '1.2.3', 'v1.2.3', '1.2.3-beta' → (1, 2, 3, pre)
    Pre-release suffixes sort *before* the stable release.
    """
    cleaned = (value or "").strip().lstrip("vV")
    match = _VERSION_RE.match(cleaned)
    if not match:
        # Fallback: treat unparsable tags as 0.0.0 so they never force an update
        return (0, 0, 0, "zzz")
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    pre = (match.group("pre") or "").lstrip("-.+")
    # Empty pre = stable (sorts after any pre-release of same x.y.z)
    return (major, minor, patch, pre or "~~~~")


def is_newer(remote: str, local: str) -> bool:
    """Return True if remote version is strictly newer than local."""
    return parse_version(remote) > parse_version(local)


def current_version() -> str:
    return __version__


def _github_api_url(owner: str, repo: str) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"


def _extract_sha256(asset: dict, release_body: str) -> Optional[str]:
    """Prefer GitHub asset digest; fall back to a sha256 line in release notes."""
    digest = asset.get("digest") or ""
    if isinstance(digest, str) and digest.lower().startswith("sha256:"):
        return digest.split(":", 1)[1].strip().lower()

    name = asset.get("name") or ""
    if release_body and name:
        # Look for:  <hex64>  VoxSlideAI_Setup.exe
        pattern = re.compile(
            rf"(?P<hash>[a-fA-F0-9]{{64}})\s+\*?{re.escape(name)}\b"
        )
        m = pattern.search(release_body)
        if m:
            return m.group("hash").lower()
    return None


def _pick_asset(assets: list, preferred_names: list[str]) -> Optional[dict]:
    """Choose the installer asset from a release."""
    if not assets:
        return None

    names_lower = [n.lower() for n in preferred_names]

    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name in names_lower:
            return asset

    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe") and "setup" in name:
            return asset

    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe"):
            return asset

    return None


def check_for_update(
    owner: str,
    repo: str,
    *,
    local_version: Optional[str] = None,
    preferred_assets: Optional[list[str]] = None,
    timeout: float = 12.0,
) -> Optional[UpdateInfo]:
    """Query GitHub Releases for a newer version.

    Returns UpdateInfo if an update is available, otherwise None.
    Raises NetworkUnavailableError / UpdateError on hard failures that
    should be surfaced (or silently ignored by the caller).
    """
    local = local_version or current_version()
    preferred = preferred_assets or [
        "VoxSlideAI_Setup.exe",
        "VoxSlide AI Setup.exe",
    ]
    url = _github_api_url(owner, repo)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"VoxSlideAI-Updater/{local}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        if requests is not None:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                return None  # no releases yet
            if resp.status_code >= 400:
                raise UpdateError(f"GitHub API error HTTP {resp.status_code}")
            data = resp.json()
        else:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                import json

                data = json.loads(resp.read().decode("utf-8"))
    except UpdateError:
        raise
    except Exception as exc:
        raise NetworkUnavailableError(str(exc)) from exc

    tag = str(data.get("tag_name") or "")
    remote_version = tag.lstrip("vV") or str(data.get("name") or "")
    if not remote_version or not is_newer(remote_version, local):
        return None

    body = str(data.get("body") or "").strip() or "Bug fixes and improvements."
    asset = _pick_asset(data.get("assets") or [], preferred)
    if not asset or not asset.get("browser_download_url"):
        raise UpdateError(
            "A newer release exists, but no installer (.exe) asset was found."
        )

    return UpdateInfo(
        version=remote_version,
        tag_name=tag or f"v{remote_version}",
        release_notes=body,
        download_url=str(asset["browser_download_url"]),
        asset_name=str(asset.get("name") or "VoxSlideAI_Setup.exe"),
        asset_size=int(asset.get("size") or 0),
        sha256=_extract_sha256(asset, body),
        html_url=str(data.get("html_url") or ""),
    )


def download_update(
    info: UpdateInfo,
    *,
    dest_dir: Optional[Path] = None,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event: Optional[threading.Event] = None,
    timeout: float = 60.0,
    chunk_size: int = 256 * 1024,
) -> Path:
    """Download the update installer to a temp folder and verify integrity.

    Raises UpdateCancelled, DownloadError, or CorruptDownloadError.
    """
    cancel_event = cancel_event or threading.Event()
    dest_dir = dest_dir or Path(tempfile.gettempdir()) / "voxslide_updates"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / info.asset_name

    # Remove any previous partial download
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass

    partial = dest.with_suffix(dest.suffix + ".partial")
    if partial.exists():
        try:
            partial.unlink()
        except OSError:
            pass

    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": f"VoxSlideAI-Updater/{current_version()}",
    }

    hasher = hashlib.sha256()
    received = 0
    expected = info.asset_size

    try:
        if requests is not None:
            with requests.get(
                info.download_url,
                headers=headers,
                stream=True,
                timeout=timeout,
                allow_redirects=True,
            ) as resp:
                if resp.status_code >= 400:
                    raise DownloadError(f"Download failed (HTTP {resp.status_code})")
                # Prefer server Content-Length when GitHub omits asset size
                cl = resp.headers.get("Content-Length")
                if cl and expected <= 0:
                    expected = int(cl)
                with open(partial, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if cancel_event.is_set():
                            raise UpdateCancelled("Download cancelled")
                        if not chunk:
                            continue
                        fh.write(chunk)
                        hasher.update(chunk)
                        received += len(chunk)
                        if progress_callback:
                            progress_callback(received, expected)
        else:
            req = Request(info.download_url, headers=headers)
            with urlopen(req, timeout=timeout) as resp, open(partial, "wb") as fh:
                cl = resp.headers.get("Content-Length")
                if cl and expected <= 0:
                    expected = int(cl)
                while True:
                    if cancel_event.is_set():
                        raise UpdateCancelled("Download cancelled")
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    hasher.update(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, expected)
    except UpdateCancelled:
        _safe_unlink(partial)
        raise
    except UpdateError:
        _safe_unlink(partial)
        raise
    except Exception as exc:
        _safe_unlink(partial)
        raise DownloadError(str(exc)) from exc

    if expected > 0 and received != expected:
        _safe_unlink(partial)
        raise CorruptDownloadError(
            f"Incomplete download ({received} of {expected} bytes)."
        )

    if info.sha256:
        actual = hasher.hexdigest().lower()
        if actual != info.sha256.lower():
            _safe_unlink(partial)
            raise CorruptDownloadError(
                "Checksum mismatch — the download may be corrupt. Please try again."
            )

    if received < 1024:
        _safe_unlink(partial)
        raise CorruptDownloadError("Downloaded file is too small to be valid.")

    partial.replace(dest)
    return dest


def launch_installer(installer_path: Path) -> None:
    """Start the installer in a detached process so this app can exit."""
    import os
    import subprocess
    import sys

    path = Path(installer_path).resolve()
    if not path.is_file():
        raise DownloadError(f"Installer not found: {path}")

    if sys.platform == "win32":
        # Detach so the installer survives after we quit
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        subprocess.Popen(
            [str(path)],
            cwd=str(path.parent),
            close_fds=True,
            creationflags=creationflags,
            shell=False,
        )
    else:
        subprocess.Popen([str(path)], cwd=str(path.parent), start_new_session=True)

    # Give the OS a moment to spawn before the parent exits
    try:
        os.sched_yield()
    except Exception:
        pass


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
