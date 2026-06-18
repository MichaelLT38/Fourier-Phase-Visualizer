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

## Notes

- If SmartScreen appears on another machine, click More info, then Run anyway.
- Rebuild after code changes before publishing a new installer.
