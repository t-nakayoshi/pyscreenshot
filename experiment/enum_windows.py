#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" enum_windows.py
"""
from datetime import datetime
from functools import partial
import sys
import time
from typing import Union
import win32gui


def _debug_print(message: str):
    ts = datetime.now().strftime('%Y/%m/%d %H%M%S.%f')[:-3]
    sys.stdout.write(f'{ts} [debug]:{message}\n')


def enum_window_callback(hwnd:int, lparam:int):
    if win32gui.IsWindowEnabled(hwnd) == 0:
        return

    if win32gui.IsWindowVisible(hwnd) == 0:
        return

    if win32gui.IsIconic(hwnd) != 0:
        return

    GW_HWNDFIRST = 0
    GW_HWNDLAST = 1
    GW_HWNDNEXT = 2
    GW_HWNDPREV = 3
    GW_OWNER = 4
    GW_CHILD = 5
    cmd = GW_OWNER
    owner:int = win32gui.GetWindow(hwnd, cmd)
    # if owner != 0:
    #     # hwnd = owner
    #     # owner = win32gui.GetWindow(hwnd, cmd)
    #     return

    # window_text = 'None' if (window_text := win32gui.GetWindowText(hwnd)) == '' else window_text
    if (window_text := win32gui.GetWindowText(hwnd)) == '':
        return
    elif window_text in ['Microsoft Text Input Application', 'Program Manager']:
        return

    class_name:str = win32gui.GetClassName(hwnd)
    if True in {x in class_name for x in ['QToolTip', 'QPopup', 'QWindowPopup', 'QWindowToolTip']}:
        return
    # if (class_name := win32gui.GetClassName(hwnd)) in ['CabinetWClass']:  # 'CabinetWClass' = Windows Explorer
    #     return

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width  = abs(right - left)
    height = abs(bottom - top)
    area = {'left': left, 'top': top, 'width': width, 'height': height}

    info: str = f'HWND:{hwnd:08x}, OWNER={owner:08x}, WINDOW_TEXT={window_text}, CLASS_NAME:{class_name}, RECT:{area}'
    print(info)


if __name__ == "__main__":
    while True:
        win32gui.EnumWindows(partial(enum_window_callback), 0)
        print('====')
        time.sleep(2)
