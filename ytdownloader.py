"""Simple interactive YouTube downloader using yt-dlp (desktop entry point).

Usage:
  - Run without args: opens the GUI.
  - Or pass the URL as the first argument: python ytdownloader.py <url>
  - Options: --output <folder>, --console, --playlist

The download logic lives in `core.py`, which is shared with the Android app.
This file is only the desktop (tkinter / console) interface.
"""

from __future__ import annotations

import sys
import os
import argparse
import threading
from typing import Optional

from core import (
    YoutubeDL,
    build_quality_options,
    choose_format_expr_for_height,
    download,
    fetch_info,
    list_available_resolutions,
    parse_quality_choice,
    resolve_ffmpeg,
)

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import filedialog
    from tkinter import simpledialog, messagebox
except ImportError:
    tk = None
    ttk = None


def get_user_input_gui() -> tuple[str, str, str]:
    """Get URL, quality, and output folder via tkinter GUI."""
    if tk is None or ttk is None:
        print("tkinter not available. Falling back to console input.")
        url, selected = get_user_input_console()
        return url, selected, '.'

    ffmpeg_path = resolve_ffmpeg()

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
            info = fetch_info(url)
            heights = list_available_resolutions(info)
            quality_combo['values'] = build_quality_options(heights)
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
            ok = download(url, format_expr, outtmpl, playlist, progress_hook,
                          ffmpeg_location=ffmpeg_path)
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

        selected = parse_quality_choice(quality)
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

    try:
        info = fetch_info(url)
    except Exception as e:
        print('Failed to fetch video info:', e)
        return '', ''

    heights = list_available_resolutions(info)
    if not heights:
        print('\n  (no discrete video heights detected)')

    labels = build_quality_options(heights)
    print('\nAvailable qualities:')
    for i, label in enumerate(labels, start=1):
        print(f"{i}. {label}")

    choice = input(f"Choose quality [1-{len(labels)}] (default 1): ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
    except Exception:
        idx = 0
    if idx < 0 or idx >= len(labels):
        idx = 0

    return url, parse_quality_choice(labels[idx])


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Download YouTube videos with quality selection.")
        parser.add_argument('url', nargs='?', help='YouTube URL to download')
        parser.add_argument('--output', '-o', default='.', help='Output folder for downloads (default: current directory)')
        parser.add_argument('--console', action='store_true', help='Use console input instead of GUI')
        parser.add_argument('--playlist', action='store_true', help='Download entire playlist if URL is a playlist')

        args = parser.parse_args()

        # check ffmpeg is available
        ffmpeg_path = resolve_ffmpeg()
        if ffmpeg_path is None:
            print('\nERROR: ffmpeg is not found on your PATH. This tool requires the ffmpeg binary to merge audio + video.')
            print('Run `bash install_deps.sh` (macOS/Linux) or `install_deps.ps1` from PowerShell (Windows) to install the required dependencies.')
            return

        if not args.console:
            # The GUI performs the download itself in a worker thread, so there
            # is nothing left to do once its window closes.
            get_user_input_gui()
            return

        url, selected = get_user_input_console(args.url)
        output_dir = args.output

        if not url or not selected:
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        outtmpl = os.path.join(output_dir, '%(title)s.%(ext)s')

        format_expr = choose_format_expr_for_height(selected)

        print(f"\nSelected: {selected} -> using format expression: {format_expr}")
        ok = download(url, format_expr, outtmpl, args.playlist, ffmpeg_location=ffmpeg_path)
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
