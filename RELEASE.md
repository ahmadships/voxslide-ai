# Publishing Releases for VoxSlide AI

VoxSlide AI checks **GitHub Releases** on every startup. When a newer
version is published, users see an update dialog, download the installer,
and run it automatically.

---

## One-time setup

1. Create a **public** GitHub repository (private repos need a token; keep it public for simple updates).
2. Open `config.py` and set:

```python
GITHUB_OWNER = "your-github-username"   # e.g. "mohammadahmad"
GITHUB_REPO = "voxslide-app"            # your repo name
UPDATE_ASSET_NAME = "VoxSlideAI_Setup.exe"
```

3. Rebuild the app after changing those values so installed users can find your releases.
4. Push this project to that repository.

---

## Version numbers (single source of truth)

| File | What to change |
|------|----------------|
| `version.py` → `__version__` | **Primary** — used by the running app |
| `installer.iss` → `#define MyAppVersion` | Must match `version.py` |

Example bump to `1.1.0`:

```python
# version.py
__version__ = "1.1.0"
```

```iss
; installer.iss
#define MyAppVersion "1.1.0"
```

---

## Publish a new version (checklist)

### 1. Bump the version

- Edit `version.py`
- Edit `installer.iss` (`MyAppVersion`)

### 2. Build the executable

From the project root:

```bat
python -m PyInstaller build.spec --clean --noconfirm
```

Output: `dist\VoxSlide AI.exe`

### 3. Build the installer

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Output: `installer_output\VoxSlideAI_Setup.exe`

**Important:** The uploaded asset name must stay `VoxSlideAI_Setup.exe`
(or match `Config.UPDATE_ASSET_NAME`).

### 4. Create a GitHub Release

1. Open your repo on GitHub → **Releases** → **Draft a new release**
2. **Tag:** `v1.1.0` (must match the new version; the `v` prefix is fine)
3. **Title:** `VoxSlide AI 1.1.0`
4. **Description:** write clear release notes (shown in the in-app dialog)
5. **Attach** `installer_output\VoxSlideAI_Setup.exe`
6. Publish the release (not a pre-release, unless you only want testers)

#### Optional: SHA-256 checksum in release notes

For stronger integrity checks, append:

```text
## Checksums
<a64-char-sha256-hex>  VoxSlideAI_Setup.exe
```

Generate on Windows PowerShell:

```powershell
Get-FileHash .\installer_output\VoxSlideAI_Setup.exe -Algorithm SHA256
```

GitHub may also expose an asset `digest` field; the updater uses that when present.

### 5. Users receive the update

On next launch:

1. App calls `GET /repos/{owner}/{repo}/releases/latest`
2. Compares release tag to `version.py` / `Config.VERSION`
3. If newer → shows dialog with notes
4. User clicks **Update now** → downloads installer → app exits → installer runs

If offline or the check fails, the app starts normally (no blocking).

---

## Testing updates locally

1. Install an older build (e.g. tag the installed app as `1.0.0`).
2. Publish a GitHub Release `v1.0.1` with a new installer.
3. Launch the old app — the update dialog should appear.

Skip the check while developing:

```bat
set VOXSLIDE_SKIP_UPDATE=1
python main.py
```

Or set `Config.SKIP_UPDATE_CHECK = True` temporarily.

---

## Failure modes (handled)

| Situation | Behavior |
|-----------|----------|
| No internet | Silent skip; app starts normally |
| No releases yet / 404 | Silent skip |
| User clicks **Later** | Dialog closes; app keeps running |
| User cancels download | Partial file deleted; can retry |
| Download incomplete / wrong size | Error message; retry |
| Checksum mismatch | Treated as corrupt; retry |
| `GITHUB_OWNER` still a placeholder | Check skipped until configured |

---

## Files involved

| File | Role |
|------|------|
| `version.py` | App version string |
| `config.py` | GitHub owner/repo + asset name |
| `updater.py` | API check, download, verify, launch installer |
| `update_dialog.py` | UI dialog + progress bar |
| `ui_components.py` | Runs check shortly after startup |
| `installer.iss` | Builds `VoxSlideAI_Setup.exe` |
| `RELEASE.md` | This guide |
