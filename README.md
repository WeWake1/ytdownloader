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

Notes on video files and GitHub:

- Do not commit downloaded videos to the repository. GitHub rejects files larger than 100 MB.
- To keep large files out of Git history, add `*.mp4` to `.gitignore` and keep downloads in a separate folder that is ignored by Git.
- If a large file is accidentally committed, you must rewrite history to remove it before pushing (see the 'Fix bad large commits' section below).
