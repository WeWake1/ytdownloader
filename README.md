# YouTube Downloader (yt-dlp wrapper)

A small interactive script that prompts for a YouTube URL and a quality, then downloads the video using yt-dlp.

Requirements

- Python 3.8+
- yt-dlp
- ffmpeg (REQUIRED) — system binary is required to merge video+audio; not a pip package
- tkinter (optional, for GUI mode)

Note about ffmpeg (REQUIRED):

- yt-dlp requires an external ffmpeg binary to merge audio and video streams and to convert formats. This binary must be installed system-wide and available on your PATH. The script will not work without the `ffmpeg` binary.
- On Windows it's easiest using Chocolatey: `choco install ffmpeg` (requires administrator). Or download a static build: https://www.gyan.dev/ffmpeg/builds/ and add it to PATH.
- If you prefer a Python wrapper you can install `ffmpeg-python` (adds convenience helpers), but the system `ffmpeg` binary remains required.

Install scripts

To help new users, the repository provides OS-aware scripts that attempt to install platform packages needed to run the script and will also install Python packages from `requirements.txt`:

- `install_deps.sh` — macOS / Linux (checks available package manager and installs `ffmpeg`; will also install Python requirements via pip)
- `install_deps.ps1` — Windows PowerShell script (tries `winget` then `choco`; falls back to manual download + unzip if neither is available). Run PowerShell as Administrator to use package managers.

Usage examples:

```powershell
# Windows PowerShell (Administrator):
.\install_deps.ps1
```

```bash
# macOS or Linux
bash install_deps.sh
```

After running the install script, confirm `ffmpeg --version` prints a version and then run the downloader.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Usage

- Run with GUI (default):

```powershell
python ytdownloader.py
```

- Pass URL on command line (will still use GUI for quality selection):

```powershell
python ytdownloader.py "https://www.youtube.com/watch?v=..."
```

- Specify output folder:

```powershell
python ytdownloader.py --output "C:\Downloads" "https://www.youtube.com/watch?v=..."
```

- Use console mode instead of GUI:

```powershell
python ytdownloader.py --console
```

- Download playlist:

```powershell
python ytdownloader.py --playlist "https://www.youtube.com/playlist?list=..."
```

The GUI includes fields for URL, output folder, a dropdown for quality (loaded after entering URL), a progress bar, and status updates during download.

## Android app

The project also builds a standalone Android APK — the phone downloads on its own, with ffmpeg bundled inside the app, so there is no setup for the user.

Layout:

| File | Role |
| --- | --- |
| `core.py` | Download logic, shared by every platform. No UI. |
| `ytdownloader.py` | Desktop front-end (tkinter GUI + console) |
| `main.py` | Android front-end (Kivy). buildozer requires this filename. |
| `buildozer.spec` | Android packaging config |

### Building the APK

Builds run on GitHub Actions (`.github/workflows/android.yml`) — push to `main`, or trigger the workflow manually. The APK is attached to the run as an artifact and published as a Release.

Do **not** try to run buildozer directly on macOS; it targets Linux. Use CI, or Docker if you want local builds.

The first build takes roughly 30–60 minutes because ffmpeg is compiled from source. Later builds are cached and much faster.

### How ffmpeg works on Android

Android 10+ refuses to execute binaries from the app's data directory (a W^X restriction). python-for-android's `ffmpeg` recipe works around this by compiling the ffmpeg CLI and installing it as `libffmpegbin.so` in the app's native library directory, which is the one place execution is still allowed. `core.resolve_ffmpeg()` locates it there and hands the path to yt-dlp via its `ffmpeg_location` option.

The app shows an ffmpeg self-test in its status line at startup, so a packaging problem is visible immediately rather than surfacing mid-download.

### Keeping yt-dlp current

YouTube changes often and a pinned yt-dlp goes stale within months. The workflow runs weekly, bumps yt-dlp to the newest release, rebuilds, and publishes a new APK.

### Requirements note

yt-dlp needs **Python 3.10+**. macOS ships 3.9, so install a newer interpreter (`brew install python@3.12`) for the desktop app. On older Python, pip silently installs an outdated yt-dlp that YouTube rejects with "The page needs to be reloaded."

Notes on video files and GitHub:

- Do not commit downloaded videos to the repository. GitHub rejects files larger than 100 MB.
- To keep large files out of Git history, add `*.mp4` to `.gitignore` and keep downloads in a separate folder that is ignored by Git.
- If a large file is accidentally committed, you must rewrite history to remove it before pushing (see the 'Fix bad large commits' section below).

🖤🩶🖤🩶🖤