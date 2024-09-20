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
from datetime import datetime
from functools import partial
import io
import keyboard
import mss
import mss.tools
import os
from PIL import Image
from queue import Queue
from screeninfo import get_monitors
import sys
from typing import Union
import win32clipboard
import win32gui

import wx
from wx.adv import TaskBarIcon, EVT_TASKBAR_LEFT_DCLICK, Sound, AboutBox, AboutDialogInfo
import wx.lib.agw.multidirdialog as MDD

import mydefine as mydef
from myutils import get_running_path, platform_info, get_special_directory, scan_directory
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
# マイピクチャパス
_MY_PICTURE = ''

_TRAY_TOOLTIP = _app_name_ + ' App'
#_TRAY_ICON = 'ScreenShot.ico'

_MAX_SAVE_FOLDERS = 16
_BASE_DELAY_TIME = 400  # (ms)
_NO_CONSOLE = False

_debug_mode = False
_disable_hotkeys = False

def _debug_print(message: str):
    global debug_mode
    if not _NO_CONSOLE and _debug_mode:
        ts = datetime.now().strftime('%Y/%m/%d %H%M%S.%f')[:-3]
        sys.stdout.write(f'{ts} [debug]:{message}\n')


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
    if (hwnd := win32gui.FindWindow(None, window_title)) == 0:
        return None

    # win32gui.SetForegroundWindow(hwnd)
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
    INFO = 0
    SETTINGS         = auto()
    QUICK_SETTINGS   = auto()
    AUTO_SAVE_FOLDER = auto()
    OPEN_FOLDER      = auto()
    PERIODIC         = auto()
    COPY_TO_CB       = auto()
    SAVE_TO_PNG      = auto()
    EXIT = auto()


class MyScreenShot(TaskBarIcon):
    """Menu IDs"""
    # バージョン情報
    ID_MENU_HELP  = 901         # ヘルプを表示
    ID_MENU_ABOUT = 902         # バージョン情報
    # 環境設定
    ID_MENU_SETTINGS = 101
    # クイック設定
    ID_MENU_MCURSOR  = 102      # マウスカーソルキャプチャーを有効
    ID_MENU_SOUND    = 103      # キャプチャー終了時に音を鳴らす
    ID_MENU_DELAYED  = 104      # 遅延キャプチャーを有効
    ID_MENU_TRIMMING = 105      # トリミングを有効
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
    HK_MOD_NONE       = ''
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
            'delayed_time_ms': 0,
            'trimming': False,
            'trimming_size': [0,0,0,0],
            'hotkey_clipboard': 0,
            'hotkey_imagefile': 1,
            'hotkey_activewin': 8,
            'periodic_capture': False,
            'periodic_save_folder': '',
            'periodic_interval': 0,
            'periodic_interval_ms': 0,
            'periodic_stop_modifier': 0,
            'periodic_stop_fkey': 0,
            'periodic_target': 0,
            'periodic_numbering': 0
        }
        self.capture_hotkey_tbl = (MyScreenShot.HK_MOD_CTRL_ALT, MyScreenShot.HK_MOD_CTRL_SHIFT)
        # キャプチャーHotkeyアクセレーターリスト（0:デスクトップ、1～:ディスプレイ、last:アクティブウィンドウ）
        self.hotkey_clipboard: list = []
        self.hotkey_imagefile: list = []
        # 定期実行停止Hotkey
        self.periodic_stop_hotkey_tbl = (MyScreenShot.HK_MOD_NONE, MyScreenShot.HK_MOD_SHIFT, MyScreenShot.HK_MOD_CTRL, MyScreenShot.HK_MOD_ALT)
        self.hotkey_periodic_stop: str = ''
        # シーケンス番号保持用
        self.sequence: int = -1
        # キャプチャー要求Queue
        self.req_queue: Queue = Queue()
        # 初期処理
        self.initialize()

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
        # ディスプレイ数取得
        self.prop['display'] = len(get_monitors())
        # Load Application ICON
        self._app_icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)
        self.SetIcon(self._app_icons.GetIcon(wx.Size(16, 16)), _TRAY_TOOLTIP)
        # 設定値の初期設定と設定ファイルの読み込み
        self.load_config()
        # メニューアイコン画像の展開
        w, h = menu_image.image_size
        self._icon_img = wx.ImageList(w, h)
        for name in menu_image.index:
            self._icon_img.Add(menu_image.catalog[name].GetBitmap())
        # BEEP音
        self._beep = Sound()
        self._beep.CreateFromData(sound.get_snd_beep_bytearray())
        self._success = Sound()
        self._success.CreateFromData(sound.get_snd_success_bytearray())
        # キャプチャーHotkeyアクセレーター展開、設定
        self.set_capture_hotkey(first=True)
        # 定期実行停止用Hotkey展開、設定
        self.set_periodic_stop_hotkey(True)

    def set_capture_hotkey(self, first: bool=False):
        """キャプチャー用ホット・キー登録処理
        * キャプチャー用ホット・キーとメニューのアクセレーター文字列を展開する
        * キャプチャー用ホット・キーを登録する
        Args:
            first (bool): 初回フラグ（初回はホット・キー削除なし）
        Returns:
            none
        """
        global _disable_hotkeys
        if _disable_hotkeys:
            return

        if not first:
            # 現在のHotkeyを削除
            for hotkey in self.hotkey_clipboard:
                keyboard.remove_hotkey(hotkey)
            for hotkey in self.hotkey_imagefile:
                keyboard.remove_hotkey(hotkey)

        self.hotkey_clipboard.clear()
        self.hotkey_imagefile.clear()
        # 設定値(prop)からキャプチャー用の修飾キーを取得し、それぞれのホット・キー文字列を展開する
        hk_clipbd: str = self.capture_hotkey_tbl[self.prop['hotkey_clipboard']]
        hk_imagef: str = self.capture_hotkey_tbl[self.prop['hotkey_imagefile']]
        # デスクトップ[0]
        disp: int = 0
        self.hotkey_clipboard.append(f'{hk_clipbd}+{disp}')
        self.hotkey_imagefile.append(f'{hk_imagef}+{disp}')
        # ディスプレイ[1～]
        for n in range(self.prop['display']):
            disp += 1
            self.hotkey_clipboard.append(f'{hk_clipbd}+{disp}')
            self.hotkey_imagefile.append(f'{hk_imagef}+{disp}')
        # アクティブウィンドウ
        self.hotkey_clipboard.append(f'{hk_clipbd}+F{self.prop['hotkey_activewin'] + 1}')
        self.hotkey_imagefile.append(f'{hk_imagef}+F{self.prop['hotkey_activewin'] + 1}')
        # Hotkeyの登録
        # _debug_print(f'Hotkey[0]={self.hotkey_clipboard[0]}, {self.hotkey_imagefile[0]}, id={MyScreenShot.ID_MENU_SCREEN0_CB}, {MyScreenShot.ID_MENU_SCREEN0}')
        keyboard.add_hotkey(self.hotkey_clipboard[0], lambda: wx.CallAfter(self.copy_to_clipboard, MyScreenShot.ID_MENU_SCREEN0_CB))
        keyboard.add_hotkey(self.hotkey_imagefile[0], lambda: wx.CallAfter(self.save_to_imagefile, MyScreenShot.ID_MENU_SCREEN0))
        disp = 0
        for n in range(self.prop['display']):
            disp += 1
            # _debug_print(f'Hotkey[{disp}]={self.hotkey_clipboard[disp]}, {self.hotkey_imagefile[disp]}, n={n}, id={MyScreenShot.ID_MENU_SCREEN1_CB + n}, {MyScreenShot.ID_MENU_SCREEN1 + n}')
            keyboard.add_hotkey(self.hotkey_clipboard[disp], lambda: wx.CallAfter(self.copy_to_clipboard, MyScreenShot.ID_MENU_SCREEN1_CB + n))
            keyboard.add_hotkey(self.hotkey_imagefile[disp], lambda: wx.CallAfter(self.save_to_imagefile, MyScreenShot.ID_MENU_SCREEN1 + n))
        disp += 1
        # _debug_print(f'Hotkey[{disp}]={self.hotkey_clipboard[disp]}, {self.hotkey_imagefile[disp]}, id={MyScreenShot.ID_MENU_ACTIVE_CB}, {MyScreenShot.ID_MENU_ACTIVE}')
        keyboard.add_hotkey(self.hotkey_clipboard[disp], lambda: wx.CallAfter(self.copy_to_clipboard, MyScreenShot.ID_MENU_ACTIVE_CB))
        keyboard.add_hotkey(self.hotkey_imagefile[disp], lambda: wx.CallAfter(self.save_to_imagefile, MyScreenShot.ID_MENU_ACTIVE))

    def set_periodic_stop_hotkey(self, first: bool):
        """定期実行停止ホット・キー登録処理
        Args:
            first (bool): 初回フラグ（初回はホット・キー削除なし）
        Returns:
            none
        """
        global _disable_hotkeys
        if _disable_hotkeys:
            return

        if not first:
            # 現在のHotkeyを削除
            keyboard.remove_hotkey(self.hotkey_periodic_stop)

        # 設定値(prop)からホット・キー文字列を展開する
        modifire = self.periodic_stop_hotkey_tbl[self.prop['periodic_stop_modifier']]
        fkey = f'F{self.prop['periodic_stop_fkey'] + 1}'
        self.hotkey_periodic_stop = fkey if len(modifire) == 0 else f'{modifire}+{fkey}'
        keyboard.add_hotkey(self.hotkey_periodic_stop, lambda: wx.CallAfter(self.stop_periodic_capture))

    def load_config(self):
        """設定値読み込み処理
        * 各種設定値を初期設定後、設定ファイルから読み込む。
        Args:
            none
        Returns:
            none
        """
        global _CONFIG_FILE

        self.config = configparser.ConfigParser()
        result: bool = False
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as fc:
                self.config.read_file(fc)
            result = True
        except OSError as e:
            wx.MessageBox(f'Configration file load failed.\n ({e})\n Use default settings.', 'ERROR', wx.ICON_ERROR)
        except configparser.Error as e:
            wx.MessageBox(f'Configration file parse failed.\n ({e})', 'ERROR', wx.ICON_ERROR)

        if not result:
            self.config.read_dict(mydef._CONFIG_DEFAULT)

        if self.config_to_property():
            self.save_config()

    def save_config(self):
        """設定値保存処理
        * 各種設定値をファイルの書き込む。
        Args:
            none
        Returns:
            none
        """
        global _CONFIG_FILE

        self.property_to_config()
        try:
            with open(_CONFIG_FILE, 'w') as fc:
                self.config.write(fc)

        except OSError as e:
            wx.MessageBox(f'Configration file save failed.\n ({e})', 'ERROR', wx.ICON_ERROR)

    def config_to_property(self) -> bool:
        """設定値展開処理
        * 設定値をプロパティに展開する
        Args:
            none
        Returns:
            none
        """
        global _MY_PICTURE
        save_req: bool = False
        # 自動保存
        self.prop['auto_save'] = self.config.getboolean('basic','auto_save', fallback=True)
        # 自動保存フォルダ
        self.prop['save_folder_index'] = self.config.getint('basic', 'save_folder_index', fallback=-1)
        for n in range(_MAX_SAVE_FOLDERS):
            option_name: str = f'folder{n}'
            if not self.config.has_option('basic', option_name):
                break
            option: str = self.config.get('basic', option_name)
            self.prop['save_folders'].append(option)

        if len(self.prop['save_folders']) > 0:
            if self.prop['save_folder_index'] < 0 or self.prop['save_folder_index'] >= len(self.prop['save_folders']):
                self.prop['save_folder_index'] = 0
                save_req = True
        else:
            # 自動保存フォルダが無いので、'Pictures'を登録する
            self.prop['save_folders'].append(_MY_PICTURE)
            self.prop['save_folder_index'] = 0
            save_req = True
        # 自動保存時のナンバリング
        self.prop['numbering']        = self.config.getint('basic', 'numbering', fallback=0)
        self.prop['prefix']           = self.config.get('basic', 'prefix', fallback='SS')
        self.prop['sequence_digits']  = self.config.getint('basic', 'sequence_digits', fallback=6)
        self.prop['sequence_begin']   = self.config.getint('basic', 'sequence_begin', fallback=0)
        self.prop['capture_mcursor']  = self.config.getboolean('other', 'mouse_cursor', fallback=False)
        self.prop['sound_on_capture'] = self.config.getboolean('other', 'sound_on_capture', fallback=False)
        self.prop['delayed_capture']  = self.config.getboolean('delayed_capture', 'delayed_capture', fallback=False)
        self.prop['delayed_time']     = self.config.getint('delayed_capture', 'delayed_time', fallback=5)
        self.prop['delayed_time_ms']  = self.prop['delayed_time'] * 1000
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
        self.prop['periodic_save_folder']   = self.config.get('periodic', 'save_folder', fallback=_MY_PICTURE)
        self.prop['periodic_interval']      = self.config.getint('periodic', 'interval', fallback=3)
        self.prop['periodic_interval_ms']   = self.prop['periodic_interval'] * 1000
        self.prop['periodic_stop_modifier'] = self.config.getint('periodic', 'stop_modifier', fallback=0)
        self.prop['periodic_stop_fkey']     = self.config.getint('periodic', 'stop_fkey', fallback=11)
        self.prop['periodic_target']        = self.config.getint('periodic', 'target', fallback=0)
        self.prop['periodic_numbering']     = self.config.getint('periodic', 'numbering', fallback=0)
        if len(self.prop['periodic_save_folder']) == 0:
            # 保存フォルダが無いので、'Pictures'を登録する
            self.prop['periodic_save_folder'] = _MY_PICTURE
            save_req = True

        return save_req

    def property_to_config(self):
        """プロパティ展開処理
        * プロパティを設定値に展開する
        Args:
            none
        Returns:
            none
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

    def CreatePopupMenu(self) -> wx.Menu:
        """Popupメニューの生成 (override)
        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。
        Args:
            none
        Returns:
            wx.Menuオブジェクト
        """
        global _disable_hotkeys
        # メニューの生成
        menu = wx.Menu()
        # Help
        # sub_menu = wx.Menu()
        # create_menu_item(sub_menu, MyScreenShot.ID_MENU_HELP, 'Helpを表示', self.on_menu_show_help)
        # sub_menu.AppendSeparator()
        item = create_menu_item(menu, MyScreenShot.ID_MENU_ABOUT, 'バージョン情報...', self.on_menu_show_about)
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.INFO.value))
        menu.AppendSeparator()
        # Settings
        item = create_menu_item(menu, MyScreenShot.ID_MENU_SETTINGS, '環境設定...', self.on_menu_settings)
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.SETTINGS.value))
        sub_menu = wx.Menu()
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_MCURSOR, 'マウスカーソルをキャプチャーする', self.on_menu_toggle_item, kind = wx.ITEM_CHECK)
        sub_item.Enable(False)  # Windowsでは現状マウスカーソルがキャプチャー出来ないので「無効」にしておく
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_SOUND, 'キャプチャー終了時に音を鳴らす', self.on_menu_toggle_item, kind = wx.ITEM_CHECK)
        sub_item.Check(self.prop['sound_on_capture'])
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_DELAYED, '遅延キャプチャーをする', self.on_menu_toggle_item, kind = wx.ITEM_CHECK)
        sub_item.Check(self.prop['delayed_capture'])
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_TRIMMING, 'トリミングをする', self.on_menu_toggle_item, kind = wx.ITEM_CHECK)
        sub_item.Check(self.prop['trimming'])
        item = menu.AppendSubMenu(sub_menu, 'クイック設定')
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.QUICK_SETTINGS.value))
        menu.AppendSeparator()
        # Auto save folder
        sub_menu = wx.Menu()
        for n, folder in enumerate(self.prop['save_folders']):
            sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_FOLDER1 + n, f'{n + 1}: {folder}', self.on_menu_select_save_folder, kind = wx.ITEM_RADIO)
            if n == self.prop['save_folder_index']:
                sub_item.Check()
        item = menu.AppendSubMenu(sub_menu, '保存先フォルダ')
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.AUTO_SAVE_FOLDER.value))
        # Open folder
        sub_menu = wx.Menu()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_AUTO, '1: 自動保存先フォルダ(選択中)', self.on_menu_open_folder)
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_PERIODIC, '2: 定期実行フォルダ', self.on_menu_open_folder)
        item = menu.AppendSubMenu(sub_menu, 'フォルダを開く')
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.OPEN_FOLDER.value))
        menu.AppendSeparator()
        # Periodic caputure settings
        item = create_menu_item(menu, MyScreenShot.ID_MENU_PERIODIC, '定期実行設定...', self.on_menu_periodic_settings)
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.PERIODIC.value))
        menu.AppendSeparator()
        # Caputure
        display_count: int = self.prop['display']   # ディスプレイ数
        sub_menu1 = wx.Menu()
        sub_menu2 = wx.Menu()
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN0_CB, f'0: デスクトップ\t{self.hotkey_clipboard[0] if not _disable_hotkeys else ""}', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN0, f'0: デスクトップ\t{self.hotkey_imagefile[0] if not _disable_hotkeys else ""}', self.on_menu_imagefile)
        disp: int = 0
        for n in range(display_count):
            disp += 1
            create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN1_CB + n, f'{disp}: ディスプレイ {disp}\t{self.hotkey_clipboard[disp] if not _disable_hotkeys else ""}', self.on_menu_clipboard)
            create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN1 + n, f'{disp}: ディスプレイ {disp}\t{self.hotkey_imagefile[disp] if not _disable_hotkeys else ""}', self.on_menu_imagefile)
        disp += 1
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_ACTIVE_CB, f'{disp}: アクティブウィンドウ\t{self.hotkey_clipboard[disp] if not _disable_hotkeys else ""}', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_ACTIVE, f'{disp}: アクティブウィンドウ\t{self.hotkey_imagefile[disp] if not _disable_hotkeys else ""}', self.on_menu_imagefile)
        item = menu.AppendSubMenu(sub_menu1, 'クリップボードへコピー')
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.COPY_TO_CB.value))
        item = menu.AppendSubMenu(sub_menu2, 'PNGファイルへ保存')
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(MenuIcon.SAVE_TO_PNG.value)))
        menu.AppendSeparator()
        # Exit
        item = create_menu_item(menu, MyScreenShot.ID_MENU_EXIT, '終了', self.on_menu_exit)
        item.SetBitmap(self._icon_img.GetBitmap(MenuIcon.EXIT.value))

        return menu

    def do_capture(self):
        """キャプチャー実行処理
        * Queueの要求に従い、キャプチャー画像を処理する
        Args:
            none
        Returns:
            none
        """
        moni_no, filename = self.req_queue.get()
        _debug_print(f"do_capture moni_no={moni_no}, filename={filename}")
        sct_img = None
        with mss.mss() as sct:
            if moni_no == 90:   # アクティブウィンドウ
                if (info := get_active_window()) == None:
                    self._beep.Play()
                    return

                window_title, area_coord = info
                sct_img = sct.grab(area_coord)
            else:
                if moni_no < 0 and moni_no >= len(sct.monitors):
                    self._beep.Play()
                    return

                sct_img = sct.grab(sct.monitors[moni_no])

        if sct_img is not None:
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            width, height = img.size
            _debug_print(f'Capture (0, 0)-({width}, {height})')
            # トリミング
            if self.prop['trimming']:
                top: int         = self.prop['trimming_size'][0]
                temp_bottom: int = self.prop['trimming_size'][1]
                left: int        = self.prop['trimming_size'][2]
                temp_right: int  = self.prop['trimming_size'][3]
                right: int  = width  - temp_right  if width  > temp_right  else width
                bottom: int = height - temp_bottom if height > temp_bottom else height

                img = img.crop((left, top, right, bottom))
                _debug_print(f'Trimming ({top}, {left})-({right}, {bottom})')

            if len(filename) == 0:
                # クリップボードへコピー
                output = io.BytesIO()
                img.convert('RGB').save(output, 'BMP')
                data = output.getvalue()[14:]
                output.close()
                copy_bitmap_to_clipboard(data)
            else:
                # ファイルへ保存
                img.save(filename)

            """"""
            msg: str = ''
            match moni_no:
                case 90:
                    msg = f'"Active window - {window_title}" area={area_coord}'
                case 0:
                    msg = '"Desktop"'
                case _:
                    msg = f'"Display-{moni_no}"'
            _debug_print(f'capture {msg} & {"copy clipboard" if len(filename) == 0 else "save PNG file"}')
            """"""

            if self.prop['sound_on_capture']:
                self._success.Play()

    def on_menu_show_help(self, event):
        """HELPメニューイベントハンドラ
        * アプリケーションのHELPを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        _debug_print("on_menu_show_help")

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
        # Aboutダイアログに各種情報を設定する
        info = AboutDialogInfo()
        info.SetIcon(self._app_icons.GetIcon(wx.Size(48, 48)))
        info.SetName(_app_name_)
        info.SetVersion(f' Ver.{__version__}\n on Python {self._platform_info[2]} and wxPython {wx.__version__}.')
        info.SetCopyright(f'(C) 2024-, by {__author__}. All right reserved.')
        info.SetDescription('Screenshot tool. (EXE conversion is by Nuitka.)')
        info.SetLicense('MIT License.')
        # info.SetWebSite("")
        info.AddDeveloper(__author__)
        # 表示する
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
            dlg.set_prop(self.prop)     # 設定値をダイアログ側へ渡す
            # 設定ダイアログを表示する
            if dlg.ShowModal() == wx.ID_OK:
                # 前回値をコピー
                auto_save: bool  = self.prop['auto_save']
                save_folder: str = self.prop['save_folders'][self.prop['save_folder_index']] if not self.prop['save_folder_index'] < 0 else ''
                numbering: int   = self.prop['numbering']
                prefix: str = self.prop['prefix']
                digits: int = self.prop['sequence_digits']
                begin: int  = self.prop['sequence_begin']
                hotkey_clipboard: int = self.prop['hotkey_clipboard']
                hotkey_activewin: int = self.prop['hotkey_activewin']
                dlg.get_prop(self.prop) # ダイアログの設定状態を取得する

                new_save_folder: str = self.prop['save_folders'][self.prop['save_folder_index']] if not self.prop['save_folder_index'] < 0 else ''
                # 自動保存に変更 or 保存フォルダが変更 or (ナンバリングがシーケンス番号に変更) or
                # (接頭語が変更) or シーケンス桁数が変更 or 開始番号が変更 なら
                # 次回シーケンス番号をリセット
                if ((auto_save != self.prop['auto_save'] and self.prop['auto_save']) or
                    (save_folder != new_save_folder) or
                    (numbering != self.prop['numbering'] and self.prop['numbering'] != 0) or
                    (self.prop['numbering'] != 0 and (
                        prefix != self.prop['prefix'] or digits != self.prop['sequence_digits'] or begin != self.prop['sequence_begin']))):
                    self.sequence = -1
                    _debug_print('Reset sequence No.')
                # キャプチャーHotkeyが変更されたら再登録
                if (hotkey_clipboard != self.prop['hotkey_clipboard'] or
                    hotkey_activewin != self.prop['hotkey_activewin']):
                    self.set_capture_hotkey()
                    _debug_print('Change capture Hotkey.')

    def on_menu_toggle_item(self, event):
        """クイック設定メニューイベントハンドラ
        * 「マウスカーソルのキャプチャーの有効/無効」を切り替える。（現状無効）
        * 「キャプチャー終了時に音を鳴らすの有効/無効」を切り替える。
        * 「遅延キャプチャーの有効/無効」を切り替える。
        * 「トリミングの有効/無効」を切り替える。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        match event.GetId():
            case MyScreenShot.ID_MENU_MCURSOR:  # マウスカーソルキャプチャー
                self.prop['capture_mcursor'] = not self.prop['capture_mcursor']
            case MyScreenShot.ID_MENU_SOUND:    # キャプチャー終了時に音を鳴らす
                self.prop['sound_on_capture'] = not self.prop['sound_on_capture']
            case MyScreenShot.ID_MENU_DELAYED:  # 遅延キャプチャー
                self.prop['delayed_capture'] = not self.prop['delayed_capture']
            case MyScreenShot.ID_MENU_TRIMMING: # トリミング
                self.prop['trimming'] = not self.prop['trimming']
            case _:
                pass

    def on_menu_select_save_folder(self, event):
        """Select save folderメニューイベントハンドラ
        * 自動保存フォルダーを切り替える。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        old: int = self.prop['save_folder_index']
        id: int = event.GetId()
        for n in range(len(self.prop['save_folders'])):
            if id == (MyScreenShot.ID_MENU_FOLDER1 + n):
                self.prop['save_folder_index'] = n
        _debug_print(f'on_menu_select_save_folder (id={event.GetId()}), Change {old} => {self.prop['save_folder_index']}')

    def on_menu_open_folder(self, event):
        """Open folderメニューイベントハンドラ
        * 自動または定期保存フォルダーを開く。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        folder: str = self.prop['save_folders'][self.prop['save_folder_index']] if event.GetId() == MyScreenShot.ID_MENU_OPEN_AUTO else self.prop['periodic_save_folder']
        if os.path.exists(folder):
            os.startfile(folder)
            _debug_print(f'on_menu_open_folder ({event.GetId()}, {folder})')

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
            # 設定ダイアログを表示する
            id: int = dlg.ShowModal()
            if id == wx.ID_EXECUTE or id == wx.ID_OK:
                # 前回値としてコピー
                save_folder: str = self.prop['periodic_save_folder']
                numbering: int   = self.prop['periodic_numbering']
                stop_modifier    = self.prop['periodic_stop_modifier']
                fkey: str        = self.prop['periodic_stop_fkey']
                dlg.get_prop(self.prop) # ダイアログの設定状態を取得する

                # 保存フォルダが変更 or ナンバリングがシーケンス番号に変更 なら
                # 次回シーケンス番号をリセット
                if ((save_folder != self.prop['periodic_save_folder']) or
                    (numbering != self.prop['periodic_numbering'] and self.prop['periodic_numbering'] != 0 and self.prop['numbering'] != 0)):
                    self.sequence = -1
                    _debug_print('Reset sequence No.')
                # 停止用Hotkeyが変更されたら再登録
                if (stop_modifier != self.prop['periodic_stop_modifier'] or fkey != self.prop['periodic_stop_fkey']):
                    self.set_periodic_stop_hotkey(True)
                    _debug_print('Change periodic stop Hotkey.')

            if id == wx.ID_EXECUTE:
                _debug_print("on_menu_periodic_settings closed 'Start'")
                # 実行開始
                self.prop['periodic_capture'] = True
                wx.CallLater(self.prop['periodic_interval_ms'] ,self.do_periodic)
            elif id == wx.ID_STOP:
                _debug_print("on_menu_periodic_settings closed 'Stop'")
                # 実行停止
                self.prop['periodic_capture'] = False

    def stop_periodic_capture(self):
        """定期実行停止処理
        """
        _debug_print("Stop periodic capture")
        # 実行停止
        self.prop['periodic_capture'] = False
        if self.prop['sound_on_capture']:
            self._success.Play()

    def create_filename(self, periodic: bool=False) -> str:
        """PNGファイル名生成処理
        * PNGファイル名を生成する。
        Args:
            periodic (bool): True=定期実行向け
        Returns:
            PNGファイル名 (str)
        """
        # 選択中の保存フォルダを取得する
        path: str = self.prop['periodic_save_folder'] if periodic else self.prop['save_folders'][self.prop['save_folder_index']]
        if not os.path.exists(path):
            wx.MessageBox('保存フォルダ "{path}" が見つかりません。', 'ERROR', wx.ICON_ERROR)
            return ''

        # ナンバリング種別を取得する
        kind: int = self.prop['numbering'] if not periodic else (self.prop['periodic_numbering'] if self.prop['periodic_numbering'] == 0 else self.prop['numbering'])
        if kind == 0:   # 日時
            filename: str = datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
        else:           # 接頭語＋シーケンス番号
            # ToDo: 保存フォルダからprefix+sequencial_no(digits)のファイル名の一覧を取得し、次のファイル名を決定する
            prefix: str = self.prop['prefix']
            digits: int = self.prop['sequence_digits']
            begin: int  = self.sequence if self.sequence > self.prop['sequence_begin'] else self.prop['sequence_begin']
            _debug_print(f'Sequence No.={begin}')

            filename = f'{prefix}{begin:0>{digits}}.png'
            if os.path.exists(os.path.join(path, filename)):
                # 現在のシーケンス番号のファイルが存在した場合、空きを探す
                ptn: str = rf'{prefix}\d{{{digits}}}\.[pP][nN][gG]'
                files: list = scan_directory(path, ptn, False)
                if len(files) == 0:
                    # 存在しない -> プレフィックス＋開始番号
                    _debug_print('Sequencial file not found.')
                    filename = f'{prefix}{begin:0>{digits}}.png'
                else:
                    _debug_print(f'Last Sequencial file is {os.path.basename(files[len(files) - 1])}')
                    basname_wo_ext: str = os.path.splitext(os.path.basename(files[len(files) - 1]))[0]
                    sno: int = int(basname_wo_ext[-digits:])
                    if (sno >= begin):
                        sno += 1
                        _debug_print(f'Sequence No. changed. {begin}->{sno}')
                        begin = sno
                    filename = f'{prefix}{begin:0>{digits}}.png'
            else:
                _debug_print(f'No duplicates "{filename}')

            self.sequence = begin + 1   # 次回のシーケンス番号
            _debug_print(f'Next sequence NO.={self.sequence}')

        return os.path.join(path, filename)

    def do_periodic(self):
        """定期実行処理
        Args:
            none
        Returns:
            none
        """
        if self.prop['periodic_capture']:
            # ターゲットを取得
            moni_no: int  = self.prop['periodic_target'] if self.prop['periodic_target'] != -1 else 90
            filename: str = self.create_filename(True)
            self.req_queue.put((moni_no, filename))
            wx.CallAfter(self.do_capture)
            # 次回を予約
            wx.CallLater(self.prop['periodic_interval_ms'], self.do_periodic)

    def copy_to_clipboard(self, id: int):
        """キャプチャー要求処理（Clipboardコピー）
        * メニューとホット・キーイベントから呼ばれる
        Args:
            id (int): EVENT(Menu) ID
        Returns:
            none
        """
        global _BASE_DELAY_TIME
        _debug_print(f'copy_to_clipboard ({id})')
        # ターゲット取得
        moni_no: int = 90 if id == MyScreenShot.ID_MENU_ACTIVE_CB else (id - MyScreenShot.ID_MENU_SCREEN0_CB)
        self.req_queue.put((moni_no, ''))
        # 遅延時間算出
        delay_ms: int = self.prop['delayed_time_ms'] if self.prop['delayed_capture'] else _BASE_DELAY_TIME
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def save_to_imagefile(self, id: int):
        """キャプチャー要求処理（PNGファイル保存）
        * メニューとホット・キーイベントから呼ばれる
        Args:
            id (int): EVENT(Menu) ID
        Returns:
            none
        """
        global _BASE_DELAY_TIME
        _debug_print(f'save_to_imagefile ({id})')
        # ターゲット取得
        moni_no: int = 90 if id == MyScreenShot.ID_MENU_ACTIVE else (id - MyScreenShot.ID_MENU_SCREEN0)
        # 保存ファイル名生成
        filename: str = self.create_filename(self.prop['periodic_capture'])
        if len(filename) == 0:
            return

        self.req_queue.put((moni_no, filename))
        delay_ms: int = self.prop['delayed_time_ms'] if self.prop['delayed_capture'] else _BASE_DELAY_TIME
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def on_menu_clipboard(self, event):
        """クリップボードへコピーメニューイベントハンドラ
        * キャプチャー画像(BMP)をClipboardへコピーする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.copy_to_clipboard(event.GetId())

    def on_menu_imagefile(self, event):
        """Save to PNG fileメニューイベントハンドラ
        * キャプチャー画像をPNGファイルとして保存する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.save_to_imagefile(event.GetId())

    def on_menu_exit(self, event):
        """Exitメニューイベントハンドラ
        * アプリケーションを終了する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        _debug_print('Exit App')
        self.save_config()              # 設定値を保存

        wx.CallAfter(self.Destroy)
        self.frame.Close()


class SettingsDialog(wx.Dialog):
    """環境設定ダイアログ（wxGladeで、設計&生成）
    """
    def __init__(self, *args, **kwds):
        # begin wxGlade: SettingsDialog.__init__
        # Button Event ID's
        self.BTN_ID_ADD  = 1001
        self.BTN_ID_DEL  = 1002
        self.BTN_ID_UP   = 1003
        self.BTN_ID_DOWN = 1004
        self.BTN_ID_BMP_CTRL_ALT   = 1101
        self.BTN_ID_BMP_CTRL_SHIFT = 1102
        self.BTN_ID_PNG_CTRL_ALT   = 1103
        self.BTN_ID_PNG_CTRL_SHIFT = 1104
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

        self.list_box_auto_save_folders = wx.ListBox(self.panel_1, wx.ID_ANY, choices=[], style=wx.LB_NEEDED_SB | wx.LB_SINGLE)
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
        sizer_8.Add(self.checkbox_delayed_capture, 0, wx.ALL | wx.EXPAND, 4)

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
        sizer_11.Add(self.checkbox_trimming, 0, wx.ALL | wx.EXPAND, 4)

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

        self.radio_btn_hotkey_bmp_ctrl_alt = wx.RadioButton(sizer_23.GetStaticBox(), self.BTN_ID_BMP_CTRL_ALT, "Ctrl+Alt", style=wx.RB_GROUP)
        self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(1)
        sizer_23.Add(self.radio_btn_hotkey_bmp_ctrl_alt, 1, 0, 0)

        self.radio_btn_hotkey_bmp_ctrl_shift = wx.RadioButton(sizer_23.GetStaticBox(), self.BTN_ID_BMP_CTRL_SHIFT, "Ctrl+Shift")
        sizer_23.Add(self.radio_btn_hotkey_bmp_ctrl_shift, 1, 0, 0)

        sizer_24 = wx.StaticBoxSizer(wx.StaticBox(self.notebook_1_pane_2, wx.ID_ANY, u"PNG保存"), wx.VERTICAL)
        sizer_21.Add(sizer_24, 0, wx.EXPAND | wx.LEFT, 4)

        self.radio_btn_hotkey_png_ctrl_alt = wx.RadioButton(sizer_24.GetStaticBox(), self.BTN_ID_PNG_CTRL_ALT, "Ctrl+Alt", style=wx.RB_GROUP)
        sizer_24.Add(self.radio_btn_hotkey_png_ctrl_alt, 1, 0, 0)

        self.radio_btn_hotkey_png_ctrl_shift = wx.RadioButton(sizer_24.GetStaticBox(), self.BTN_ID_PNG_CTRL_SHIFT, "Ctrl+Shift")
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
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))

        self.button_add_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_add)
        self.button_del_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_del)
        self.button_up_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_move)
        self.button_down_folder.Bind(wx.EVT_BUTTON, self.on_save_folder_move)
        self.radio_btn_hotkey_bmp_ctrl_alt.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_change)
        self.radio_btn_hotkey_bmp_ctrl_shift.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_change)
        self.radio_btn_hotkey_png_ctrl_alt.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_change)
        self.radio_btn_hotkey_png_ctrl_shift.Bind(wx.EVT_RADIOBUTTON, self.on_btn_hotkey_change)
        # end wxGlade

    def on_save_folder_add(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの追加
        """
        defaultPath: str = os.getcwd()
        agwstyle: int = MDD.DD_MULTIPLE|MDD.DD_DIR_MUST_EXIST
        with MDD.MultiDirDialog(None, title="フォルダの追加", defaultPath=defaultPath, agwStyle=agwstyle) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            # 選択されたフォルダをListBoxに追加する
            paths: list = dlg.GetPaths()
            for folder in paths:
                self.list_box_auto_save_folders.Append(folder)
        event.Skip()

    def on_save_folder_del(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの削除
        """
        index:int = self.list_box_auto_save_folders.GetSelection()
        if index != wx.NOT_FOUND:
            self.list_box_auto_save_folders.Delete(index)

            count: int = self.list_box_auto_save_folders.GetCount()
            index -= 1
            if (index >= 0 and (count > 0 and index < count)):
                self.list_box_auto_save_folders.SetSelection(index)
        event.Skip()

    def on_save_folder_move(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの移動（上下）
        """
        index: int = self.list_box_auto_save_folders.GetSelection()
        move: int = 0
        limit: bool = False

        if event.GetId() == self.BTN_ID_UP:
            move = -1
            limit = True if index > 0 else False
        else:
            move = 1
            limit = True if index < (self.list_box_auto_save_folders.GetCount() - 1) else False

        if index != wx.NOT_FOUND and limit:
            folder: str = self.list_box_auto_save_folders.GetString(index)
            _debug_print(f'folder={index}:{folder}')
            self.list_box_auto_save_folders.Delete(index)
            self.list_box_auto_save_folders.Insert(folder, index + move)
            self.list_box_auto_save_folders.SetSelection(index + move)
        event.Skip()

    """ HotKey: 修飾キーの切り替え制御 """
    def on_btn_hotkey_change(self, event):  # wxGlade: SettingsDialog.<event_handler>
        match event.GetId():
            case self.BTN_ID_BMP_CTRL_ALT:
                self.radio_btn_hotkey_png_ctrl_shift.SetValue(True)
            case self.BTN_ID_BMP_CTRL_SHIFT:
                self.radio_btn_hotkey_png_ctrl_alt.SetValue(True)
            case self.BTN_ID_PNG_CTRL_ALT:
                self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(True)
            case self.BTN_ID_PNG_CTRL_SHIFT:
                self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(True)
            case _:
                pass
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
        self.choice_hotkey_active_window.SetSelection(prop['hotkey_activewin'])

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
        prop['delayed_time_ms'] = prop['delayed_time'] * 1000
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

        self.spin_ctrl_periodic_interval = wx.SpinCtrl(self, wx.ID_ANY, "3", min=1, max=3600, style=wx.ALIGN_RIGHT | wx.SP_ARROW_KEYS)
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

        self.radio_btn_periodic_numbering_datetime = wx.RadioButton(sizer_8.GetStaticBox(), wx.ID_ANY, u"日時 (yyyymmdd_hhmmss)", style=wx.RB_GROUP)
        self.radio_btn_periodic_numbering_datetime.SetValue(1)
        sizer_8.Add(self.radio_btn_periodic_numbering_datetime, 0, wx.ALL, 4)

        self.radio_btn_periodic_numbering_autosave = wx.RadioButton(sizer_8.GetStaticBox(), wx.ID_ANY, u"自動保存の設定に従う")
        sizer_8.Add(self.radio_btn_periodic_numbering_autosave, 0, wx.ALL, 4)

        sizer_9 = wx.BoxSizer(wx.VERTICAL)
        sizer_6.Add(sizer_9, 1, wx.EXPAND, 0)

        self.button_periodic_start = wx.Button(self, wx.ID_EXECUTE, u"開始")
        self.button_periodic_start.Enable(False)
        sizer_9.Add(self.button_periodic_start, 1, wx.ALL | wx.EXPAND, 4)

        self.button_periodic_stop = wx.Button(self, wx.ID_STOP, u"終了")
        self.button_periodic_stop.Enable(False)
        sizer_9.Add(self.button_periodic_stop, 0, wx.ALL | wx.EXPAND, 4)

        sizer_2 = wx.StdDialogButtonSizer()
        sizer_1.Add(sizer_2, 0, wx.ALIGN_RIGHT | wx.ALL, 4)

        self.button_OK = wx.Button(self, wx.ID_OK, "")
        self.button_OK.SetDefault()
        sizer_2.AddButton(self.button_OK)

        self.button_CANCEL = wx.Button(self, wx.ID_CANCEL, "")
        sizer_2.AddButton(self.button_CANCEL)

        sizer_2.Realize()

        self.SetSizer(sizer_1)

        self.SetAffirmativeId(self.button_OK.GetId())
        self.SetEscapeId(self.button_CANCEL.GetId())

        self.Layout()
        self.Centre()
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))

        self.button_periodic_folder_brows.Bind(wx.EVT_BUTTON, self.on_save_folder_browse)
        self.button_periodic_start.Bind(wx.EVT_BUTTON, self.on_periodic_capture_ctrl)
        self.button_periodic_stop.Bind(wx.EVT_BUTTON, self.on_periodic_capture_ctrl)
        # end wxGlade

    def on_save_folder_browse(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        """保存フォルダの選択
        """
        defaultPath: str = self.text_ctrl_periodic_folder.GetValue()
        if len(defaultPath) == 0 or not os.path.exists(defaultPath):
            defaultPath = os.getcwd()
        agwstyle: int = MDD.DD_MULTIPLE|MDD.DD_DIR_MUST_EXIST
        with MDD.MultiDirDialog(None, title="フォルダの選択", defaultPath=defaultPath, agwStyle=agwstyle) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            paths: list = dlg.GetPaths()
            for folder in paths:
                self.text_ctrl_periodic_folder.SetValue(folder)
                _debug_print(f'Set {folder}')
        event.Skip()

    def on_periodic_capture_ctrl(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        _debug_print(f"Event handler 'on_periodic_capture_ctrl' id={event.GetId()}")
        self.EndModal(event.GetId())
        event.Skip()

    def set_prop(self, prop: dict):
        """設定値をコントロールに反映する
        """
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not prop['periodic_capture'])
        self.button_periodic_stop.Enable(prop['periodic_capture'])
        # 保存フォルダ
        self.text_ctrl_periodic_folder.SetValue(prop['periodic_save_folder'])
        # 間隔
        self.spin_ctrl_periodic_interval.SetValue(prop['periodic_interval'])
        # 停止キー（修飾キー）
        self.choice_periodic_stopkey_modifire.SetSelection(prop['periodic_stop_modifier'])
        self.choice_periodic_stop_fkey.SetSelection(prop['periodic_stop_fkey'])
        # ターゲット
        for i in range(prop['display']):
            item: str = f'ディスプレイ {i + 1}'
            self.choice_periodic_capture_target.Insert(item, self.choice_periodic_capture_target.GetCount() - 1)
        if prop['periodic_target'] == -1:
            self.choice_periodic_capture_target.SetSelection(self.choice_periodic_capture_target.GetCount() - 1)
        else:
            self.choice_periodic_capture_target.SetSelection(prop['periodic_target'])
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
        prop['periodic_interval_ms'] = prop['periodic_interval'] * 1000
        # 停止キー（修飾キー）
        prop['periodic_stop_modifier'] = self.choice_periodic_stopkey_modifire.GetSelection()
        prop['periodic_stop_fkey']     = self.choice_periodic_stop_fkey.GetSelection()
        # ターゲット
        index: int = self.choice_periodic_capture_target.GetSelection()
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


class App(wx.App):

    def OnInit(self):
        frame = wx.Frame(None)
        frame.Centre()  # AboutBoxをプライマリディスプレイの中心に出すため
        self.SetTopWindow(frame)
        MyScreenShot(frame)

        _debug_print('launch App')
        return True


def app_init() -> bool:
    """アプリケーション初期化
    * 設定ファイル、リソースファイルのPATHを取得等
    Args:
        none
    Returns:
        none
    """
    global _debug_mode
    global _disable_hotkeys
    global _CONFIG_FILE
    global _EXE_PATH
    global _RESRC_PATH
    global _NO_CONSOLE
    global _MY_PICTURE
    # コマンドラインパラメータ解析（デバッグオプションのみ）
    parser = argparse.ArgumentParser(description='My ScreenSHot Tool.')
    parser.add_argument('--debug', action='store_true', help='Debug mode.')
    parser.add_argument('--disable-hotkeys', action='store_true', help='Disable Hot Keys.')
    # 解析結果
    args = parser.parse_args()
    _debug_mode = args.debug
    _disable_hotkeys = args.disable_hotkeys

    # 実行ファイル展開PATHを取得
    base_path, _NO_CONSOLE = get_running_path()
    # 実行ファイルPATHを設定
    _EXE_PATH = os.path.dirname(sys.argv[0])
    _EXE_PATH = '.' + os.sep if len(_EXE_PATH) == 0 else _EXE_PATH
    # 設定ファイルは実行ファイル（スクリプト）ディレクトリ下
    _CONFIG_FILE = os.path.join(_EXE_PATH, _CONFIG_FILE)
    if not os.path.exists(_CONFIG_FILE):
        # 設定ファイルが存在しない場合は、デフォルト設定で作成
        config = configparser.ConfigParser()
        config.read_dict(mydef._CONFIG_DEFAULT)
        try:
            with open(_CONFIG_FILE, 'w') as fc:
                config.write(fc)

        except OSError as e:
            wx.MessageBox(f'Configration file save failed.\n ({e})', 'ERROR', wx.ICON_ERROR)
            return False
    # リソースディレクトリは実行ディレクトリ下
    _RESRC_PATH = os.path.join(base_path, _RESRC_PATH)
    # マイピクチャのPATHを取得
    _MY_PICTURE = get_special_directory()[2]
    return True


if __name__ == "__main__":
    # 初期化
    if not app_init():
        sys.exit()

    app = App(False)
    app.MainLoop()
