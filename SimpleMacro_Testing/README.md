# Simple Macro

This repository contains the source for the Simple Macro GUI application.

Contents:
- `simple_macro.py` — Main Tkinter GUI application and macro editor
- `macro.py` — Macro execution helper classes
- `image_utils.py` — Image detection and screen capture utilities
- `recorder_macro.py` — Input recorder and playback utilities
- `example_custom_macro.py` — Example macro using the `RobloxMacro` class
- `requirements.txt` — Python dependencies

Build (create a onefile Windows EXE) using PyInstaller in the project virtual environment:

```powershell
Push-Location 'C:\Users\Owner\OneDrive\Documents\Macro'
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SimpleMacroTest simple_macro.py
Pop-Location
```

