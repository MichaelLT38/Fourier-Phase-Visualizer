# Fourier Drag App

Interactive desktop app to explore how translation, scaling, and rotation of a square affect its 2D Fourier transform.

## Features

- Left panel: white canvas with draggable black square
- Middle panel: live Fourier magnitude spectrum
- Right panel: live Fourier phase map

## Controls

- Left drag: move square
- Hold S + drag: scale square
- Hold R + drag: rotate square
- Press C: center square and clear rotation

## Run From Source

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Build Portable App

```powershell
./build.ps1
```

Output:

- dist\\FourierDragApp\\FourierDragApp.exe

## Build Installer (Recommended)

```powershell
./make-installer.ps1
```

Output:

- installer\\Output\\FourierDragApp-Setup.exe

## GitHub Build And Release

This repo includes a workflow at `.github/workflows/release-installer.yml` that:

- Builds the installer on Windows
- Uploads `FourierDragApp-Setup.exe` as a workflow artifact
- On version tags (`v*`), creates a GitHub Release and attaches the setup exe

### Trigger A Release Build

1. Commit and push your latest changes.
2. Create and push a version tag:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

After the workflow finishes, download the setup file from either:

- Actions run artifacts
- GitHub Releases assets

## Notes

- If SmartScreen appears on another machine, click More info, then Run anyway.
- Rebuild after code changes before publishing a new installer.
