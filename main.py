"""Kivy front-end for the YouTube downloader (Android entry point).

buildozer requires this file to be named `main.py`. All download logic lives in
`core.py`, shared with the desktop app.

On Android the flow is:
  1. Download into the app's private directory (always writable).
  2. Publish the finished file to shared Downloads via MediaStore, so it shows
     up in the Files app. Scoped storage forbids writing to /sdcard directly.
"""

from __future__ import annotations

import os
import subprocess
import threading

from kivy.app import App
from kivy.clock import mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from core import (
    build_quality_options,
    choose_format_expr_for_height,
    download,
    fetch_info,
    list_available_resolutions,
    parse_quality_choice,
    resolve_ffmpeg,
)

IS_ANDROID = platform == 'android'
PROMPT = "Enter URL and tap 'Load Qualities'"


def storage_dir() -> str:
    """Directory to download into. Private on Android, cwd on desktop."""
    if IS_ANDROID:
        from android.storage import app_storage_path
        path = os.path.join(app_storage_path(), 'downloads')
        os.makedirs(path, exist_ok=True)
        return path
    return os.getcwd()


def publish_to_shared(path: str) -> str:
    """Copy a finished download into shared Downloads so it's visible in Files.

    Returns a human-readable description of where the file ended up.
    """
    if not IS_ANDROID:
        return path
    try:
        from androidstorage4kivy import SharedStorage
        SharedStorage().copy_to_shared(path)
        return 'Downloads'
    except Exception as e:
        # The file still exists in app storage, so this is not fatal.
        return f'app storage ({e})'


class DownloaderLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=dp(12), spacing=dp(8), **kwargs)

        self.ffmpeg_path = resolve_ffmpeg()

        self.url_input = TextInput(
            hint_text='Paste YouTube URL',
            multiline=False,
            size_hint_y=None,
            height=dp(48),
        )
        self.add_widget(self.url_input)

        self.load_button = Button(text='Load Qualities', size_hint_y=None, height=dp(48))
        self.load_button.bind(on_release=self.on_load_qualities)
        self.add_widget(self.load_button)

        self.quality_spinner = Spinner(
            text=PROMPT,
            values=[],
            size_hint_y=None,
            height=dp(48),
        )
        self.add_widget(self.quality_spinner)

        self.download_button = Button(text='Download', size_hint_y=None, height=dp(48))
        self.download_button.bind(on_release=self.on_download)
        self.add_widget(self.download_button)

        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(24))
        self.add_widget(self.progress)

        self.status = Label(text=self._ffmpeg_banner(), halign='center', valign='top')
        self.status.bind(size=lambda *_: setattr(self.status, 'text_size', self.status.size))
        self.add_widget(self.status)

    def _ffmpeg_banner(self) -> str:
        """Self-test proving the bundled ffmpeg binary is present and executable.

        This is the single riskiest part of the Android build (Android 10+ W^X
        blocks executing binaries outside nativeLibraryDir), so surface it up
        front rather than discovering it mid-download.
        """
        if not self.ffmpeg_path:
            return 'ffmpeg NOT found — merging and MP3 will fail'
        try:
            out = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True, text=True, timeout=15,
            )
            first = (out.stdout or out.stderr).splitlines()
            if out.returncode == 0 and first:
                return f'Ready — {first[0][:60]}'
            return f'ffmpeg found but exited {out.returncode}'
        except Exception as e:
            return f'ffmpeg found but not executable: {e}'

    # --- UI updates from worker threads must be marshalled to the main thread ---

    @mainthread
    def set_status(self, text: str):
        self.status.text = text

    @mainthread
    def set_progress(self, value: float):
        self.progress.value = value

    @mainthread
    def set_options(self, options: list):
        self.quality_spinner.values = options
        self.quality_spinner.text = options[0] if options else PROMPT

    @mainthread
    def set_buttons_enabled(self, enabled: bool):
        self.load_button.disabled = not enabled
        self.download_button.disabled = not enabled

    # --- actions ---

    def on_load_qualities(self, *_):
        url = self.url_input.text.strip()
        if not url:
            self.set_status('Please enter a YouTube URL.')
            return
        self.set_buttons_enabled(False)
        self.set_status('Loading qualities...')
        threading.Thread(target=self._load_worker, args=(url,), daemon=True).start()

    def _load_worker(self, url: str):
        try:
            info = fetch_info(url)
            heights = list_available_resolutions(info)
            self.set_options(build_quality_options(heights))
            title = (info.get('title') or '')[:50]
            self.set_status(f'Loaded: {title}')
        except Exception as e:
            self.set_status(f'Failed to fetch video info: {e}')
        finally:
            self.set_buttons_enabled(True)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100) if total else 0
            self.set_progress(percent)
            eta = d.get('eta')
            speed = d.get('_speed_str', 'N/A')
            eta_str = f' ETA {eta}s' if eta else ''
            self.set_status(f'Downloading: {percent:.1f}% at {speed}{eta_str}')
        elif d['status'] == 'finished':
            self.set_progress(100)
            self.set_status('Processing (merging / converting)...')

    def on_download(self, *_):
        url = self.url_input.text.strip()
        quality = self.quality_spinner.text
        if not url:
            self.set_status('Please enter a YouTube URL.')
            return
        if not quality or quality == PROMPT or not self.quality_spinner.values:
            self.set_status('Please load qualities and select one.')
            return

        self.set_buttons_enabled(False)
        self.set_progress(0)
        self.set_status('Starting download...')

        selected = parse_quality_choice(quality)
        format_expr = choose_format_expr_for_height(selected)
        outtmpl = os.path.join(storage_dir(), '%(title)s.%(ext)s')
        threading.Thread(
            target=self._download_worker,
            args=(url, format_expr, outtmpl),
            daemon=True,
        ).start()

    def _download_worker(self, url: str, format_expr: str, outtmpl: str):
        try:
            ok = download(
                url, format_expr, outtmpl,
                playlist=False,
                progress_hook=self.progress_hook,
                ffmpeg_location=self.ffmpeg_path,
            )
            if not ok:
                self.set_status('Download failed.')
                return
            self._publish_new_files()
        except Exception as e:
            self.set_status(f'Download error: {e}')
        finally:
            self.set_buttons_enabled(True)

    def _publish_new_files(self):
        target = storage_dir()
        names = sorted(os.listdir(target)) if os.path.isdir(target) else []
        if not names:
            self.set_status('Download finished, but no file was produced.')
            return
        newest = max(
            (os.path.join(target, n) for n in names),
            key=os.path.getmtime,
        )
        where = publish_to_shared(newest)
        self.set_status(f'Saved {os.path.basename(newest)} to {where}')


class YTDownloaderApp(App):
    title = 'YouTube Downloader'

    def build(self):
        if IS_ANDROID:
            self._request_permissions()
        return DownloaderLayout()

    def _request_permissions(self):
        """Storage permissions are only meaningful before Android 13.

        From API 33 onward, publishing to Downloads via MediaStore needs no
        permission at all, so a denial here is not fatal. INTERNET is granted at
        install time and is not a runtime permission, so it is not requested.
        """
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])
        except Exception:
            pass


if __name__ == '__main__':
    YTDownloaderApp().run()
