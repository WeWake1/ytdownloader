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
import traceback

from kivy.app import App
from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

from core import (
    build_quality_options,
    choose_format_expr_for_height,
    download,
    ensure_writable_std_streams,
    fetch_info,
    list_available_resolutions,
    parse_quality_choice,
    resolve_ffmpeg,
)

# Do this before anything can write to stdout: on Android these are not always
# real file objects, and yt-dlp writing to them fails with
# "'str' object has no attribute 'write'".
ensure_writable_std_streams()

IS_ANDROID = platform == 'android'
PROMPT = 'Select quality'

BG        = (0.055, 0.063, 0.078, 1)   # page background
SURFACE   = (0.106, 0.118, 0.141, 1)   # inputs and secondary buttons
SURFACE_2 = (0.153, 0.169, 0.196, 1)   # pressed / track
ACCENT    = (0.898, 0.196, 0.180, 1)   # primary action
ACCENT_D  = (0.640, 0.140, 0.129, 1)   # primary pressed
TEXT      = (0.937, 0.945, 0.957, 1)
MUTED     = (0.604, 0.639, 0.686, 1)
OK_GREEN  = (0.302, 0.780, 0.451, 1)
ERR_RED   = (0.965, 0.451, 0.427, 1)


class RoundBox:
    """Mixin drawing a rounded background behind a widget."""

    def _init_bg(self, color, radius=12):
        self._bg_color_value = color
        with self.canvas.before:
            self._bg_color = Color(*color)
            self._bg_rect = RoundedRectangle(radius=[dp(radius)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def set_bg(self, color):
        self._bg_color.rgba = color


class FlatButton(Button, RoundBox):
    def __init__(self, base=SURFACE, pressed=SURFACE_2, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('color', TEXT)
        kwargs.setdefault('font_size', sp(17))
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(52))
        super().__init__(**kwargs)
        self._base, self._pressed = base, pressed
        self._init_bg(base)
        self.bind(state=self._on_state, disabled=self._on_state)

    def _on_state(self, *_):
        if self.disabled:
            self.set_bg((self._base[0], self._base[1], self._base[2], 0.45))
            self.color = (*MUTED[:3], 0.6)
        else:
            self.color = TEXT
            self.set_bg(self._pressed if self.state == 'down' else self._base)


class FlatSpinner(Spinner, RoundBox):
    def __init__(self, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('color', TEXT)
        kwargs.setdefault('font_size', sp(17))
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(52))
        super().__init__(**kwargs)
        self._init_bg(SURFACE)


class UrlInput(TextInput, RoundBox):
    def __init__(self, **kwargs):
        kwargs.setdefault('multiline', False)
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_active', '')
        kwargs.setdefault('background_color', (0, 0, 0, 0))
        kwargs.setdefault('foreground_color', TEXT)
        kwargs.setdefault('cursor_color', ACCENT)
        kwargs.setdefault('hint_text_color', MUTED)
        kwargs.setdefault('font_size', sp(16))
        kwargs.setdefault('padding', [dp(14), dp(15), dp(14), dp(14)])
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(52))
        super().__init__(**kwargs)
        self._init_bg(SURFACE)


class ProgressBarX(Widget):
    """Progress bar drawn by hand; Kivy's default does not theme well."""

    value = NumericProperty(0.0)   # 0..100

    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(8))
        super().__init__(**kwargs)
        with self.canvas:
            self._track_color = Color(*SURFACE_2)
            self._track = RoundedRectangle(radius=[dp(4)])
            self._fill_color = Color(*ACCENT)
            self._fill = RoundedRectangle(radius=[dp(4)])
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *_):
        self._track.pos, self._track.size = self.pos, self.size
        pct = max(0.0, min(100.0, float(self.value))) / 100.0
        self._fill.pos = self.pos
        self._fill.size = (self.width * pct, self.height)


class DownloaderLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=[dp(18), dp(24)],
                         spacing=dp(12), **kwargs)
        Window.clearcolor = BG

        self.ffmpeg_path = resolve_ffmpeg()

        title = Label(text='YouTube Downloader', font_size=sp(24), bold=True,
                      color=TEXT, size_hint_y=None, height=dp(34), halign='left')
        title.bind(size=lambda *_: setattr(title, 'text_size', title.size))
        self.add_widget(title)

        # Permanent ffmpeg self-test line. Kept separate from the status label
        # so a later download error cannot erase this diagnostic.
        ok, banner = self._ffmpeg_banner()
        self.ffmpeg_label = Label(text=banner, font_size=sp(12),
                                  color=OK_GREEN if ok else ERR_RED,
                                  size_hint_y=None, height=dp(18), halign='left')
        self.ffmpeg_label.bind(
            size=lambda *_: setattr(self.ffmpeg_label, 'text_size', self.ffmpeg_label.size))
        self.add_widget(self.ffmpeg_label)

        self.add_widget(Widget(size_hint_y=None, height=dp(6)))

        self.url_input = UrlInput(hint_text='Paste a YouTube link')
        self.add_widget(self.url_input)

        self.load_button = FlatButton(text='Load Qualities')
        self.load_button.bind(on_release=self.on_load_qualities)
        self.add_widget(self.load_button)

        self.quality_spinner = FlatSpinner(text=PROMPT, values=[])
        self.quality_spinner.disabled = True
        self.add_widget(self.quality_spinner)

        self.download_button = FlatButton(text='Download', base=ACCENT, pressed=ACCENT_D)
        self.download_button.disabled = True
        self.download_button.bind(on_release=self.on_download)
        self.add_widget(self.download_button)

        self.progress = ProgressBarX()
        self.add_widget(self.progress)

        self.status = Label(text='Paste a link to begin.', font_size=sp(14),
                            color=MUTED, halign='left', valign='top')
        self.status.bind(size=lambda *_: setattr(self.status, 'text_size', self.status.size))
        self.add_widget(self.status)

    def _ffmpeg_banner(self):
        """Self-test proving the bundled ffmpeg binary is present and executable.

        This is the riskiest part of the Android build (Android 10+ W^X blocks
        executing binaries outside nativeLibraryDir), so surface it up front
        rather than discovering it mid-download.
        """
        if not self.ffmpeg_path:
            return False, 'ffmpeg NOT found - merging and MP3 will fail'
        try:
            out = subprocess.run([self.ffmpeg_path, '-version'],
                                 capture_output=True, text=True, timeout=15)
            first = (out.stdout or out.stderr).splitlines()
            if out.returncode == 0 and first:
                return True, first[0][:64]
            return False, f'ffmpeg exited {out.returncode}'
        except Exception as e:
            return False, f'ffmpeg not executable: {type(e).__name__}: {e}'

    # --- UI updates from worker threads must be marshalled to the main thread ---

    @mainthread
    def set_status(self, text, color=None):
        self.status.text = text
        self.status.color = color or MUTED

    @mainthread
    def set_progress(self, value):
        self.progress.value = value

    @mainthread
    def set_options(self, options):
        self.quality_spinner.values = options
        self.quality_spinner.text = options[0] if options else PROMPT
        self.quality_spinner.disabled = not options
        self.download_button.disabled = not options

    @mainthread
    def set_busy(self, busy):
        self.load_button.disabled = busy
        self.download_button.disabled = busy or not self.quality_spinner.values

    # --- actions ---

    def on_load_qualities(self, *_):
        url = self.url_input.text.strip()
        if not url:
            self.set_status('Please paste a YouTube link first.', ERR_RED)
            return
        self.set_busy(True)
        self.set_status('Loading available qualities...')
        threading.Thread(target=self._load_worker, args=(url,), daemon=True).start()

    def _load_worker(self, url):
        try:
            info = fetch_info(url)
            heights = list_available_resolutions(info)
            self.set_options(build_quality_options(heights))
            title = (info.get('title') or 'video')[:60]
            self.set_status(f'Ready: {title}')
        except Exception as e:
            self.set_status(f'Could not read that link.\n{type(e).__name__}: {e}', ERR_RED)
        finally:
            self.set_busy(False)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            done = d.get('downloaded_bytes', 0)
            pct = (done / total * 100) if total else 0
            self.set_progress(pct)
            speed = d.get('_speed_str', '')
            eta = d.get('eta')
            tail = f' - ETA {eta}s' if eta else ''
            self.set_status(f'Downloading {pct:.0f}%  {speed}{tail}')
        elif d['status'] == 'finished':
            self.set_progress(100)
            self.set_status('Converting with ffmpeg...')

    def on_download(self, *_):
        url = self.url_input.text.strip()
        quality = self.quality_spinner.text
        if not url:
            self.set_status('Please paste a YouTube link first.', ERR_RED)
            return
        if not quality or quality == PROMPT or not self.quality_spinner.values:
            self.set_status('Tap "Load Qualities" and pick one first.', ERR_RED)
            return

        self.set_busy(True)
        self.set_progress(0)
        self.set_status('Starting download...')

        selected = parse_quality_choice(quality)
        fmt = choose_format_expr_for_height(selected)
        outtmpl = os.path.join(storage_dir(), '%(title)s.%(ext)s')
        threading.Thread(target=self._download_worker, args=(url, fmt, outtmpl),
                         daemon=True).start()

    def _download_worker(self, url, fmt, outtmpl):
        try:
            download(url, fmt, outtmpl, playlist=False,
                     progress_hook=self.progress_hook,
                     ffmpeg_location=self.ffmpeg_path)
            self._publish_new_files()
        except Exception as e:
            # The exception text is the only diagnostic available on device, so
            # show the type and the last traceback frame too.
            frame = ''
            tb = traceback.extract_tb(e.__traceback__)
            if tb:
                last = tb[-1]
                frame = f'\nat {os.path.basename(last.filename)}:{last.lineno}'
            self.set_status(f'Download failed.\n{type(e).__name__}: {e}{frame}', ERR_RED)
        finally:
            self.set_busy(False)

    def _publish_new_files(self):
        target = storage_dir()
        names = [n for n in os.listdir(target)] if os.path.isdir(target) else []
        if not names:
            self.set_status('Finished, but no file was produced.', ERR_RED)
            return
        newest = max((os.path.join(target, n) for n in names), key=os.path.getmtime)
        ok, where = publish_to_shared(newest)
        name = os.path.basename(newest)
        if ok:
            self.set_status(f'Saved to {where}\n{name}', OK_GREEN)
        else:
            self.set_status(f'Downloaded, but saving to Downloads failed.\n'
                            f'It is in app storage.\n{where}', ERR_RED)


def storage_dir() -> str:
    """Directory to download into. Private on Android, cwd on desktop."""
    if IS_ANDROID:
        from android.storage import app_storage_path
        path = os.path.join(app_storage_path(), 'downloads')
        os.makedirs(path, exist_ok=True)
        return path
    return os.getcwd()


def publish_to_shared(path):
    """Copy a finished download into shared Downloads so it is visible in Files.

    Returns (ok, description).
    """
    if not IS_ANDROID:
        return True, os.path.dirname(path)
    try:
        from androidstorage4kivy import SharedStorage
        SharedStorage().copy_to_shared(path)
        return True, 'Downloads'
    except Exception as e:
        # The file still exists in app storage, so this is not fatal.
        return False, f'{type(e).__name__}: {e}'


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
