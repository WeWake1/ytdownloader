#!/usr/bin/env bash
# install_deps.sh - Installs ffmpeg (system) and python requirements
set -e

echo "Starting install_deps.sh"

install_ffmpeg_apt() {
  echo "Installing ffmpeg via apt... (requires sudo)"
  sudo apt-get update && sudo apt-get install -y ffmpeg
}

install_ffmpeg_dnf() {
  echo "Installing ffmpeg via dnf... (requires sudo)"
  sudo dnf install -y ffmpeg
}

install_ffmpeg_pacman() {
  echo "Installing ffmpeg via pacman... (requires sudo)"
  sudo pacman -S --noconfirm ffmpeg
}

install_ffmpeg_brew() {
  echo "Installing ffmpeg via Homebrew..."
  brew install ffmpeg
}

install_ffmpeg_zypper() {
  echo "Installing ffmpeg via zypper... (requires sudo)"
  sudo zypper install -y ffmpeg
}

if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is already installed: $(ffmpeg -version | head -n1)"
else
  echo "ffmpeg not found. Selecting package manager..."
  if command -v apt-get >/dev/null 2>&1; then
    install_ffmpeg_apt
  elif command -v dnf >/dev/null 2>&1; then
    install_ffmpeg_dnf
  elif command -v pacman >/dev/null 2>&1; then
    install_ffmpeg_pacman
  elif command -v brew >/dev/null 2>&1; then
    install_ffmpeg_brew
  elif command -v zypper >/dev/null 2>&1; then
    install_ffmpeg_zypper
  else
    echo "No known package manager found. Please install ffmpeg manually: https://ffmpeg.org/download.html"
    exit 1
  fi
fi

echo "Installing Python packages from requirements.txt"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Done. Verify by running: ffmpeg --version && yt-dlp --version"