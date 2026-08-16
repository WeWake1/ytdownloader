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
| `p4a-recipes/kivy/` | Local recipe override — see "Why kivy's recipe is patched" |

### Building the APK

Builds run on GitHub Actions (`.github/workflows/android.yml`). The APK is attached to the run as an artifact; a public Release is published only from `main`, so branch builds never publish an unverified APK.

Do **not** try to run buildozer directly on macOS; it targets Linux. Use CI, or Docker if you want local builds — and note the official image is `linux/amd64`, so on Apple Silicon it runs under emulation and the ffmpeg compile becomes impractically slow.

Measured build times: **916s** cold, **61s** warm from cache. The cold cost is ffmpeg compiling from source. Output is a 33 MB APK.

CI asserts that `lib/arm64-v8a/libffmpegbin.so` is present in the finished APK and fails the build if it is not, so the assumption the whole design rests on is re-proven on every build.

### Audio is saved as .m4a on Android, not .mp3

The bundled ffmpeg can mux but not encode. python-for-android's recipe enables only parsers, decoders, muxers and demuxers for mp4 — there is **no `--enable-encoder` line at all** — and MP3 additionally needs `libmp3lame`, which p4a never builds. So `FFmpegExtractAudio → mp3` has no encoder to call and fails.

YouTube already serves audio as AAC, so on Android the app requests `bestaudio[ext=m4a]` and saves the stream unchanged. No encoder is involved, nothing is re-encoded, and no quality is lost. `.m4a` plays natively on Android.

Video is unaffected: merging needs only the `mp4`/`mov` muxers, which are enabled, plus a stream copy. Desktop still produces MP3, since a normal ffmpeg has `libmp3lame`.

Restoring MP3 on Android would mean adding `ffpyplayer_codecs` to the requirements — which enables all encoders plus libx264, libvpx and libshine — at a large cost in build time and APK size, and yt-dlp asks for `libmp3lame` specifically, which even that does not provide.

### Known limitation: no JavaScript runtime

Recent yt-dlp warns that extraction without a JS runtime is deprecated and "some formats may be missing". There is no deno or equivalent inside the APK. Extraction currently works, but this may need revisiting if YouTube tightens it.

### Why kivy's recipe is patched

`p4a-recipes/kivy/` overrides python-for-android's kivy recipe to drop `requests` from its `python_depends`.

`requests` pulls in charset-normalizer, which from 3.5.0 publishes PEP 738 Android wheels. That trips a p4a bug: requirements are resolved with `pip --dry-run --only-binary=:all: --platform=android_24_arm64_v8a`, so pip picks an Android wheel, but the resolved set is then installed with plain `pip install --no-deps` and no `--platform`, so the host pip rejects the wheel it just chose:

```
charset_normalizer-3.5.1-cp314-cp314-android_24_arm64_v8a.whl
is not a supported wheel on this platform
```

Pinning does not help — kivy's `python_depends` are resolved in a different pip pass from the project's own requirements, so a pin in `buildozer.spec` never constrains them. The app uses neither `kivy.network.urlrequest` nor `kivy.garden`, the only parts of Kivy that need `requests`, so dropping it is safe. The override subclasses the upstream recipe and redirects `get_recipe_dir()` back to upstream so kivy's patches still resolve.

Remove the override once p4a passes `--platform` to its install step.

### Other things that bite

- `android.accept_sdk_license = True` is **required** for unattended builds. It defaults to `False`, and without it buildozer runs `sdkmanager` but never answers its interactive `(y/N)` prompt, so build-tools is never installed and the build fails with a misleading `Aidl not found`.
- Do not use `ArtemSBulgakov/buildozer-action`; it adds `ppa:openjdk-r/ppa` on top of a base image that is now `ubuntu:26.04`, which that PPA does not publish for, so the action cannot build. The official `kivy/buildozer` image already ships `openjdk-17-jdk`.

### How ffmpeg works on Android

Android 10+ refuses to execute binaries from the app's data directory (a W^X restriction). python-for-android's `ffmpeg` recipe works around this by compiling the ffmpeg CLI and installing it as `libffmpegbin.so` in the app's native library directory, which is the one place execution is still allowed. `core.resolve_ffmpeg()` locates it there and hands the path to yt-dlp via its `ffmpeg_location` option.

The app shows an ffmpeg self-test in its status line at startup, so a packaging problem is visible immediately rather than surfacing mid-download.

**Pass the full file path, not the directory.** This was verified by pointing yt-dlp at a real ffmpeg binary renamed to `libffmpegbin.so`, reproducing Android's layout (no `ffprobe` beside it):

| `ffmpeg_location` | Result |
| --- | --- |
| `.../libffmpegbin.so` (full path) | works — merging and MP3 both succeed |
| `.../` (its directory) | **fails silently** — yt-dlp scans for files named `ffmpeg`/`ffprobe` and finds neither |

Both a video+audio merge and a 192kbps MP3 conversion were confirmed working through the renamed binary, so the Android ffmpeg path is proven independently of any APK build.

### Keeping yt-dlp current

YouTube changes often and a pinned yt-dlp goes stale within months. The workflow runs weekly, bumps yt-dlp to the newest release, rebuilds, and publishes a new APK.

### Requirements note

yt-dlp needs **Python 3.10+**. macOS ships 3.9, so install a newer interpreter (`brew install python@3.12`) for the desktop app. On older Python, pip silently installs an outdated yt-dlp that YouTube rejects with "The page needs to be reloaded."

Notes on video files and GitHub:

- Do not commit downloaded videos to the repository. GitHub rejects files larger than 100 MB.
- To keep large files out of Git history, add `*.mp4` to `.gitignore` and keep downloads in a separate folder that is ignored by Git.
- If a large file is accidentally committed, you must rewrite history to remove it before pushing (see the 'Fix bad large commits' section below).

🖤🩶🖤🩶🖤