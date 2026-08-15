[app]

title = YouTube Downloader
package.name = ytdownloader
package.domain = org.wewake

source.dir = .
source.include_exts = py,kv,png,jpg,json,ini
# Keep the desktop-only files out of the APK. ytdownloader.py imports tkinter,
# which does not exist on Android; it is never imported by main.py, but there is
# no reason to ship it.
source.exclude_patterns = ytdownloader.py,install_deps.*,README.md,.github/*

version = 0.1

# `ffmpeg` is the important one: python-for-android's recipe compiles the real
# ffmpeg CLI and installs it as libffmpegbin.so inside nativeLibraryDir, which
# is the only place Android 10+ still permits executing a binary from.
# charset-normalizer is pinned because newer releases fail to cross-compile.
requirements = python3,kivy,openssl,certifi,requests,charset-normalizer==3.4.5,yt-dlp==2026.7.4,ffmpeg,androidstorage4kivy,pyjnius

orientation = portrait
fullscreen = 0

# WRITE/READ_EXTERNAL_STORAGE only matter on Android 12 and below; from API 33
# publishing to Downloads through MediaStore needs no permission at all.
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 34
android.minapi = 24
android.ndk_api = 24

# arm64-v8a only. Building every ABI multiplies the (already slow) ffmpeg
# compile; every phone from roughly 2017 onward is arm64.
android.archs = arm64-v8a

android.allow_backup = 1
android.release_artifact = apk
android.debug_artifact = apk

[buildozer]

log_level = 2
warn_on_root = 1
