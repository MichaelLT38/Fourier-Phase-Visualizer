# Share As A Double-Click App (Windows)

You have two distribution options:

1. Portable executable (fastest)
2. Installer executable (best for non-technical users)

## Option 1: Portable EXE

Build:

```powershell
./build.ps1
```

or

```bat
build.bat
```

Share:

- `dist\\FourierDragApp\\` (share the full folder)

## Option 2: Installer EXE (recommended)

Install Inno Setup once:

- https://jrsoftware.org/isdl.php

Build installer:

```powershell
./make-installer.ps1
```

or

```bat
make-installer.bat
```

Share:

- `installer\\Output\\FourierDragApp-Setup.exe`

Users run the setup file, click through the wizard, then launch from Start Menu/Desktop.

## Notes

- Rebuild after changing `main.py`.
- SmartScreen may show "More info" then "Run anyway" on unsigned builds.
- The installer is recommended over portable sharing for best reliability.
