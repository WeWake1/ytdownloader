"""Platform-independent download logic shared by the desktop and Android apps.

This module contains no UI code and makes no assumptions about the platform it
runs on. The desktop entry point (`ytdownloader.py`) and the Android entry point
(`main.py`) both build their interfaces on top of it.

The only platform-specific concern here is `resolve_ffmpeg()`, which finds the
ffmpeg binary in the very different places it lives on desktop vs Android.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from typing import List, Optional

try:
    from yt_dlp import YoutubeDL
except Exception:  # ImportError or other
    YoutubeDL = None

log = logging.getLogger(__name__)


class _NullStream:
    """Stand-in for a missing or unusable stdout/stderr."""

    def write(self, _data):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False


def ensure_writable_std_streams() -> None:
    """Guarantee sys.stdout/sys.stderr are writable file-like objects.

    On Android, p4a does not always leave these as real file objects, and
    anything that writes to them then fails with

        AttributeError: 'str' object has no attribute 'write'

    Only replaces a stream that is missing or has no write(), so a working
    console (desktop) or Kivy's Android log redirection is left alone.
    """
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, 'write'):
            setattr(sys, name, _NullStream())


class _YtdlpLogger:
    """Route yt-dlp's output through logging rather than stdout.

    yt-dlp only consults `logger` before touching its output files, so passing
    this keeps it away from sys.stdout entirely -- which is what breaks on
    Android.
    """

    def debug(self, msg):
        log.debug(msg)

    def info(self, msg):
        log.info(msg)

    def warning(self, msg):
        log.warning(msg)

    def error(self, msg):
        log.error(msg)


# On Android the ffmpeg CLI is shipped disguised as a shared library, because
# Android 10+ (W^X) refuses to execute binaries from the app data directory.
# python-for-android's ffmpeg recipe copies the compiled `ffmpeg` executable to
# this name so it lands in nativeLibraryDir, the one place exec() is allowed.
ANDROID_FFMPEG_SONAME = 'libffmpegbin.so'


def resolve_ffmpeg() -> Optional[str]:
    """Return a path to the ffmpeg binary, or None if it cannot be found.

    On Android, looks inside the app's native library directory. On desktop,
    falls back to a normal PATH lookup.

    Always returns the full path to the *file*, never its directory. yt-dlp
    accepts either, but when given a directory it scans for entries literally
    named `ffmpeg`/`ffprobe` -- which never matches `libffmpegbin.so`, leaving
    ffmpeg silently unavailable. Verified: full path works, directory does not.
    """
    try:
        from jnius import autoclass  # only present on Android
    except ImportError:
        return shutil.which('ffmpeg')

    try:
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        lib_dir = activity.getApplicationInfo().nativeLibraryDir
        candidate = os.path.join(lib_dir, ANDROID_FFMPEG_SONAME)
        return candidate if os.path.exists(candidate) else None
    except Exception:
        return None


def list_available_resolutions(info: dict) -> List[int]:
    """Return sorted list of available video heights (integers) in descending order."""
    formats = info.get('formats', []) if info else []
    heights = set()
    for f in formats:
        # Only consider formats that contain video
        vcodec = f.get('vcodec')
        height = f.get('height')
        if vcodec and vcodec != 'none' and isinstance(height, int):
            heights.add(height)
    return sorted(heights, reverse=True)


def choose_format_expr_for_height(height) -> str:
    """Return a yt-dlp format expression for the given height or special keys.

    height can be an int (e.g. 1080), or the strings 'best' or 'audio'.
    """
    if height == 'best':
        return 'bestvideo+bestaudio/best'
    if height == 'audio':
        return 'bestaudio'
    # numeric height
    try:
        h = int(height)
        # Prefer merged bestvideo (<=h) + bestaudio, fallback to best (<=h)
        # To fix audio issues, prefer more compatible formats: h264 + aac
        return f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]"
    except Exception:
        return 'best'


def fetch_info(url: str) -> dict:
    """Fetch video metadata without downloading. Raises on failure."""
    if YoutubeDL is None:
        raise RuntimeError('yt-dlp is not installed. Install with: pip install -r requirements.txt')
    ensure_writable_std_streams()
    opts = {'quiet': True, 'no_warnings': True, 'logger': _YtdlpLogger()}
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def build_quality_options(heights: List[int]) -> List[str]:
    """Build the user-facing quality menu from available heights.

    Shared by every front-end so the labels stay identical across platforms.
    Parse the result back with `parse_quality_choice`.
    """
    options = [f"{h}p" for h in heights]
    options.append('best (best available)')
    options.append('audio-only')
    return options


def parse_quality_choice(choice: str):
    """Turn a label from `build_quality_options` back into a height / key."""
    if choice.endswith('p'):
        try:
            return int(choice[:-1])
        except ValueError:
            return 'best'
    if choice == 'audio-only':
        return 'audio'
    return 'best'


def download(url: str, format_expr: str, outtmpl: str = '%(title)s.%(ext)s',
             playlist: bool = False, progress_hook=None,
             ffmpeg_location: Optional[str] = None) -> bool:
    """Download `url` using the given yt-dlp format expression.

    `ffmpeg_location` should be the path returned by `resolve_ffmpeg()`. When it
    is None, yt-dlp falls back to looking for ffmpeg on PATH.
    """
    if YoutubeDL is None:
        log.error('yt-dlp is not installed. Install with: pip install -r requirements.txt')
        return False

    ensure_writable_std_streams()

    ydl_opts = {
        'format': format_expr,
        'outtmpl': outtmpl,
        'noplaylist': not playlist,
        # Ask yt-dlp to merge into mp4 if possible (requires ffmpeg)
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook] if progress_hook else [],
        # Keep yt-dlp off sys.stdout; see _YtdlpLogger.
        'logger': _YtdlpLogger(),
    }

    if ffmpeg_location:
        ydl_opts['ffmpeg_location'] = ffmpeg_location

    # If audio-only is selected, convert to mp3
    if format_expr == 'bestaudio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        # Remove merge_output_format for audio only to avoid conflicts
        if 'merge_output_format' in ydl_opts:
            del ydl_opts['merge_output_format']

    try:
        with YoutubeDL(ydl_opts) as ydl:
            log.info('Starting download (format: %s)...', format_expr)
            ydl.download([url])
        return True
    except Exception as e:
        log.error('Download failed: %s', e)
        return False
