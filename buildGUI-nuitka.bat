@rem Create EXE (nuitka)
@setlocal
.\.venv\Scripts\nuitka ^
--msvc=14.3 ^
--follow-imports ^
--nofollow-import-to=tkinter ^
--noinclude-unittest-mode=allow ^
--onefile ^
--windows-console-mode=disable ^
--windows-icon-from-ico=./resource_data/ScreenShot.ico ^
--file-description="PyScreenShot スクリーンショットアプリケーション" ^
--file-version=1.0.0.0 ^
--product-name="Nakayoshi's PyScreenShot" ^
--product-version=1.0.0 ^
--copyright="(C) 2024-, t-nakayoshi (Takayoshi Tagawa). All right reserved." ^
--output-dir=dist_nuitka ^
--output-filename=PyScreenShot.exe ^
PyScreenShot.py
