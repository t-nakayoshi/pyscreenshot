@rem Create EXE (nuitka)
@setlocal
.\.venv\Scripts\nuitka ^
--msvc=14.3 ^
--follow-imports ^
--nofollow-import-to=tkinter ^
--noinclude-unittest-mode=allow ^
--onefile ^
--windows-console-mode=disable ^
--windows-icon-from-ico=./res/ScreenShot.ico ^
--output-dir=dist_nuitka ^
--output-filename=MyScreenShot.exe ^
PyScreenShot.py
