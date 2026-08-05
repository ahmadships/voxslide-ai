"""VoxSlide AI — Entry Point"""

import sys

# Windows: give the process a unique AppUserModelID so the taskbar uses
# our embedded EXE icon instead of grouping under python.exe / a stale cache.
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VoxSlide.AI.Desktop.1.0"
        )
    except Exception:
        pass

import customtkinter
from ui_components import VoxSlideApp

if __name__ == "__main__":
    app = VoxSlideApp()
    app.mainloop()
