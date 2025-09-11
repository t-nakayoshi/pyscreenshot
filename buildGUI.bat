@rem Create EXE (nuitka)
@setlocal
.\.venv\Scripts\nuitka ^
--msvc=14.3 ^
--follow-imports ^
--nofollow-import-to=tkinter ^
--noinclude-unittest-mode=allow ^
--noinclude-setuptools-mode=allow ^
--windows-console-mode=disable ^
--windows-icon-from-ico=./resource_data/ScreenShot.ico ^
--company-name="Nakayoshi Studio" ^
--file-description="PyScreenShot: スクリーンショットアプリケーション" ^
--file-version=2.0.0.0 ^
--product-name="PyScreenShot" ^
--product-version=2.0.0 ^
--copyright="Copyright(C) 2024-2025, t-nakayoshi (Takayoshi Tagawa). All right reserved." ^
--onefile ^
--onefile-tempdir-spec="{TEMP}/{COMPANY}/{PRODUCT}" ^
--output-filename=PyScreenShot.exe ^
PyScreenShot.py
