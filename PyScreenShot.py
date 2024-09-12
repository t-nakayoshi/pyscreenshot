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
import keyboard
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
import wx.lib.agw.multidirdialog as MDD

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
        'auto_save': 'True',
        'numbering': '0',
        'prefix': 'SS',
        'sequence_digits': '6',
        'sequence_begin': '0',
        'save_folder_index': '-1',
    },
    'other': {
        'mouse_cursor': 'False',
        'sound_on_capture': 'False'
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
        'clipboard': '0',
        'imagefile': '1',
        'activewin': '8'
    },
    'periodic': {
        'save_folder': '',
        'interval': '3',
        'stop_modifier': '0',
        'stop_fkey': '10',
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
        self.BTN_ID_ADD  = 1001
        self.BTN_ID_DEL  = 1002
        self.BTN_ID_UP   = 1003
        self.BTN_ID_DOWN = 1004
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

        self.panel_1 = wx.Panel(self.notebook_1_pane_1, wx.ID_ANY)
        sizer_3.Add(self.panel_1, 2, wx.ALL | wx.EXPAND, 2)

        sizer_4 = wx.StaticBoxSizer(wx.StaticBox(self.panel_1, wx.ID_ANY, u"保存先"), wx.VERTICAL)

        self.radio_btn_inquire_allways = wx.RadioButton(sizer_4.GetStaticBox(), wx.ID_ANY, u"保存ファイルを毎回指定する", style=wx.RB_GROUP)
        sizer_4.Add(self.radio_btn_inquire_allways, 0, wx.EXPAND | wx.LEFT, 4)

        self.radio_btn_auto_save = wx.RadioButton(sizer_4.GetStaticBox(), wx.ID_ANY, u"ファイル自動保存")
        sizer_4.Add(self.radio_btn_auto_save, 0, wx.BOTTOM | wx.EXPAND | wx.LEFT | wx.TOP, 4)

        sizer_15 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_4.Add(sizer_15, 1, wx.EXPAND, 0)

        self.list_box_auto_save_folders = wx.ListBox(self.panel_1, wx.ID_ANY, choices=[])
        sizer_15.Add(self.list_box_auto_save_folders, 1, wx.ALL | wx.EXPAND, 2)

        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_4.Add(sizer_5, 0, wx.ALL | wx.EXPAND, 2)

        self.button_add_folder = wx.Button(self.panel_1, self.BTN_ID_ADD, u"追加")
        sizer_5.Add(self.button_add_folder, 0, 0, 0)

        self.button_del_folder = wx.Button(self.panel_1, self.BTN_ID_DEL, u"削除")
        sizer_5.Add(self.button_del_folder, 0, 0, 0)

        sizer_5.Add((20, 20), 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_up_folder = wx.Button(self.panel_1, self.BTN_ID_UP, u"△")
        sizer_5.Add(self.button_up_folder, 0, 0, 0)

        self.button_down_folder = wx.Button(self.panel_1, self.BTN_ID_DOWN, u"▽")
        sizer_5.Add(self.button_down_folder, 0, 0, 0)

        self.panel_2 = wx.Panel(self.notebook_1_pane_1, wx.ID_ANY)
        sizer_3.Add(self.panel_2, 0, wx.ALL | wx.EXPAND, 2)

        sizer_6 = wx.StaticBoxSizer(wx.StaticBox(self.panel_2, wx.ID_ANY, u"ナンバリング"), wx.VERTICAL)

        self.radio_btn_numbering_datetime = wx.RadioButton(sizer_6.GetStaticBox(), wx.ID_ANY, u"日時 (yyyymmdd_hhmmss)", style=wx.RB_GROUP)
        sizer_6.Add(self.radio_btn_numbering_datetime, 0, wx.BOTTOM | wx.EXPAND | wx.LEFT, 4)

        self.radio_btn_nubering_prefix_sequence = wx.RadioButton(sizer_6.GetStaticBox(), wx.ID_ANY, u"接頭語+シーケンス番号")
        sizer_6.Add(self.radio_btn_nubering_prefix_sequence, 0, wx.EXPAND | wx.LEFT, 4)

        sizer_7 = wx.StaticBoxSizer(wx.StaticBox(self.panel_2, wx.ID_ANY, ""), wx.HORIZONTAL)
        sizer_6.Add(sizer_7, 0, wx.BOTTOM | wx.EXPAND | wx.LEFT, 4)

        label_2 = wx.StaticText(sizer_7.GetStaticBox(), wx.ID_ANY, u"接頭語: ")
        sizer_7.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.text_ctrl_prefix = wx.TextCtrl(sizer_7.GetStaticBox(), wx.ID_ANY, "")
        self.text_ctrl_prefix.SetMinSize((49, 23))
        sizer_7.Add(self.text_ctrl_prefix, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_3 = wx.StaticText(sizer_7.GetStaticBox(), wx.ID_ANY, u"シーケンス桁数: ")
        sizer_7.Add(label_3, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)

        self.spin_ctrl_sequence_digits = wx.SpinCtrl(sizer_7.GetStaticBox(), wx.ID_ANY, "6", min=1, max=6, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        self.spin_ctrl_sequence_digits.SetMinSize((40, 23))
        sizer_7.Add(self.spin_ctrl_sequence_digits, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_4 = wx.StaticText(sizer_7.GetStaticBox(), wx.ID_ANY, u"開始番号: ")
        sizer_7.Add(label_4, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)

        self.spin_ctrl_sequence_begin = wx.SpinCtrl(sizer_7.GetStaticBox(), wx.ID_ANY, "0", min=0, max=100, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        self.spin_ctrl_sequence_begin.SetMinSize((48, 23))
        sizer_7.Add(self.spin_ctrl_sequence_begin, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.notebook_1_pane_2 = wx.Panel(self.notebook_1, wx.ID_ANY)
        self.notebook_1.AddPage(self.notebook_1_pane_2, u"その他の設定")

        sizer_9 = wx.BoxSizer(wx.VERTICAL)

        sizer_18 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_9.Add(sizer_18, 1, wx.EXPAND, 0)

        self.checkbox_capture_mcursor = wx.CheckBox(self.notebook_1_pane_2, wx.ID_ANY, u"マウスカーソルをキャプチャーする")
        self.checkbox_capture_mcursor.Enable(False)
        sizer_18.Add(self.checkbox_capture_mcursor, 1, wx.ALL | wx.EXPAND, 4)

        sizer_19 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_9.Add(sizer_19, 1, wx.EXPAND, 0)

        self.checkbox_sound_on_capture = wx.CheckBox(self.notebook_1_pane_2, wx.ID_ANY, u"キャプチャー終了時に音を鳴らす")
        sizer_19.Add(self.checkbox_sound_on_capture, 1, wx.ALL | wx.EXPAND, 4)

        sizer_8 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_9.Add(sizer_8, 1, wx.EXPAND, 0)

        self.checkbox_delayed_capture = wx.CheckBox(self.notebook_1_pane_2, wx.ID_ANY, u"遅延キャプチャー")
        self.checkbox_delayed_capture.SetMinSize((89, 15))
        sizer_8.Add(self.checkbox_delayed_capture, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        sizer_10 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_8.Add(sizer_10, 0, wx.EXPAND, 0)

        self.spin_ctrl_delayed_time = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "5", min=1, max=60, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        self.spin_ctrl_delayed_time.SetMinSize((44, 23))
        sizer_10.Add(self.spin_ctrl_delayed_time, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_5 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"秒後")
        sizer_10.Add(label_5, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        sizer_11 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_9.Add(sizer_11, 1, wx.EXPAND, 0)

        self.checkbox_trimming = wx.CheckBox(self.notebook_1_pane_2, wx.ID_ANY, u"トリミング")
        self.checkbox_trimming.SetMinSize((68, 15))
        sizer_11.Add(self.checkbox_trimming, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)

        sizer_12 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_11.Add(sizer_12, 0, wx.EXPAND, 0)

        label_6 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"上: ")
        sizer_12.Add(label_6, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        self.spin_ctrl_trimming_top = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        sizer_12.Add(self.spin_ctrl_trimming_top, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_7 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"下: ")
        sizer_12.Add(label_7, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        self.spin_ctrl_trimming_bottom = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        sizer_12.Add(self.spin_ctrl_trimming_bottom, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_8 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"左: ")
        sizer_12.Add(label_8, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        self.spin_ctrl_trimming_left = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        sizer_12.Add(self.spin_ctrl_trimming_left, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_9 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"右: ")
        sizer_12.Add(label_9, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        self.spin_ctrl_trimming_right = wx.SpinCtrl(self.notebook_1_pane_2, wx.ID_ANY, "0", min=0, max=100, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        sizer_12.Add(self.spin_ctrl_trimming_right, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_20 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"ホット・キー"), wx.HORIZONTAL)
        sizer_9.Add(sizer_20, 1, wx.EXPAND | wx.RIGHT | wx.TOP, 2)

        sizer_21 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"修飾キー"), wx.HORIZONTAL)
        sizer_20.Add(sizer_21, 1, wx.EXPAND, 0)

        sizer_23 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"クリップボードコピー"), wx.VERTICAL)
        sizer_21.Add(sizer_23, 0, wx.EXPAND, 0)

        self.radio_btn_hotkey_bmp_ctrl_alt = wx.RadioButton(sizer_23.GetStaticBox(), wx.ID_ANY, "Ctrl+Alt", style=wx.RB_GROUP)
        self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(1)
        sizer_23.Add(self.radio_btn_hotkey_bmp_ctrl_alt, 1, 0, 0)

        self.radio_btn_hotkey_bmp_ctrl_shift = wx.RadioButton(sizer_23.GetStaticBox(), wx.ID_ANY, "Ctrl+Shift")
        sizer_23.Add(self.radio_btn_hotkey_bmp_ctrl_shift, 1, 0, 0)

        sizer_24 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"PNG保存"), wx.VERTICAL)
        sizer_21.Add(sizer_24, 0, wx.EXPAND | wx.LEFT, 4)

        self.radio_btn_hotkey_png_ctrl_alt = wx.RadioButton(sizer_24.GetStaticBox(), wx.ID_ANY, "Ctrl+Alt", style=wx.RB_GROUP)
        sizer_24.Add(self.radio_btn_hotkey_png_ctrl_alt, 1, 0, 0)

        self.radio_btn_hotkey_png_ctrl_shift = wx.RadioButton(sizer_24.GetStaticBox(), wx.ID_ANY, "Ctrl+Shift")
        self.radio_btn_hotkey_png_ctrl_shift.SetValue(1)
        sizer_24.Add(self.radio_btn_hotkey_png_ctrl_shift, 1, 0, 0)

        sizer_22 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"ターゲット"), wx.VERTICAL)
        sizer_20.Add(sizer_22, 1, wx.EXPAND | wx.LEFT, 4)

        grid_sizer_3 = wx.FlexGridSizer(3, 2, 1, 1)
        sizer_22.Add(grid_sizer_3, 1, wx.EXPAND, 0)

        label_12 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"デスクトップ: ")
        grid_sizer_3.Add(label_12, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.TOP, 2)

        label_13 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, "0")
        grid_sizer_3.Add(label_13, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_14 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"ディスプレイ: ")
        grid_sizer_3.Add(label_14, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.TOP, 2)

        label_15 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"1 ～")
        grid_sizer_3.Add(label_15, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_16 = wx.StaticText(self.notebook_1_pane_2, wx.ID_ANY, u"アクティブウィンドウ: ")
        grid_sizer_3.Add(label_16, 0, wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.TOP, 2)

        self.choice_hotkey_active_window = wx.Choice(self.notebook_1_pane_2, wx.ID_ANY, choices=["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"])
        self.choice_hotkey_active_window.SetSelection(8)
        grid_sizer_3.Add(self.choice_hotkey_active_window, 0, wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 2)

        sizer_9.Add((20, 8), 1, wx.EXPAND, 0)

        sizer_2 = wx.StdDialogButtonSizer()
        sizer_1.Add(sizer_2, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

        self.button_OK = wx.Button(self, wx.ID_OK, "")
        self.button_OK.SetDefault()
        sizer_2.AddButton(self.button_OK)

        self.button_CANCEL = wx.Button(self, wx.ID_CANCEL, "")
        sizer_2.AddButton(self.button_CANCEL)

        sizer_2.Realize()

        self.notebook_1_pane_2.SetSizer(sizer_9)

        self.panel_2.SetSizer(sizer_6)

        self.panel_1.SetSizer(sizer_4)

        self.notebook_1_pane_1.SetSizer(sizer_3)

        self.SetSizer(sizer_1)

        self.SetAffirmativeId(self.button_OK.GetId())
        self.SetEscapeId(self.button_CANCEL.GetId())

        self.Layout()
        self.Centre()

        self.button_add_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_add)
        self.button_del_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_del)
        self.button_up_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_move)
        self.button_down_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_move)
        self.radio_btn_hotkey_bmp_ctrl_alt.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_bmp_ctrl_alt)
        self.radio_btn_hotkey_bmp_ctrl_shift.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_bmp_ctrl_shift)
        self.radio_btn_hotkey_png_ctrl_alt.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_png_ctrl_alt)
        self.radio_btn_hotkey_png_ctrl_shift.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_png_ctrl_shift)
        # end wxGlade

    def on_save_folder_add(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの追加
        """
        defaultPath = os.getcwd()
        agwstyle = MDD.DD_MULTIPLE|MDD.DD_DIR_MUST_EXIST
        with MDD.MultiDirDialog(None, title="フォルダの追加", defaultPath=defaultPath, agwStyle=agwstyle) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            # 選択されたフォルダをListBoxに追加する
            paths = dlg.GetPaths()
            for folder in paths:
                self.list_box_auto_save_folders.Append(folder)
        event.Skip()

    def on_save_folder_del(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの削除
        """
        index = self.list_box_auto_save_folders.GetSelection()
        if index != wx.NOT_FOUND:
            self.list_box_auto_save_folders.Delete(index)
        event.Skip()

    def on_save_folder_move(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの移動（上下）
        """
        index = self.list_box_auto_save_folders.GetSelection()
        id = event.GetId()

        move = 0
        limit = False
        if id == self.BTN_ID_UP:
            move = -1
            limit = True if index > 0 else False
        else:
            move = 1
            limit = True if index < (self.list_box_auto_save_folders.GetCount() - 1) else False

        if index != wx.NOT_FOUND and limit:
            folder = self.list_box_auto_save_folders.GetString(index)
            print(f'folder={index}:{folder}')
            self.list_box_auto_save_folders.Delete(index)
            self.list_box_auto_save_folders.Insert(folder, index + move)
            self.list_box_auto_save_folders.SetSelection(index + move)
        event.Skip()

    """ HotKey: 修飾キーの切り替え制御 """
    def on_btn_hotkey_bmp_ctrl_alt(self, event):  # wxGlade: SettingsDialog.<event_handler>
        self.radio_btn_hotkey_png_ctrl_shift.SetValue(True)
        event.Skip()

    def on_btn_hotkey_bmp_ctrl_shift(self, event):  # wxGlade: SettingsDialog.<event_handler>
        self.radio_btn_hotkey_png_ctrl_alt.SetValue(True)
        event.Skip()

    def on_btn_hotkey_png_ctrl_alt(self, event):  # wxGlade: SettingsDialog.<event_handler>
        self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(True)
        event.Skip()

    def on_btn_hotkey_png_ctrl_shift(self, event):  # wxGlade: SettingsDialog.<event_handler>
        self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(True)
        event.Skip()

    def set_prop(self, prop: dict):
        """設定値をコントロールに反映する
        """
        #--- 基本設定
        # 自動/手動
        if prop['auto_save']:
            self.radio_btn_auto_save.SetValue(True)
        else:
            self.radio_btn_inquire_allways.SetValue(True)
        # 自動保存フォルダ
        for folder in prop['save_folders']:
            self.list_box_auto_save_folders.Append(folder)
        self.list_box_auto_save_folders.SetSelection(prop['save_folder_index'])
        # ナンバリング
        if prop['numbering'] == 0:
            self.radio_btn_numbering_datetime.SetValue(True)
        else:
            self.radio_btn_nubering_prefix_sequence.SetValue(True)
        # 接頭語/シーケンス桁数/開始番号
        self.text_ctrl_prefix.SetValue(prop['prefix'])
        self.spin_ctrl_sequence_digits.SetValue(prop['sequence_digits'])
        self.spin_ctrl_sequence_begin.SetValue(prop['sequence_begin'])
        #--- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        self.checkbox_capture_mcursor.SetValue(prop['capture_mcursor'])
        self.checkbox_sound_on_capture.SetValue(prop['sound_on_capture'])
        # 遅延キャプチャー
        self.checkbox_delayed_capture.SetValue(prop['delayed_capture'])
        self.spin_ctrl_delayed_time.SetValue(prop['delayed_time'])
        # トリミング
        self.checkbox_trimming.SetValue(prop['trimming'])
        self.spin_ctrl_trimming_top.SetValue(prop['trimming_size'][0])
        self.spin_ctrl_trimming_bottom.SetValue(prop['trimming_size'][1])
        self.spin_ctrl_trimming_left.SetValue(prop['trimming_size'][2])
        self.spin_ctrl_trimming_right.SetValue(prop['trimming_size'][3])
        # ホット・キー
        if prop['hotkey_clipboard'] == 0:
            self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(True)
            self.radio_btn_hotkey_png_ctrl_shift.SetValue(True)
        else:
            self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(True)
            self.radio_btn_hotkey_png_ctrl_alt.SetValue(True)
        # ターゲット
        self.choice_hotkey_active_window.Select(prop['hotkey_activewin'])

    def get_prop(self, prop: dict):
        """設定値をプロパティに反映する
        """
        #--- 基本設定
        # 自動/手動
        prop['auto_save'] = self.radio_btn_auto_save.GetValue()
        # 自動保存フォルダ
        prop['save_folders'].clear()
        for folder in self.list_box_auto_save_folders.Items:
            prop['save_folders'].append(folder)
        prop['save_folder_index'] = self.list_box_auto_save_folders.GetSelection()
        # ナンバリング
        if self.radio_btn_numbering_datetime.GetValue():
            prop['numbering'] = 0
        else:
            prop['numbering'] = 1
        # 接頭語/シーケンス桁数/開始番号
        prop['prefix'] = self.text_ctrl_prefix.GetValue()
        prop['sequence_digits'] = self.spin_ctrl_sequence_digits.GetValue()
        prop['sequence_begin']  = self.spin_ctrl_sequence_begin.GetValue()
        #--- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        prop['capture_mcursor']  = self.checkbox_capture_mcursor.GetValue()
        prop['sound_on_capture'] = self.checkbox_sound_on_capture.GetValue()
        # 遅延キャプチャー
        prop['delayed_capture'] = self.checkbox_delayed_capture.GetValue()
        prop['delayed_time']    = self.spin_ctrl_delayed_time.GetValue()
        # トリミング
        prop['trimming'] = self.checkbox_trimming.GetValue()
        prop['trimming_size'] = [
            self.spin_ctrl_trimming_top.GetValue(),
            self.spin_ctrl_trimming_bottom.GetValue(),
            self.spin_ctrl_trimming_left.GetValue(),
            self.spin_ctrl_trimming_right.GetValue()
        ]
        # ホット・キー
        if self.radio_btn_hotkey_bmp_ctrl_alt.GetValue():
            prop['hotkey_clipboard'] = 0
            prop['hotkey_imagefile'] = 1
        else:
            prop['hotkey_clipboard'] = 1
            prop['hotkey_imagefile'] = 0
        # ターゲット
        prop['hotkey_activewin'] = self.choice_hotkey_active_window.GetSelection()

# end of class SettingsDialog


class PeriodicDialog(wx.Dialog):
    """定期実行設定ダイアログ（wxGladeで、設計&生成）
    """
    def __init__(self, *args, **kwds):
        # begin wxGlade: PeriodicDialog.__init__
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        wx.Dialog.__init__(self, *args, **kwds)
        self.SetSize((400, 240))
        self.SetTitle(u"定期実行設定")

        sizer_1 = wx.BoxSizer(wx.VERTICAL)

        sizer_3 = wx.BoxSizer(wx.VERTICAL)
        sizer_1.Add(sizer_3, 1, wx.ALL | wx.EXPAND, 2)

        sizer_4 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3.Add(sizer_4, 0, wx.ALL | wx.EXPAND, 4)

        label_1 = wx.StaticText(self, wx.ID_ANY, u"保存先: ")
        sizer_4.Add(label_1, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        self.text_ctrl_periodic_folder = wx.TextCtrl(self, wx.ID_ANY, "")
        sizer_4.Add(self.text_ctrl_periodic_folder, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        self.button_periodic_folder_brows = wx.Button(self, wx.ID_ANY, "...")
        self.button_periodic_folder_brows.SetMinSize((25, 23))
        sizer_4.Add(self.button_periodic_folder_brows, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        sizer_5 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3.Add(sizer_5, 0, wx.ALL | wx.EXPAND, 4)

        label_2 = wx.StaticText(self, wx.ID_ANY, u"間　隔: ")
        sizer_5.Add(label_2, 0, wx.ALIGN_CENTER_VERTICAL, 4)

        self.spin_ctrl_periodic_interval = wx.SpinCtrl(self, wx.ID_ANY, "1", min=1, max=3600, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
        sizer_5.Add(self.spin_ctrl_periodic_interval, 0, wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 4)

        label_3 = wx.StaticText(self, wx.ID_ANY, u"秒")
        sizer_5.Add(label_3, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)

        label_4 = wx.StaticText(self, wx.ID_ANY, u"終了キー: ")
        sizer_5.Add(label_4, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 24)

        self.choice_periodic_stopkey_modifire = wx.Choice(self, wx.ID_ANY, choices=["none", "Shift", "Ctrl", "Alt"])
        self.choice_periodic_stopkey_modifire.SetSelection(0)
        sizer_5.Add(self.choice_periodic_stopkey_modifire, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        label_6 = wx.StaticText(self, wx.ID_ANY, "+")
        sizer_5.Add(label_6, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)

        self.choice_periodic_stop_fkey = wx.Choice(self, wx.ID_ANY, choices=["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"])
        self.choice_periodic_stop_fkey.SetSelection(10)
        sizer_5.Add(self.choice_periodic_stop_fkey, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_6 = wx.BoxSizer(wx.HORIZONTAL)
        sizer_3.Add(sizer_6, 1, wx.ALL | wx.EXPAND, 4)

        sizer_7 = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, u"対象"), wx.VERTICAL)
        sizer_6.Add(sizer_7, 0, wx.EXPAND, 0)

        self.choice_periodic_capture_target = wx.Choice(sizer_7.GetStaticBox(), wx.ID_ANY, choices=[u"デスクトップ", u"アクティブウィンドウ"])
        self.choice_periodic_capture_target.SetSelection(0)
        sizer_7.Add(self.choice_periodic_capture_target, 0, wx.ALL, 4)

        sizer_8 = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, u"ナンバリング"), wx.VERTICAL)
        sizer_6.Add(sizer_8, 0, wx.EXPAND | wx.LEFT, 4)

        self.radio_btn_periodic_numbering_datetime = wx.RadioButton(sizer_8.GetStaticBox(), wx.ID_ANY, u"日時 (yyyymmdd_hhmmss)")
        self.radio_btn_periodic_numbering_datetime.SetValue(1)
        sizer_8.Add(self.radio_btn_periodic_numbering_datetime, 0, wx.ALL, 4)

        self.radio_btn_periodic_numbering_autosave = wx.RadioButton(sizer_8.GetStaticBox(), wx.ID_ANY, u"自動保存の設定に従う")
        sizer_8.Add(self.radio_btn_periodic_numbering_autosave, 0, wx.ALL, 4)

        sizer_9 = wx.BoxSizer(wx.VERTICAL)
        sizer_6.Add(sizer_9, 1, wx.EXPAND, 0)

        self.button_periodic_start = wx.Button(self, wx.ID_OK, u"開始")
        self.button_periodic_start.Enable(False)
        sizer_9.Add(self.button_periodic_start, 1, wx.ALL | wx.EXPAND, 4)

        self.button_periodic_stop = wx.Button(self, wx.ID_STOP, u"終了")
        self.button_periodic_stop.Enable(False)
        sizer_9.Add(self.button_periodic_stop, 0, wx.ALL | wx.EXPAND, 4)

        sizer_2 = wx.StdDialogButtonSizer()
        sizer_1.Add(sizer_2, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

        self.button_CANCEL = wx.Button(self, wx.ID_CANCEL, "")
        sizer_2.AddButton(self.button_CANCEL)

        sizer_2.Realize()

        self.SetSizer(sizer_1)

        self.SetAffirmativeId(self.button_periodic_start.GetId())
        self.SetEscapeId(self.button_CANCEL.GetId())

        self.Layout()
        self.Centre()

        self.button_periodic_stop.Bind(wx.EVT_BUTTON, self.on_periodic_capture_stop)
        # end wxGlade

    def on_save_folder_browse(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        """保存フォルダの選択
        """
        defaultPath = os.getcwd()
        agwstyle = MDD.DD_MULTIPLE|MDD.DD_DIR_MUST_EXIST
        with MDD.MultiDirDialog(None, title="フォルダの選択", defaultPath=defaultPath, agwStyle=agwstyle) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            paths = dlg.GetPaths()
            for folder in paths:
                self.text_ctrl_periodic_folder.SetValue(folder)
                print(f'Set {folder}')
        event.Skip()

    def on_periodic_capture_stop(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        print("Event handler 'on_periodic_capture_stop'")
        self.EndModal(event.GetId())
        event.Skip()

    def set_prop(self, prop: dict):
        """設定値をコントロールに反映する
        """
        # 保存フォルダ
        self.text_ctrl_periodic_folder.SetValue(prop['periodic_save_folder'])
        # 間隔
        self.spin_ctrl_periodic_interval.SetValue(prop['periodic_interval'])
        # 停止キー（修飾キー）
        self.choice_periodic_stopkey_modifire.Select(prop['periodic_stop_modifier'])
        self.choice_periodic_stop_fkey.Select(prop['periodic_stop_fkey'])
        # ターゲット
        for i in range(prop['display']):
            item = f'ディスプレイ {i + 1}'
            self.choice_periodic_capture_target.Insert(item, self.choice_periodic_capture_target.GetCount() - 1)
        if prop['periodic_target'] == -1:
            self.choice_periodic_capture_target.Select(self.choice_periodic_capture_target.GetCount() - 1)
        else:
            self.choice_periodic_capture_target.Select(prop['periodic_target'])
        # ナンバリング
        if prop['periodic_numbering'] == 0:
            self.radio_btn_periodic_numbering_datetime.SetValue(True)
        else:
            self.radio_btn_periodic_numbering_autosave.SetValue(True)

    def get_prop(self, prop: dict):
        """設定値をプロパティに反映する
        """
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not prop['periodic_capture'])
        self.button_periodic_stop.Enable(prop['periodic_capture'])
        # 保存フォルダ
        prop['periodic_save_folder'] = self.text_ctrl_periodic_folder.GetValue()
        # 間隔
        prop['periodic_interval'] = self.spin_ctrl_periodic_interval.GetValue()
        # 停止キー（修飾キー）
        prop['periodic_stop_modifier'] = self.choice_periodic_stopkey_modifire.GetSelection()
        prop['periodic_stop_fkey']     = self.choice_periodic_stop_fkey.GetSelection()
        # ターゲット
        index = self.choice_periodic_capture_target.Selection()
        if index == (self.choice_periodic_capture_target.GetCount() - 1):
            prop['periodic_target'] = -1
        else:
            prop['periodic_target'] = index
        # ナンバリング
        if self.radio_btn_periodic_numbering_datetime.GetValue():
            prop['periodic_numbering'] = 0
        else:
            prop['periodic_numbering'] = 1

# end of class PeriodicDialog


class MyScreenShot(TaskBarIcon):
    """Menu IDs"""
    # Help
    ID_MENU_HELP  = 901         # ヘルプを表示
    ID_MENU_ABOUT = 902         # バージョン情報
    # 環境設定
    ID_MENU_SETTINGS = 101
    # クイック設定
    ID_MENU_MCURSOR  = 102      # マウスカーソルキャプチャーを有効
    ID_MENU_DELAYED  = 103      # 遅延キャプチャーを有効
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
    """ Hotkey Modifiers """
    HK_MOD_SHIFT      = 'Shift'
    HK_MOD_CTRL       = 'Ctrl'
    HK_MOD_ALT        = 'Alt'
    HK_MOD_CTRL_ALT   = f'{HK_MOD_CTRL}+{HK_MOD_ALT}'
    HK_MOD_CTRL_SHIFT = f'{HK_MOD_CTRL}+{HK_MOD_SHIFT}'
    HK_MOD_SHIFT_ALT  = f'{HK_MOD_SHIFT}+{HK_MOD_ALT}'

    def __init__(self, frame):
        self.frame = frame
        super(MyScreenShot, self).__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # プロパティ
        self.prop: dict = {
            'display': 1,
            'auto_save': True,
            'save_folders': [],
            'save_folder_index': -1,
            'numbering': 0,
            'prefix': '',
            'sequence_digits': 0,
            'sequence_begin': 0,
            'capture_mcursor': False,
            'sound_on_capture': False,
            'delayed_capture': False,
            'delayed_time': 0,
            'trimming': False,
            'trimming_size': [0,0,0,0],
            'hotkey_clipboard': 0,
            'hotkey_imagefile': 1,
            'hotkey_activewin': 8,
            'periodic_capture': False,
            'periodic_save_folder': '',
            'periodic_interval': 0,
            'periodic_stop_modifier': 0,
            'periodic_stop_fkey': 0,
            'periodic_target': 0,
            'periodic_numbering': 0
        }
        self.capture_hotkey = [MyScreenShot.HK_MOD_CTRL_ALT, MyScreenShot.HK_MOD_CTRL_SHIFT]
        # キャプチャーHotkeyアクセレーターリスト（0:デスクトップ、1～:ディスプレイ、last:アクティブウィンドウ）
        self.hotkey_clipboard = []
        self.hotkey_imagefile = []
        self.ss_queue = queue.Queue()
        # 初期処理
        self.initialize()

    def CreatePopupMenu(self):
        """Popupメニューの生成 (override)
        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。
        """
        # ディスプレイ数
        self.prop['display'] = len(get_monitors())
        display_count = self.prop['display']
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
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_MCURSOR, 'マウスカーソルキャプチャーを有効', self.on_menu_toggle_mouse_capture, kind = wx.ITEM_CHECK)
        sub_item.Enable(False)  # Windowsでは現状マウスカーソルがキャプチャー出来ないので「無効」にしておく
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_DELAYED, '遅延キャプチャーを有効', self.on_menu_toggle_delayed_capture, kind = wx.ITEM_CHECK)
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
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN0_CB, f'0: デスクトップ\t{self.hotkey_clipboard}+0', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN0, f'0: デスクトップ\t{self.hotkey_imagefile}+0', self.on_menu_imagefile)
        for n in range(display_count):
            create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN1_CB + n, f'{n + 1}: ディスプレイ {n + 1}\t{self.hotkey_clipboard}+{n + 1}', self.on_menu_clipboard)
            create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN1 + n, f'{n + 1}: ディスプレイ {n + 1}\t{self.hotkey_imagefile}+{n + 1}', self.on_menu_imagefile)
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_ACTIVE_CB, f'{display_count + 1}: アクティブウィンドウ\t{self.hotkey_clipboard}+{self.hotkey_activewin}', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_ACTIVE, f'{display_count + 1}: アクティブウィンドウ\t{self.hotkey_imagefile}+{self.hotkey_activewin}', self.on_menu_imagefile)
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
        # キャプチャーHotkeyアクセレーター展開 & Hotkey設定
        self.set_capture_hotkey(first=True)

    def set_capture_hotkey(self, first: bool=False):
        """キャプチャーHotkeyのメニューアクセレーターを展開する & Hotkey設定
        """
        if not first:
            # 現在のHotkeyを削除
            for hotkey in self.hotkey_clipboard:
                keyboard.remove_hotkey(hotkey)
            for hotkey in self.hotkey_imagefile:
                keyboard.remove_hotkey(hotkey)

        # 新しいアクセレーターを展開
        hk_clipbd = self.capture_hotkey[self.prop['hotkey_clipboard']]
        hk_imagef = self.capture_hotkey[self.prop['hotkey_imagefile']]
        # デスクトップ[0]
        self.hotkey_clipboard = [f'{hk_clipbd}+0']
        self.hotkey_imagefile = [f'{hk_imagef}+0']
        # ディスプレイ[1～]
        for n in range(self.prop['display']):
            self.hotkey_clipboard.append(f'{hk_clipbd}+{n + 1}')
            self.hotkey_imagefile.append(f'{hk_imagef}+{n + 1}')
        # アクティブウィンドウ
        self.hotkey_clipboard.append(f'{hk_clipbd}+F{self.prop['hotkey_activewin'] + 1}')
        self.hotkey_imagefile.append(f'{hk_clipbd}+F{self.prop['hotkey_activewin'] + 1}')
        # Hotkeyの登録
        keyboard.add_hotkey(self.hotkey_clipboard[0],
                            lambda: wx.CallAfter(self.on_menu_clipboard, wx.Event(MyScreenShot.ID_MENU_SCREEN0_CB)))
        keyboard.add_hotkey(self.hotkey_imagefile[0],
                            lambda: wx.CallAfter(self.on_menu_imagefile, wx.Event(MyScreenShot.ID_MENU_SCREEN0)))
        for n in range(self.prop['display']):
            keyboard.add_hotkey(self.hotkey_clipboard[n],
                                lambda: wx.CallAfter(self.on_menu_clipboard, wx.Event(MyScreenShot.ID_MENU_SCREEN0_CB + n)))
            keyboard.add_hotkey(self.hotkey_imagefile[n],
                                lambda: wx.CallAfter(self.on_menu_clipboard, wx.Event(MyScreenShot.ID_MENU_SCREEN0 + n)))
        keyboard.add_hotkey(self.hotkey_clipboard[self.prop['display'] + 1],
                            lambda: wx.CallAfter(self.on_menu_clipboard, wx.Event(MyScreenShot.ID_MENU_ACTIVE_CB)))
        keyboard.add_hotkey(self.hotkey_imagefile[self.prop['display'] + 1],
                            lambda: wx.CallAfter(self.on_menu_imagefile, wx.Event(MyScreenShot.ID_MENU_ACTIVE)))

    def config_to_property(self):
        """設定値をプロパティに展開する
        """
        # ディスプレイ数
        self.prop['display'] = len(get_monitors())
        # 自動保存
        self.prop['auto_save'] = self.config.getboolean('basic','auto_save', fallback=True)
        # 自動保存フォルダ
        self.prop['save_folder_index'] = self.config.getint('basic', 'save_folder_index', fallback=-1)
        for n in range(_MAX_SAVE_FOLDERS):
            option_name: str = 'folder' + str(n + 1)
            if not self.config.has_option('basic', option_name):
                break
            option: str = self.config.get('basic', option_name)
            self.prop['save_folders'].append(option)

        if len(self.prop['save_folders']) > 0:
            if self.prop['save_folder_index'] < 0 or self.prop['save_folder_index'] >= len(self.prop['save_folders']):
                self.prop['save_folder_index'] = 0
        else:
            # 自動保存フォルダが無いので、'Pictures'を登録する
            pict_folder = os.path.join(os.path.expanduser('~'), 'Pictures')
            self.prop['auto_save_folders'].append(pict_folder)
            self.prop['save_folder_index'] = 0
        # 自動保存時のナンバリング
        self.prop['numbering']        = self.config.getint('basic', 'numbering', fallback=0)
        self.prop['prefix']           = self.config.get('basic', 'prefix', fallback='SS')
        self.prop['sequence_digits']  = self.config.getint('basic', 'sequence_digits', fallback=6)
        self.prop['sequence_begin']   = self.config.getint('basic', 'sequence_begin', fallback=0)
        self.prop['capture_mcursor']  = self.config.getboolean('other', 'mouse_cursor', fallback=False)
        self.prop['sound_on_capture'] = self.config.getboolean('other', 'sound_on_capture', fallback=False)
        self.prop['delayed_capture']  = self.config.getboolean('delayed_capture', 'delayed_capture', fallback=False)
        self.prop['delayed_time']     = self.config.getint('delayed_capture', 'delayed_time', fallback=5)
        # トリミング
        self.prop['trimming'] = self.config.getboolean('trimming', 'trimming', fallback=False)
        top: int    = self.config.getint('trimming', 'top', fallback=0)
        bottom: int = self.config.getint('trimming', 'bottom', fallback=0)
        left: int   = self.config.getint('trimming', 'left', fallback=0)
        right: int  = self.config.getint('trimming', 'right', fallback=0)
        self.prop['trimming_size'] = [top, bottom, left, right]
        # ホット・キー
        self.prop['hotkey_clipboard'] = self.config.getint('hotkey', 'clipboard', fallback=0)
        self.prop['hotkey_imagefile'] = self.config.getint('hotkey', 'imagefile', fallback=1)
        self.prop['hotkey_activewin'] = self.config.getint('hotkey', 'activewin', fallback=8)
        # 定期実行
        self.prop['periodic_save_folder']   = self.config.get('periodic', 'save_folder', fallback='')
        self.prop['periodic_interval']      = self.config.getint('periodic', 'interval', fallback=3)
        self.prop['periodic_stop_modifier'] = self.config.getint('periodic', 'stop_modifier', fallback=0)
        self.prop['periodic_stop_fkey']     = self.config.getint('periodic', 'stop_fkey', fallback=10)
        self.prop['periodic_target']        = self.config.getint('periodic', 'target', fallback=0)
        self.prop['periodic_numbering']     = self.config.getint('periodic', 'numbering', fallback=0)

    def property_to_config(self):
        """プロパティを設定値に展開する
        """
        # 自動保存
        self.config.set('basic','auto_save', str(self.prop['auto_save']))
        # 自動保存フォルダ
        self.config.set('basic', 'save_folder_index', str(self.prop['save_folder_index']))
        for n, folder_name in enumerate(self.prop['save_folders']):
            option_name: str = 'folder' + str(n + 1)
            self.config.set('basic', option_name, folder_name)
        # 自動保存時のナンバリング
        self.config.set('basic', 'numbering', str(self.prop['numbering']))
        self.config.set('basic', 'prefix', self.prop['prefix'])
        self.config.set('basic', 'sequence_digits', str(self.prop['sequence_digits']))
        self.config.set('basic', 'sequence_begin', str(self.prop['sequence_begin']))
        self.config.set('other', 'mouse_cursor', str(self.prop['capture_mcursor']))
        self.config.set('other', 'sound_on_capture', str(self.prop['sound_on_capture']))
        self.config.set('delayed_capture', 'delayed_capture', str(self.prop['delayed_capture']))
        self.config.set('delayed_capture', 'delayed_time', str(self.prop['delayed_time']))
        # トリミング
        self.config.set('trimming', 'trimming', str(self.prop['trimming']))
        self.config.set('trimming', 'top', str(self.prop['trimming_size'][0]))
        self.config.set('trimming', 'bottom', str(self.prop['trimming_size'][1]))
        self.config.set('trimming', 'left', str(self.prop['trimming_size'][2]))
        self.config.set('trimming', 'right', str(self.prop['trimming_size'][3]))
        # ホット・キー
        self.config.set('hotkey', 'clipboard', str(self.prop['hotkey_clipboard']))
        self.config.set('hotkey', 'imagefile', str(self.prop['hotkey_imagefile']))
        self.config.set('hotkey', 'activewin', str(self.prop['hotkey_activewin']))
        # 定期実行
        self.config.set('periodic', 'save_folder', self.prop['periodic_save_folder'])
        self.config.set('periodic', 'interval', str(self.prop['periodic_interval']))
        self.config.set('periodic', 'stop_modifier', str(self.prop['periodic_stop_modifier']))
        self.config.set('periodic', 'stop_fkey', str(self.prop['periodic_stop_fkey']))
        self.config.set('periodic', 'target', str(self.prop['periodic_target']))
        self.config.set('periodic', 'numbering', str(self.prop['periodic_numbering']))

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

        self.config_to_property()

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

        self.property_to_config()
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
        * 環境の設定ダイヤログを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        with SettingsDialog(self.frame, wx.ID_ANY, "") as dlg:
            # 設定値をダイアログ側へ渡す
            dlg.set_prop(self.prop)
            if dlg.ShowModal() == wx.ID_OK:
                print("on_menu_settings closed 'OK'")
                dlg.get_prop(self.prop)
                # print(self.prop)
                # キャプチャーHotkeyアクセレーター展開
                self.set_capture_hotkey()

    def on_menu_toggle_mouse_capture(self, event):
        """Mouse captureメニューイベントハンドラ
        * マウスカーソルのキャプチャーを有効/無効にする。
          ※現在の所、Windowsではキャプチャー出来ない
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.prop['capture_mcursor'] = not self.prop['capture_mcursor']
        print(f"on_menu_toggle_mouse_capture ({self.prop['capture_mcursor']})")

    def on_menu_toggle_delayed_capture(self, event):
        """Delayed captureメニューイベントハンドラ
        * 遅延キャプチャーを有効/無効にする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.prop['delayed_capture'] = not self.prop['delayed_capture']
        print(f"on_menu_toggle_delayed_capture ({self.prop['delayed_capture']})")

    def on_menu_toggle_trimming(self, event):
        """Trimmingメニューイベントハンドラ
        * トリミングを有効/無効にする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.prop['trimming'] = not self.prop['trimming']
        print(f"on_menu_toggle_trimming ({self.prop['trimming']})")

    def on_menu_select_save_folder(self, event):
        """Select save folderメニューイベントハンドラ
        * 自動保存フォルダーを切り替える。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        index1 = self.prop['save_folder_index']
        index2 = index1
        id = event.GetId()
        for n in range(self.prop['save_folders']):
            if id == (MyScreenShot.ID_MENU_FOLDER1 + n):
                index2 = n
                self.prop['save_folder_index'] = n
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
        """Periodic settingsメニューイベントハンドラ
        * 定期実行設定ダイヤログを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        with PeriodicDialog(self.frame, wx.ID_ANY, "") as dlg:
            # 設定値をダイアログ側へ渡す
            dlg.set_prop(self.prop)
            id = dlg.ShowModal()
            if id == wx.ID_OK:
                print("on_menu_periodic_settings closed 'Start(OK)'")
                dlg.get_prop(self.prop)
                self.prop['periodic_capture'] = True
                # print(self.prop)
                # キャプチャーHotkeyアクセレーター展開
                self.hotkey_clipboard = self.capture_hotkey[self.prop['hotkey_clipboard']]
                self.hotkey_imagefile = self.capture_hotkey[self.prop['hotkey_imagefile']]
                self.hotkey_activewin = f'F{self.prop['hotkey_activewin'] + 1}'
            elif id == wx.ID_STOP:
                self.prop['periodic_capture'] = False

    def capture_callback(self, menu_id, moni_no: int, clipboard: bool, filname: str):
        """
        """
        wx.CallAfter(self.on_menu_clipboard, wx.Event(menu_id))

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
        moni_no: int = -1
        if id == MyScreenShot.ID_MENU_ACTIVE_CB:
            moni_no = 90
        else:
            moni_no = id - MyScreenShot.ID_MENU_SCREEN0_CB

        self.ss_queue.put({'moni_no': moni_no, 'clipboard': True, 'filename': ''})
        print(f'on_menu_clipboard ({id})')
        delay_ms: int = _BASE_DELAY_TIME
        if self.prop['delayed_capture']:
            delay_ms = self.prop['delayed_time'] * 1000
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
        print('on_menu_exit')
        self.save_config()

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
