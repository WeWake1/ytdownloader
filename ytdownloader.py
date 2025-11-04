"""Simple interactive YouTube downloader using yt-dlp.

Usage:
  - Run without args: it will prompt for a YouTube URL and a quality choice.
  - Or pass the URL as the first argument: python ytdownloader.py <url>
  - Options: --output <folder>, --gui, --playlist

The script lists available resolutions and lets you choose one. It will
attempt to download best video+audio for the chosen resolution and merge
them into an MP4 when possible.
"""

from __future__ import annotations

import sys
import os
import argparse
import threading
from typing import List, Optional

try:
    from yt_dlp import YoutubeDL
except Exception:  # ImportError or other
    YoutubeDL = None

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import filedialog
    from tkinter import simpledialog, messagebox
except ImportError:
    tk = None
    ttk = None


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


def download(url: str, format_expr: str, outtmpl: str = '%(title)s.%(ext)s', playlist: bool = False, progress_hook=None) -> bool:
    if YoutubeDL is None:
        print('\nyt-dlp is not installed. Install dependencies with:')
        print('  pip install -r requirements.txt')
        return False

    ydl_opts = {
        'format': format_expr,
        'outtmpl': outtmpl,
        'noplaylist': not playlist,
        # Ask yt-dlp to merge into mp4 if possible (requires ffmpeg on PATH)
        'merge_output_format': 'mp4',
        # show progress on console
        'progress_hooks': [progress_hook] if progress_hook else [],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            print(f"\nStarting download (format: {format_expr})...")
            ydl.download([url])
        return True
    except Exception as e:
        print('Download failed:', e)
        return False


def get_user_input_gui() -> tuple[str, str, str]:
    """Get URL, quality, and output folder via tkinter GUI."""
    if tk is None or ttk is None:
        print("tkinter not available. Falling back to console input.")
        url, selected = get_user_input_console()
        return url, selected, '.'

    root = tk.Tk()
    root.title("YouTube Downloader")
    root.geometry("600x350")

    tk.Label(root, text="YouTube URL:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
    url_entry = tk.Entry(root, width=50)
    url_entry.grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Output Folder:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
    output_entry = tk.Entry(root, width=40)
    output_entry.insert(0, os.getcwd())  # Default to current dir
    output_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

    def browse_folder():
        folder = filedialog.askdirectory()
        if folder:
            output_entry.delete(0, tk.END)
            output_entry.insert(0, folder)

    browse_button = tk.Button(root, text="Browse", command=browse_folder)
    browse_button.grid(row=1, column=2, padx=10, pady=5)

    tk.Label(root, text="Quality:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
    quality_var = tk.StringVar()
    quality_combo = ttk.Combobox(root, textvariable=quality_var, state="readonly", width=47)
    quality_combo.grid(row=2, column=1, padx=10, pady=5)
    quality_combo['values'] = ["Enter URL and click 'Load Qualities'"]

    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
    progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=5, sticky='ew')

    status_label = tk.Label(root, text="")
    status_label.grid(row=4, column=0, columnspan=3, padx=10, pady=5)

    result = {'url': '', 'quality': '', 'output': ''}

    def load_qualities():
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL.")
            return

        if YoutubeDL is None:
            messagebox.showerror("Error", "yt-dlp not installed. Install with: pip install -r requirements.txt")
            return

        try:
            ydl = YoutubeDL({'quiet': True})
            info = ydl.extract_info(url, download=False)
            heights = list_available_resolutions(info)
            options = []
            if heights:
                options.extend([f"{h}p" for h in heights])
            options.append("best (best available)")
            options.append("audio-only")
            quality_combo['values'] = options
            quality_combo.current(0)
            status_label.config(text="Qualities loaded.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch video info: {e}")

    load_button = tk.Button(root, text="Load Qualities", command=load_qualities)
    load_button.grid(row=5, column=0, padx=10, pady=10)

    def progress_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
            else:
                percent = 0
            root.after(0, lambda: progress_var.set(percent))
            eta = d.get('eta', None)
            speed = d.get('_speed_str', 'N/A')
            eta_str = f" ETA {eta}s" if eta else ""
            status_text = f"Downloading: {percent:.1f}% at {speed}{eta_str}"
            root.after(0, lambda: status_label.config(text=status_text))
        elif d['status'] == 'finished':
            root.after(0, lambda: progress_var.set(100))
            root.after(0, lambda: status_label.config(text="Download completed."))
        elif d['status'] == 'error':
            root.after(0, lambda: status_label.config(text="Download error."))

    def download_thread(url, format_expr, outtmpl, playlist):
        try:
            ok = download(url, format_expr, outtmpl, playlist, progress_hook)
            if ok:
                root.after(0, lambda: status_label.config(text="Download finished."))
            else:
                root.after(0, lambda: status_label.config(text="Download failed."))
        except Exception as e:
            root.after(0, lambda: status_label.config(text=f"Download error: {e}"))
        finally:
            root.after(0, lambda: download_button.config(state='normal'))

    def on_download():
        url = url_entry.get().strip()
        quality = quality_var.get()
        output_dir = output_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL.")
            return
        if not quality or quality == "Enter URL and click 'Load Qualities'":
            messagebox.showerror("Error", "Please load qualities and select one.")
            return
        if not output_dir:
            output_dir = '.'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Parse quality
        if quality.endswith('p'):
            selected = int(quality[:-1])
        elif quality == "best (best available)":
            selected = 'best'
        elif quality == "audio-only":
            selected = 'audio'
        else:
            selected = quality

        format_expr = choose_format_expr_for_height(selected)
        outtmpl = os.path.join(output_dir, '%(title)s.%(ext)s')

        result['url'] = url
        result['quality'] = selected
        result['output'] = output_dir

        # Disable button and start download in thread
        download_button.config(state='disabled')
        status_label.config(text="Starting download...")
        progress_var.set(0)
        thread = threading.Thread(target=download_thread, args=(url, format_expr, outtmpl, False))  # playlist not handled in GUI yet
        thread.start()

    download_button = tk.Button(root, text="Download", command=on_download)
    download_button.grid(row=5, column=2, padx=10, pady=10)

    root.mainloop()
    root.destroy()
    return result['url'], result['quality'], result['output']


def get_user_input_console(url_arg: Optional[str] = None) -> tuple[str, str]:
    """Get URL and quality choice via console prompts."""
    if url_arg:
        url = url_arg
    else:
        url = input('Paste YouTube video URL: ').strip()

    if not url:
        print('No URL provided. Exiting.')
        return '', ''

    if YoutubeDL is None:
        print('\nyt-dlp package not found. Please install with:')
        print('  pip install -r requirements.txt')
        return '', ''

    # Extract information about the video without downloading
    ydl = YoutubeDL({'quiet': True})
    try:
        info = ydl.extract_info(url, download=False)
    except Exception as e:
        print('Failed to fetch video info:', e)
        return '', ''

    heights = list_available_resolutions(info)

    print('\nAvailable qualities:')
    options = []
    if heights:
        for i, h in enumerate(heights, start=1):
            print(f"{i}. {h}p")
            options.append(h)
    else:
        print('  (no discrete video heights detected)')

    # add best and audio-only as options
    print(f"{len(options) + 1}. best (best available)")
    options.append('best')
    print(f"{len(options) + 1}. audio-only")
    options.append('audio')

    choice = input(f"Choose quality [1-{len(options)}] (default 1): ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
    except Exception:
        idx = 0
    if idx < 0 or idx >= len(options):
        idx = 0

    selected = options[idx]
    return url, selected


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Download YouTube videos with quality selection.")
        parser.add_argument('url', nargs='?', help='YouTube URL to download')
        parser.add_argument('--output', '-o', default='.', help='Output folder for downloads (default: current directory)')
        parser.add_argument('--console', action='store_true', help='Use console input instead of GUI')
        parser.add_argument('--playlist', action='store_true', help='Download entire playlist if URL is a playlist')

        args = parser.parse_args()

        if args.console:
            url, selected = get_user_input_console(args.url)
            output_dir = args.output
        else:
            url, selected, output_dir = get_user_input_gui()

        if not url or not selected:
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        outtmpl = os.path.join(output_dir, '%(title)s.%(ext)s')

        format_expr = choose_format_expr_for_height(selected)

        print(f"\nSelected: {selected} -> using format expression: {format_expr}")
        ok = download(url, format_expr, outtmpl, args.playlist)
        if ok:
            print('\nDownload finished.')
        else:
            print('\nDownload did not complete.')
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

