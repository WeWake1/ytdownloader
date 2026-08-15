[app]

title = YouTube Downloader
package.name = ytdownloader
package.domain = org.wewake

source.dir = .
source.include_exts = py,kv,png,jpg,json,ini
# Keep the desktop-only files out of the APK. ytdownloader.py imports tkinter,
# which does not exist on Android; it is never imported by main.py, but there is
# no reason to ship it.
source.exclude_patterns = ytdownloader.py,install_deps.*,README.md,.github/*,p4a-recipes/*

version = 0.1

# `ffmpeg` is the important one: python-for-android's recipe compiles the real
# ffmpeg CLI and installs it as libffmpegbin.so inside nativeLibraryDir, which
# is the only place Android 10+ still permits executing a binary from.
#
# Deliberately minimal: yt-dlp declares no mandatory dependencies (everything in
# its metadata sits behind an `extra ==` marker) and uses stdlib urllib by
# default. `requests` was pulling charset-normalizer transitively, which failed
# to cross-compile, so it is omitted rather than pinned around. certifi is kept
# because yt-dlp uses it for CA certificates when present.
requirements = python3,kivy,openssl,certifi,yt-dlp==2026.7.4,ffmpeg,androidstorage4kivy,pyjnius

orientation = portrait
fullscreen = 0

# WRITE/READ_EXTERNAL_STORAGE only matter on Android 12 and below; from API 33
# publishing to Downloads through MediaStore needs no permission at all.
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 34
android.minapi = 24
android.ndk_api = 24

# Required for unattended builds. This defaults to False, and without it
# buildozer runs sdkmanager but never answers its interactive (y/N) license
# prompt, so build-tools is never installed and the build dies with the
# misleading "Aidl not found" -- aidl lives inside build-tools.
# Setting this accepts Google's Android SDK licence terms.
android.accept_sdk_license = True

# arm64-v8a only. Building every ABI multiplies the (already slow) ffmpeg
# compile; every phone from roughly 2017 onward is arm64.
android.archs = arm64-v8a

android.allow_backup = 1
android.release_artifact = apk
android.debug_artifact = apk

# Local recipe overrides. See p4a-recipes/kivy/__init__.py for why the
# kivy recipe's python_depends are patched.
p4a.local_recipes = ./p4a-recipes

[buildozer]

log_level = 2
warn_on_root = 1
