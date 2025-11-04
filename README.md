# YouTube Downloader (yt-dlp wrapper)

A small interactive script that prompts for a YouTube URL and a quality, then downloads the video using yt-dlp.

Requirements

- Python 3.8+
- yt-dlp
- ffmpeg (optional, required to merge video/audio into mp4)
- tkinter (optional, for GUI mode)

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
