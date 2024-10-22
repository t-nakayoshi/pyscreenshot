@rem Create EXE (nuitka)
@setlocal
.\.venv\Scripts\nuitka ^
--msvc=14.3 ^
--follow-imports ^
--nofollow-import-to=tkinter ^
--noinclude-unittest-mode=allow ^
--windows-console-mode=disable ^
--windows-icon-from-ico=./resource_data/ScreenShot.ico ^
--company-name="Nakayoshi Studio" ^
--file-description="PyScreenShot スクリーンショットアプリケーション" ^
--file-version=1.0.7.0 ^
--product-name="PyScreenShot" ^
--product-version=1.0.7 ^
--copyright="(C) 2024-, t-nakayoshi (Takayoshi Tagawa). All right reserved." ^
--onefile ^
--onefile-tempdir-spec="{TEMP}/{COMPANY}/{PRODUCT}" ^
--output-filename=PyScreenShot.exe ^
PyScreenShot.py
