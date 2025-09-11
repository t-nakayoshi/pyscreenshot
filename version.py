#!/usr/bin/env python3
#
"""version.py

バージョン情報

"""

# fmt: off
_author = "t-nakayoshi (Takayoshi Tagawa)"
_app_name: str = "PyScreenShot"

INFO: dict = {
    "APP_NAME": f"{_app_name}",
    "FILE_DESCRIPTION": f"{_app_name} スクリーンショットアプリケーション",
    "FILE_VERSION": "2.0.0.0",
    "PRODUCT_NAME": f"{_app_name}",
    "PRODUCT_VERSION": "2.0.0",
    "VERSION": "2.0.0"
}

COPYRIGHT: dict = {
    "AUTHOR"   : _author,
    "COPYRIGHT": f"Copyright(C) 2024-, {_author}. All right reserved.",
    "LICENSE"  : "MIT License",
}
# fmt: on
