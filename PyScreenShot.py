#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" MyScreenShot
スクリーンショットアプリケーション
* 
* 
"""
import argparse
from enum import IntEnum, auto
import configparser
from functools import partial
import io
import mss
import os
from PIL import Image
import queue
import mss.tools
from screeninfo import get_monitors
import sys
from typing import Union
import win32clipboard
import win32gui

import wx
from wx.adv import TaskBarIcon, EVT_TASKBAR_LEFT_DCLICK, Sound, AboutBox, AboutDialogInfo

from myutils import get_running_path, platform_info, scan_directory, atof, natural_keys
from res import app_icon, menu_image, sound

__version__ = '1.0.0'
__author__ = 't-nakayoshi (Takayoshi Tagawa)'

_app_name_ = 'My ScreenShot'

# 実行ファイルパス
_EXE_PATH = ''
# リソースファイルパス
_RESRC_PATH = ''                        # アプリアイコン等
# 設定ファイルパス
_CONFIG_FILE = 'config.ini'
# ヘルプファイル
_HELP_FILE = 'manual.html'

_TRAY_TOOLTIP = _app_name_ + ' App'
#_TRAY_ICON = 'ScreenShot.ico'

_MAX_SAVE_FOLDERS = 16
_BASE_DELAY_TIME = 400  # (ms)

_CONFIG_DEFAULT = {
    'basic': {
        'mouse_cursor': 'False',
        'sound_on_capture': 'False',
        'auto_save': 'True',
        'prefix': '1',
        'prefix_string': 'SS',
        'sequence_digits': '6',
        'start_number': '0',
        'save_folder_index': '-1',
    },
    'delayed_capture': {
        'delayed_capture': 'False',
        'delayed_time': '5'
    },
    'trimming': {
        'trimming': 'False',
        'top': '0',
        'bottom': '0',
        'left': '0',
        'right': '0'
    },
    'hotkey': {
        'clipboard': 'Ctrl + Alt',
        'imagefile': 'Ctrl + Shift',
        'active_window': 'F9'
    },
    'periodic': {
        'save_folder': 'ピクチャ',
        'interval': '3',
        'modifier': '0',
        'exit_key': 'F11',
        'target': '-1',
        'numbering': '0'
    }
}

_NO_CONSOLE = False
debug_mode = False
#

def open_site():
    """
    """
    print("open site.")
    pass
    # import webbrowser
    # webbrowser.open_new(r"https://www.google.com/")


def create_menu_item(menu: wx.Menu, id: int = -1, label: str = '', func = None, kind = wx.ITEM_NORMAL) -> wx.MenuItem:
    """
    """
    item = wx.MenuItem(menu, id, label, kind = kind)
    if func is not None:
        menu.Bind(wx.EVT_MENU, func, id = item.GetId())
    menu.Append(item)

    return item


def enum_window_callback(hwnd:int, lparam:int, window_titles:list[str]):
    # GW_OWNER = 4
    if win32gui.IsWindowEnabled(hwnd) == 0:
        return

    if win32gui.IsWindowVisible(hwnd) == 0:
        return

    if (window_text := win32gui.GetWindowText(hwnd)) == '':
        return

    # if (owner := win32gui.GetWindow(hwnd, GW_OWNER)) != 0:
    #     return

    # if (class_name := win32gui.GetClassName(hwnd)) in ['CabinetWClass']:
    #     return

    if window_text not in window_titles:
        window_titles.append(window_text)


def get_active_window() -> Union[tuple, None]:
    """アクティブウィンドウの座標（RECT）を取得する
    * 取得したRECT情報とWindowタイトルを返す
    （座標はmssのキャプチャー範囲に変換する）
    """
    window_titles: list[str] = []
    win32gui.EnumWindows(partial(enum_window_callback, window_titles=window_titles), 0)
    # for title in window_titles:
    #     print(title)
    # print('====')
    if len(window_titles) == 0:
        return None

    # hwnd  = win32gui.GetForegroundWindow()
    # title = win32gui.GetWindowText(hwnd)
    window_title = window_titles[0]
    if (hwnd := win32gui.FindWindow(None, window_title)) == -1:
        return None

    win32gui.SetForegroundWindow(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width  = abs(right - left)
    height = abs(bottom - top)
    area = {'left': left, 'top': top, 'width': width, 'height': height}

    return (window_title, area)


def copy_bitmap_to_clipboard(data):
    """クリップボードにビットマップデータをコピーする
    """
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()


class MenuIcon(IntEnum):
    HELP = 0
    SETTINGS = auto()
    AUTO_SAVE_FOLDER = auto()
    OPEN_FOLDER = auto()
    PERIODIC = auto()
    COPY_TO_CB = auto()
    SAVE_TO_PNG = auto()
    EXIT = auto()


class SettingsDialog(wx.Dialog):
    """環境設定ダイアログ（wxGladeで、設計&生成）
    """
    def __init__(self, *args, **kwds):
        # begin wxGlade: SettingsDialog.__init__
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)
        self.SetSize((400, 400))
        self.SetTitle(u"環境設定")

        sizer_1 = wx.BoxSizer(wx.VERTICAL)

        self.notebook_1 = wx.Notebook(self, wx.ID_ANY)
        sizer_1.Add(self.notebook_1, 1, wx.EXPAND, 0)

        self.notebook_1_pane_1 = wx.Panel(self.notebook_1, wx.ID_ANY)
        self.notebook_1.AddPage(self.notebook_1_pane_1, u"基本設定")

        sizer_3 = wx.BoxSizer(wx.VERTICAL)

        sizer_4 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_1, wx.ID_ANY, u"保存設定: "), wx.HORIZONTAL)
        sizer_3.Add(sizer_4, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        sizer_5 = wx.BoxSizer(wx.VERTICAL)
        sizer_4.Add(sizer_5, 1, wx.EXPAND, 0)

        self.radio_auto_save = wx.RadioButton(self.notebook_1_pane_1, wx.ID_ANY, u"ファイル自動保存", style=wx.RB_GROUP)
        sizer_5.Add(self.radio_auto_save, 0, wx.BOTTOM | wx.EXPAND | wx.LEFT, 4)

        sizer_6 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_5.Add(sizer_6, 1, wx.EXPAND, 0)

        label_1 = wx.StaticText(self.notebook_1_pane_1, wx.ID_ANY, u"保存先: ")
        sizer_6.Add(label_1, 0, 0, 0)

        self.list_box_auto_save_folders = wx.ListBox(self.notebook_1_pane_1, wx.ID_ANY, choices=[])
        sizer_6.Add(self.list_box_auto_save_folders, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        sizer_7 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_5.Add(sizer_7, 0, wx.BOTTOM | wx.EXPAND | wx.TOP, 4)

        sizer_7.Add((49, 20), 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_add = wx.Button(self.notebook_1_pane_1, wx.ID_ANY, u"追加")
        self.button_add.SetMinSize((49, 23))
        sizer_7.Add(self.button_add, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_remove = wx.Button(self.notebook_1_pane_1, wx.ID_ANY, u"削除")
        self.button_remove.SetMinSize((49, 23))
        sizer_7.Add(self.button_remove, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_7.Add((20, 20), 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_move_up = wx.Button(self.notebook_1_pane_1, wx.ID_ANY, u"△")
        self.button_move_up.SetMinSize((41, 23))
        sizer_7.Add(self.button_move_up, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_move_down = wx.Button(self.notebook_1_pane_1, wx.ID_ANY, u"▽")
        self.button_move_down.SetMinSize((41, 23))
        sizer_7.Add(self.button_move_down, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_7.Add((8, 20), 0, wx.EXPAND, 0)

        sizer_8 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_5.Add(sizer_8, 0, wx.BOTTOM | wx.EXPAND | wx.TOP, 4)

        label_2 = wx.StaticText(self.notebook_1_pane_1, wx.ID_ANY, u"接頭語: ", style=wx.ALIGN_CENTER_HORIZONTAL)
        sizer_8.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.textctrl_prefix = wx.TextCtrl(self.notebook_1_pane_1, wx.ID_ANY, "SS")
        self.textctrl_prefix.SetMinSize((41, 23))
        sizer_8.Add(self.textctrl_prefix, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        label_3 = wx.StaticText(self.notebook_1_pane_1, wx.ID_ANY, u"シーケンス桁数: ")
        sizer_8.Add(label_3, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.spin_ctrl_sequence_digit = wx.SpinCtrl(self.notebook_1_pane_1, wx.ID_ANY, "6", min=1, max=6)
        self.spin_ctrl_sequence_digit.SetMinSize((41, 23))
        sizer_8.Add(self.spin_ctrl_sequence_digit, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        label_4 = wx.StaticText(self.notebook_1_pane_1, wx.ID_ANY, u"開始番号: ", style=wx.ALIGN_CENTER_HORIZONTAL)
        sizer_8.Add(label_4, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.spin_ctrl_sequence_start_no = wx.SpinCtrl(self.notebook_1_pane_1, wx.ID_ANY, "0", min=0, max=100000)
        sizer_8.Add(self.spin_ctrl_sequence_start_no, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.radio_inquire_save_name = wx.RadioButton(self.notebook_1_pane_1, wx.ID_ANY, u"保存ファイル名を毎回指定する")
        sizer_5.Add(self.radio_inquire_save_name, 0, wx.ALL | wx.EXPAND, 4)

        self.checkbox_mcursor = wx.CheckBox(self.notebook_1_pane_1, wx.ID_ANY, u"マウスカーソルをキャプチャする")
        sizer_3.Add(self.checkbox_mcursor, 0, wx.ALL, 4)

        self.checkbox_beep_on_capture = wx.CheckBox(self.notebook_1_pane_1, wx.ID_ANY, u"キャプチャ終了時に音を鳴らす")
        sizer_3.Add(self.checkbox_beep_on_capture, 0, wx.ALL, 4)

        self.notebook_1_pane_2 = wx.Panel(self.notebook_1, wx.ID_ANY)
        self.notebook_1.AddPage(self.notebook_1_pane_2, u"その他の設定")

        sizer_9 = wx.BoxSizer(wx.VERTICAL)

        sizer_12 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"遅延キャプチャ: "), wx.HORIZONTAL)
        sizer_9.Add(sizer_12, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        self.checkbox_delayed = wx.CheckBox(sizer_12.GetStaticBox(), wx.ID_ANY, u"遅延キャプチャ", style=wx.CHK_2STATE)
        sizer_12.Add(self.checkbox_delayed, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        self.spin_ctrl_delay_time = wx.SpinCtrl(sizer_12.GetStaticBox(), wx.ID_ANY, "5", min=1, max=600)
        sizer_12.Add(self.spin_ctrl_delay_time, 0, wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 4)

        label_10 = wx.StaticText(sizer_12.GetStaticBox(), wx.ID_ANY, u"秒後")
        sizer_12.Add(label_10, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)

        sizer_13 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"ホット・キー: "), wx.HORIZONTAL)
        sizer_9.Add(sizer_13, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        sizer_10 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_13.Add(sizer_10, 0, wx.EXPAND, 0)

        self.radio_box_hotkey_clipboard = wx.RadioBox(self.notebook_1_pane_2, wx.ID_ANY, u"クリップボードへコピー: ", choices=["Ctrl + Alt", "Ctrl + Shift"], majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.radio_box_hotkey_clipboard.SetMinSize((125, 65))
        self.radio_box_hotkey_clipboard.SetSelection(0)
        sizer_10.Add(self.radio_box_hotkey_clipboard, 0, wx.BOTTOM | wx.RIGHT, 4)

        self.radio_box_hotkey_imagefile = wx.RadioBox(self.notebook_1_pane_2, wx.ID_ANY, u"PNGへ保存: ", choices=["Ctrl + Alt", "Ctrl + Shift"], majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.radio_box_hotkey_imagefile.SetMinSize((113, 65))
        self.radio_box_hotkey_imagefile.SetSelection(1)
        sizer_10.Add(self.radio_box_hotkey_imagefile, 0, wx.BOTTOM | wx.EXPAND | wx.RIGHT, 4)

        sizer_11 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"アクティブウィンドウ: "), wx.VERTICAL)
        sizer_10.Add(sizer_11, 0, wx.BOTTOM | wx.EXPAND, 4)

        self.choice_hotkey_active_window = wx.Choice(sizer_11.GetStaticBox(), wx.ID_ANY, choices=["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"])
        self.choice_hotkey_active_window.SetSelection(8)
        sizer_11.Add(self.choice_hotkey_active_window, 0, wx.EXPAND, 0)

        sizer_14 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"トリミング: "), wx.VERTICAL)
        sizer_9.Add(sizer_14, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        sizer_16 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_14.Add(sizer_16, 0, wx.EXPAND | wx.TOP, 2)

        self.checkbox_triming = wx.CheckBox(self.notebook_1_pane_2, wx.ID_ANY, u"有効", style=wx.CHK_2STATE)
        sizer_16.Add(self.checkbox_triming, 0, wx.EXPAND, 0)

        label_15 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"上: ")
        sizer_16.Add(label_15, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.spin_ctrl_triming_top_copy = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100)
        sizer_16.Add(self.spin_ctrl_triming_top_copy, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        label_16 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"下: ")
        sizer_16.Add(label_16, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.spin_ctrl_triming_bottom_copy = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100)
        sizer_16.Add(self.spin_ctrl_triming_bottom_copy, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        label_17 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"左: ")
        sizer_16.Add(label_17, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.spin_ctrl_triming_left_copy = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100)
        sizer_16.Add(self.spin_ctrl_triming_left_copy, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        label_18 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"右: ")
        sizer_16.Add(label_18, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.spin_ctrl_triming_right_copy = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100)
        sizer_16.Add(self.spin_ctrl_triming_right_copy, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        sizer_9.Add((20, 20), 1, wx.EXPAND, 0)

        sizer_2 = wx.StdDialogButtonSizer()
        sizer_1.Add(sizer_2, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

        self.button_OK = wx.Button(self, wx.ID_OK, "")
        self.button_OK.SetDefault()
        sizer_2.AddButton(self.button_OK)

        self.button_CANCEL = wx.Button(self, wx.ID_CANCEL, "")
        sizer_2.AddButton(self.button_CANCEL)

        sizer_2.Realize()

        self.notebook_1_pane_2.SetSizer(sizer_9)

        self.notebook_1_pane_1.SetSizer(sizer_3)

        self.SetSizer(sizer_1)

        self.SetAffirmativeId(self.button_OK.GetId())
        self.SetEscapeId(self.button_CANCEL.GetId())

        self.Layout()

        self.button_add.Bind(wx.EVT_BUTTON, self.on_save_folder_add)
        self.button_remove.Bind(wx.EVT_BUTTON, self.on_save_folder_del)
        self.button_move_up.Bind(wx.EVT_BUTTON, self.on_save_folder_up)
        self.button_move_down.Bind(wx.EVT_BUTTON, self.on_save_folder_down)
        # end wxGlade

    def on_save_folder_add(self, event):  # wxGlade: SettingsDialog.<event_handler>
        print("Event handler 'on_save_folder_add' not implemented!")
        event.Skip()
    def on_save_folder_del(self, event):  # wxGlade: SettingsDialog.<event_handler>
        print("Event handler 'on_save_folder_del' not implemented!")
        event.Skip()
    def on_save_folder_up(self, event):  # wxGlade: SettingsDialog.<event_handler>
        print("Event handler 'on_save_folder_up' not implemented!")
        event.Skip()
    def on_save_folder_down(self, event):  # wxGlade: SettingsDialog.<event_handler>
        print("Event handler 'on_save_folder_down' not implemented!")
        event.Skip()
# end of class SettingsDialog


class MyScreenShot(TaskBarIcon):
    """Menu IDs"""
    # Help
    ID_MENU_HELP  = 901         # ヘルプを表示
    ID_MENU_ABOUT = 902         # バージョン情報
    # 環境設定
    ID_MENU_SETTINGS = 101
    # クイック設定
    ID_MENU_MCURSOR  = 102      # マウスカーソルキャプチャを有効
    ID_MENU_DELAYED  = 103      # 遅延キャプチャを有効
    ID_MENU_TRIMMING = 104      # トリミングを有効
    #--- 保存先フォルダ(Base)
    ID_MENU_FOLDER1 = 201
    # フォルダを開く
    ID_MENU_OPEN_AUTO     = 301 # 自動保存フォルダ(選択中)
    ID_MENU_OPEN_PERIODIC = 302 # 定期実行フォルダ
    # 定期実行設定
    ID_MENU_PERIODIC = 401
    # クリップボードへコピー
    ID_MENU_SCREEN0_CB = 501    # デスクトップ
    ID_MENU_SCREEN1_CB = 502    # ディスプレイ1
    ID_MENU_ACTIVE_CB  = 590    # アクティブウィンドウ
    # PNG保存
    ID_MENU_SCREEN0 = 601       # デスクトップ
    ID_MENU_SCREEN1 = 602       # ディスプレイ1
    ID_MENU_ACTIVE  = 690       # アクティブウィンドウ
    # 終了
    ID_MENU_EXIT = 991

    def __init__(self, frame):
        self.frame = frame
        super(MyScreenShot, self).__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # プロパティ
        #--- basic
        self._auto_save:bool = True
        self._save_folders:list[str] = []
        self._folder_index: int = -1
        self._prefix: int = 0
        self._prefix_string: str = ''
        self._sequence_digits: int = 6
        self._sequence_start: int = 0
        self._capture_mcursor: bool = False
        self._sound_on_capture: bool = False
        #--- other
        self._delayed_capture: bool = False
        self._delayed_time: int = 5
        self._hotkey_clipboard: int = 0
        self._hotkey_imagefile: int = 1
        self._hotkey_activewin: int = 8
        self._trimming: bool = False
        self._trimming_size: list[int] = []
        #--- periodic
        self._periodic_save_folder: str = ''
        self._periodic_interval: int = 3
        self._periodic_exit_modifier: int = 0
        self._periodic_exit_fkey: int = 10
        self._periodic_target: int = 0
        self._periodic_numbering: int = 0
        #
        self.ss_queue = queue.Queue()
        # 初期処理
        self.initialize()

    def CreatePopupMenu(self):
        """Popupメニューの生成 (override)
        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。
        """
        # print("CreatePopupMenu")
        self.dis_count = len(get_monitors())    # ディスプレイ数を取得する
        # メニューの生成
        menu = wx.Menu()
        # Help
        sub_menu = wx.Menu()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_HELP, 'Helpを表示', self.on_menu_show_help)
        sub_menu.AppendSeparator()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_ABOUT, 'バージョン情報...', self.on_menu_show_about)
        item = menu.AppendSubMenu(sub_menu, 'Help')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.HELP.value) ))
        menu.AppendSeparator()
        # Settings
        item = create_menu_item(menu, MyScreenShot.ID_MENU_SETTINGS, '環境設定...', self.on_menu_settings)
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.SETTINGS.value)))
        sub_menu = wx.Menu()
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_MCURSOR, 'マウスカーソルキャプチャを有効', self.on_menu_toggle_mouse_capture, kind = wx.ITEM_CHECK)
        sub_item.Enable(False)  # Windowsでは現状マウスカーソルがキャプチャ出来ないので「無効」にしておく
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_DELAYED, '遅延キャプチャを有効', self.on_menu_toggle_delayed_capture, kind = wx.ITEM_CHECK)
        sub_item.Check(self.config.getboolean('other', 'delayed_capture', fallback = False))
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_TRIMMING, 'トリミングを有効', self.on_menu_toggle_trimming, kind = wx.ITEM_CHECK)
        sub_item.Check(self.config.getboolean('trimming', 'trimming', fallback = False))
        menu.AppendSubMenu(sub_menu, 'クイック設定')
        menu.AppendSeparator()
        # Auto save folder
        sub_menu = wx.Menu()
        value = self.config.get('basic', 'folder1', fallback = 'ピクチャ')
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_FOLDER1, f'1: {value}', self.on_menu_select_save_folder, kind = wx.ITEM_RADIO)
        if self.config.getint('basic', 'save_folder_index', fallback = 0) == 0:
            sub_item.Check()
        self.save_folder_count = 1
        for n in range(1, _MAX_SAVE_FOLDERS):
            value = self.config.get('basic', f'folder{n + 1}', fallback = '')
            if len(value) == 0:
                break
            sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_FOLDER1 + n, f'{n + 1}: {value}', self.on_menu_select_save_folder, kind = wx.ITEM_RADIO)
            self.save_folder_count += 1
            if n == self.config.getint('basic', 'save_folder_index', fallback = 0):
                sub_item.Check()
        item = menu.AppendSubMenu(sub_menu, '保存先フォルダ')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.AUTO_SAVE_FOLDER.value)))
        # Open folder
        sub_menu = wx.Menu()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_AUTO, '1: 自動保存先フォルダ(選択中)', self.on_menu_open_folder)
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_PERIODIC, '2: 定期実行フォルダ', self.on_menu_open_folder)
        item = menu.AppendSubMenu(sub_menu, 'フォルダを開く')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.OPEN_FOLDER.value)))
        menu.AppendSeparator()
        # Periodic caputure settings
        item = create_menu_item(menu, MyScreenShot.ID_MENU_PERIODIC, '定期実行設定...', self.on_menu_periodic_settings)
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.PERIODIC.value)))
        menu.AppendSeparator()
        # Caputure
        sub_menu1 = wx.Menu()
        sub_menu2 = wx.Menu()
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN0_CB, f'0: デスクトップ', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN0, f'0: デスクトップ', self.on_menu_imagefile)
        if self.dis_count > 1:
            for n in range(0, self.dis_count):
                create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN1_CB + n, f'{n + 1}: ディスプレイ {n + 1}', self.on_menu_clipboard)
                create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN1 + n, f'{n + 1}: ディスプレイ {n + 1}', self.on_menu_imagefile)
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_ACTIVE_CB, f'{self.dis_count + 1}: アクティブウィンドウ', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_ACTIVE, f'{self.dis_count + 1}: アクティブウィンドウ', self.on_menu_imagefile)
        item = menu.AppendSubMenu(sub_menu1, 'クリップボードへコピー')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.COPY_TO_CB.value)))
        item = menu.AppendSubMenu(sub_menu2, 'PNG保存')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.SAVE_TO_PNG.value)))
        menu.AppendSeparator()
        # Exit
        item = create_menu_item(menu, MyScreenShot.ID_MENU_EXIT, '終了', self.on_menu_exit)
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.EXIT.value)))

        return menu

    def initialize(self):
        """初期処理
        * 各種設定値の初期化、設定読み込み、ディスプレイ情報の取得、等
        Args:
            none
        Returns:
            none
        """
        # 動作環境情報取得
        self._platform_info = platform_info()
        # Load Application ICON
        self._app_icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)
        self.SetIcon(self._app_icons.GetIcon(wx.Size(16, 16)), _TRAY_TOOLTIP)
        # 設定値の初期設定と設定ファイルの読み込み
        self.load_config()
        # メニューアイコン画像の展開
        self._icon_img = wx.ImageList(24, 24)
        for name in menu_image.index:
            self._icon_img.Add(menu_image.catalog[name].GetBitmap())
        # BEEP音
        self._beep = Sound()
        self._beep.CreateFromData(sound.get_snd_beep_bytearray())
        self._success = Sound()
        self._success.CreateFromData(sound.get_snd_success_bytearray())

    def set_property(self):
        """設定値をプロパティに展開する
        """
        # 自動保存
        self._auto_save = self.config.getboolean('basic','auto_save', fallback=True)
        # 自動保存フォルダ
        self._folder_index = self.config.getint('basic', 'save_folder_index', fallback=-1)
        for n in range(_MAX_SAVE_FOLDERS):
            option_name: str = 'folder' + str(n + 1)
            if not self.config.has_option('basic', option_name):
                break
            option: str = self.config.get('basic', option_name)
            self._save_folders.append(option)
        if len(self._save_folders) > 0 and self._folder_index < 0:
            self._folder_index = 0
            self.config.set('basic', 'save_folder_index', str(self._folder_index))
        # 接頭語
        self._prefix = self.config.getint('basic', 'prefix', fallback=1)
        self._prefix_string = self.config.get('basic', 'prefix_string', fallback='SS')
        self._sequence_digits = self.config.getint('basic', 'sequence_digits', fallback=6)
        self._sequence_start = self.config.getint('basic', 'sequence_start', fallback=0)
        self._capture_mcursor = self.config.getboolean('basic', 'mouse_cursor', fallback=False)
        self._sound_on_capture = self.config.getboolean('basic', 'sound_on_capture', fallback=False)

    def load_config(self):
        """設定値読み込み処理
        * 各種設定値を初期設定後、設定ファイルから読み込む。
        Args:
            none
        Returns:
            none
        Note:
            ConfigParserモジュール使用
        """
        global _CONFIG_DEFAULT
        global _CONFIG_FILE
        self.config = configparser.ConfigParser()
        self.config.read_dict(_CONFIG_DEFAULT)
        self.save_folder_count = 0

        if os.path.exists(_CONFIG_FILE):
            try:
                with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config.read_file(f)
            except OSError as e:
                wx.MessageBox(f'Configration file load failed.\n ({e})\n Use default settings.', 'ERROR', wx.ICON_ERROR)
            except configparser.Error as e:
                wx.MessageBox(f'Configration file parse failed.\n ({e})', 'ERROR', wx.ICON_ERROR)
        else:
            wx.MessageBox('Configration file not found.\nCreate default configuration file.', 'Attension', wx.ICON_EXCLAMATION)
            self.save_config()

        self.set_property()

    def save_config(self):
        """設定値保存処理
        * 各種設定値をファイルの書き込む。
        Args:
            none
        Returns:
            none
        Note:
            ConfigParserモジュール使用
        """
        global _CONFIG_FILE
        try:
            with open(_CONFIG_FILE, 'w') as fc:
                self.config.write(fc)

        except OSError as e:
            wx.MessageBox(f'Configration file save failed.\n ({e})', 'ERROR', wx.ICON_ERROR)

    def do_capture(self):
        """キャプチャー実行
        """
        req:dict = self.ss_queue.get()
        moni_no:int = req['moni_no']
        clipboard:bool = req['clipboard']
        filename:str = req['filename']
        # print(f"do_capture moni_no={moni_no}, clipboard={clipboard}, filename={filename}")

        sct_img = None
        msg = ''
        with mss.mss() as sct:
            match moni_no:
                case 90:
                    if (info := get_active_window()) == None:
                        return

                    window_title, area_coord = info
                    sct_img = sct.grab(area_coord)
                    msg = f'"Active window - {window_title}" area={area_coord}'

                case _:
                    if moni_no < 0 and moni_no >= len(sct.monitors):
                        return

                    sct_img = sct.grab(sct.monitors[moni_no])
                    if moni_no == 0:
                        msg = '"Desktop"'
                    else:
                        msg = f'"Display-{moni_no}"'

        if sct_img is not None:
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            # トリミング
            if self.config.getboolean('triming', 'triming', fallback=False):
                top    = self.config.getint('triming', 'top', fallback=0)
                bottom = self.config.getint('triming', 'top', fallback=0)
                left   = self.config.getint('triming', 'top', fallback=0)
                right  = self.config.getint('triming', 'top', fallback=0)
                width, height = img.size
                box = (left, top, width - right if width > right else width, height - bottom if height > bottom else height)
                img.crop(box)

            if clipboard:
                # クリップボードへコピー
                output = io.BytesIO()
                img.convert('RGB').save(output, 'BMP')
                data = output.getvalue()[14:]
                output.close()
                copy_bitmap_to_clipboard(data)
                print(f'capture {msg} & copy clipboard')
            else:
                # ファイルへ保存
                if len(filename) > 0:
                    img.save(filename)


    def on_menu_show_help(self, event):
        """HELPメニューイベントハンドラ
        * アプリケーションのHELPを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        print("on_menu_show_help")

    def on_menu_show_about(self, event):
        """Aboutメニューイベントハンドラ
        * アプリケーションのバージョン情報などを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        global __version__
        global __author__
        info = AboutDialogInfo()
        info.SetIcon(self._app_icons.GetIcon(wx.Size(48, 48)))
        info.SetName(_app_name_)
        info.SetVersion(f' Ver.{__version__}\n on Python {self._platform_info[2]} and wxPython {wx.__version__}.')
        info.SetCopyright(f'(C) 2024-, by {__author__}. All right reserved.')
        info.SetDescription('Screenshot tool. (EXE conversion is by Nuitka.)')
        info.SetLicense('MIT License.')
        # info.SetWebSite("")
        info.AddDeveloper(__author__)
        # 表示
        AboutBox(info, self.frame)

    def on_menu_settings(self, event):
        """Settingメニューイベントハンドラ
        * アプリケーションの設定ダイヤログを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        with SettingsDialog(None, wx.ID_ANY, "") as dlg:
            # 設定値をダイアログ側へ渡す
            flag = self.config.getboolean('basic', 'auto_save', fallback=True)
            if flag:
                dlg.radio_auto_save.SetValue(True)
            else:
                dlg.radio_inquire_save_name.SetValue(True)
            if dlg.ShowModal() == wx.ID_OK:
                print("on_menu_settings closed 'OK'")
                self.config.set('basic', 'auto_save', str(dlg.radio_auto_save.GetValue()))
                pass

    def on_menu_toggle_mouse_capture(self, event):
        """Mouse captureメニューイベントハンドラ
        * マウスカーソルのキャプチャーを有効/無効にする。
          ※現在の所、Windowsではキャプチャー出来ない
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        flag = not self.config.getboolean('other', 'mouse_cursor', fallback = False)
        self.config.set('other', 'mouse_cursor', str(flag))
        print(f"on_menu_toggle_mouse_capture ({flag})")

    def on_menu_toggle_delayed_capture(self, event):
        """Delayed captureメニューイベントハンドラ
        * 遅延キャプチャーを有効/無効にする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        flag = not self.config.getboolean('other', 'delayed_capture', fallback = True)
        self.config.set('other', 'delayed_capture', str(flag))
        print(f"on_menu_toggle_delayed_capture ({flag})")

    def on_menu_toggle_trimming(self, event):
        """Trimmingメニューイベントハンドラ
        * トリミングを有効/無効にする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        flag = not self.config.getboolean('trimming', 'trimming', fallback = True)
        self.config.set('trimming', 'trimming', str(flag))
        print(f"on_menu_toggle_trimming ({flag})")

    def on_menu_select_save_folder(self, event):
        """Select save folderメニューイベントハンドラ
        * 自動保存フォルダーを切り替える。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        index1 = self.config.getint('basic', 'save_folder_index', fallback = 0)
        index2 = index1
        id = event.GetId()
        for n in range(0, self.save_folder_count):
            if id == (MyScreenShot.ID_MENU_FOLDER1 + n):
                index2 = n
                self.config.set('basic', 'save_folder_index', str(n))
        print(f'on_menu_select_save_folder (id={id}), index={index1}=>{index2}')

    def on_menu_open_folder(self, event):
        """Open folderメニューイベントハンドラ
        * 自動または定期保存フォルダーを開く。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        id = event.GetId()
        print(f'on_menu_open_folder ({id})')

    def on_menu_periodic_settings(self, event):
        """
        """
        print("on_menu_periodic_settings")

    def on_menu_clipboard(self, event):
        """Copy to clipboardメニューイベントハンドラ
        * キャプチャー画像をClipboardへコピーする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        global _BASE_DELAY_TIME
        id = event.GetId()
        moni_no = -1
        if id == MyScreenShot.ID_MENU_ACTIVE_CB:
            moni_no = 90
        else:
            moni_no = id - MyScreenShot.ID_MENU_SCREEN0_CB

        self.ss_queue.put({'moni_no': moni_no, 'clipboard': True, 'filename': ''})
        print(f'on_menu_clipboard ({id})')
        delay_ms = _BASE_DELAY_TIME
        if self.config.getboolean('other', 'delayed_capture', fallback = False):
            delay_ms = self.config.getint('other', 'delayed_time', fallback = 1) * 1000
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def on_menu_imagefile(self, event):
        """Save to PNG fileメニューイベントハンドラ
        * キャプチャー画像をPNGファイルとして保存する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        global _BASE_DELAY_TIME
        id = event.GetId()
        moni_no = -1
        if id == MyScreenShot.ID_MENU_ACTIVE:
            moni_no = 90
        else:
            moni_no = id - MyScreenShot.ID_MENU_SCREEN0

        # 保存ファイル名生成
        filename = ''

        self.ss_queue.put({'moni_no': moni_no, 'clipboard': True, 'filename': ''})
        print(f'on_menu_imagefile ({id})')
        delay_ms = _BASE_DELAY_TIME
        if self.config.getboolean('other', 'delayed_capture', fallback = False):
            delay_ms = self.config.getint('other', 'delayed_time', fallback = 1) * 1000
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def on_menu_exit(self, event):
        """Exitメニューイベントハンドラ
        * アプリケーションを終了する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        # print('on_menu_exit')
        wx.CallAfter(self.Destroy)
        self.frame.Close()


class App(wx.App):

    def OnInit(self):
        frame = wx.Frame(None)
        frame.Centre()  # AboutBoxはプライマリディスプレイの中心に出す
        self.SetTopWindow(frame)
        MyScreenShot(frame)

        print('launch App')
        return True


def app_init():
    """アプリケーション初期化
    * 設定ファイル、リソースファイルのPATHを取得等
    Args:
        none
    Returns:
        none
    """
    global _CONFIG_FILE
    global _EXE_PATH
    global _RESRC_PATH
    global _NO_CONSOLE
    # 実行ファイル展開PATHを取得
    base_path, _NO_CONSOLE = get_running_path()
    # 実行ファイルPATH
    _EXE_PATH = os.path.dirname(sys.argv[0])
    _EXE_PATH = '.' + os.sep if len(_EXE_PATH) == 0 else _EXE_PATH
    # 設定ファイルは実行ファイル（スクリプト）ディレクトリ下
    _CONFIG_FILE = os.path.join(_EXE_PATH, _CONFIG_FILE)
    # リソースディレクトリは実行ディレクトリ下
    _RESRC_PATH = os.path.join(base_path, _RESRC_PATH)


if __name__ == "__main__":
    app_init()  # 初期化

    app = App(False)
    app.MainLoop()
