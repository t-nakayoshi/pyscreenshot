#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" make_res.py
MyScreenShot向けリソースデータ作成ツール
"""
import os
from base64 import b64encode
from zlib import compress
#import wx

menu_icon_files = [
    '警告音1.wav',
    '決定、ボタン押下8.wav',
    'menu_icon_Help.png',
    'menu_icon_Settings.png',
    'menu_icon_Auto_save_folder.png',
    'menu_icon_Open_folder.png',
    'menu_icon_Periodic_capture_settings.png',
    'menu_icon_Copy_to_clipboard.png',
    'menu_icon_Save_to_PNG.png',
    'menu_icon_Exit.png',
    'ScreenShot.ico',
    ''
]

CHARS = 72


def convert_base64():
    for f in menu_icon_files:
        if f == '':
            break

        data = ''
        with open(f, 'rb') as rfc:
            data = b64encode(compress(rfc.read()))
            print(f'read {f}. ({len(data)}) => ', end='')

            b64name = f + '.base64'
            lines = len(data) // CHARS
            with open(b64name, 'wb') as wfc:
                pos = 0
                if lines > 0:
                    for l in range(1, lines + 1):
                        line = data[pos:(CHARS * l)] + b'\n'
                        wfc.write(line)
                        pos += CHARS
                if len(data) % CHARS > 0:
                    line = data[pos:] + b'\n'
                    wfc.write(line)
                print(f'write {b64name}.')


if __name__ == "__main__":
    convert_base64()
