# install_deps.ps1 - Windows PowerShell script to install ffmpeg and Python deps
Param(
    [switch]$Force
)

function CommandExists([string]$name) {
    return (Get-Command $name -ErrorAction SilentlyContinue) -ne $null
}

Write-Host "Starting install_deps.ps1..."

if (CommandExists "ffmpeg") {
    Write-Host "ffmpeg already installed. Version: $(ffmpeg -version | Select-String -Pattern 'ffmpeg')"
} else {
    if (CommandExists "winget") {
        Write-Host "Installing ffmpeg via winget..."
        winget install -e --id Gyan.FFmpeg || winget install -e --id FFmpeg.FFmpeg
    } elseif (CommandExists "choco") {
        Write-Host "Installing ffmpeg via Chocolatey..."
        choco install ffmpeg -y
    } else {
        Write-Host "Neither winget nor choco found. Attempting manual download..."
        $tmp = "$env:TEMP\ffmpeg.zip"
        Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $tmp -UseBasicParsing
        $dest = "C:\ffmpeg"
        Expand-Archive -Path $tmp -DestinationPath $dest
        # The zip contains a subfolder, find ffmpeg.exe
        $found = Get-ChildItem -Path $dest -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $ffdir = $found.DirectoryName
            Write-Host "ffmpeg installed to $ffdir. Adding to PATH..."
            [Environment]::SetEnvironmentVariable('PATH', $env:PATH + ";" + $ffdir, [EnvironmentVariableTarget]::Machine)
            Write-Host "You may need to restart your shell for PATH changes to take effect."
        } else {
            Write-Host "Failed to locate ffmpeg.exe after download. Please install manually."
            Remove-Item $tmp -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Installing Python packages from requirements.txt..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Done. Verify: ffmpeg --version && yt-dlp --version"