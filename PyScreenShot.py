#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" MyScreenShot
スクリーンショットアプリケーション
* 
* 
"""
import argparse
import configparser
import os
from screeninfo import get_monitors
import sys

from myutils import get_running_path, platform_info, scan_directory, atof, natural_keys

import wx
from wx.adv import TaskBarIcon, EVT_TASKBAR_LEFT_DCLICK, Sound, AboutBox, AboutDialogInfo

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
_TRAY_ICON = 'ScreenShot.ico'

_MAX_MONITERS = 4
_MAX_SAVE_FOLDERS = 8

_PERIODIC_EXIT_KEYS = [\
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',\
    'shift+f1', 'shift+f2', 'shift+f3', 'shift+f4', 'shift+f5', 'shift+f6', 'shift+f7', 'shift+f8', 'shift+f9', 'shift+f10', 'shift+f11', 'shift+f12',\
    'alt+f1', 'alt+f2', 'alt+f3', 'alt+f4', 'alt+f5', 'alt+f6', 'alt+f7', 'alt+f8', 'alt+f9', 'alt+f10', 'alt+f11', 'alt+f12'\
]

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


class MyScreenShot(TaskBarIcon):
    # Menu IDs
    #--- Help
    ID_MENU_HELP = 901
    ID_MENU_ABOUT = 902
    #--- Settings
    ID_MENU_SETTINGS = 101
    ID_MENU_MCURSOR = 102
    ID_MENU_DELAYED = 103
    #--- Folders
    ID_MENU_FOLDER0 = 200
    ID_MENU_FOLDER1 = 201
    ID_MENU_FOLDER2 = 202
    ID_MENU_FOLDER3 = 203
    ID_MENU_FOLDER4 = 204
    ID_MENU_FOLDER5 = 205
    ID_MENU_FOLDER6 = 206
    ID_MENU_FOLDER7 = 207       # 最大保存フォルダー数に合わせること
    ID_MENU_OPEN_AUTO = 301
    ID_MENU_OPEN_PERIODIC = 302
    #--- Periodic settings
    ID_MENU_PERIODIC = 401
    #--- Capture
    ID_MENU_ACTIVE_CB = 500
    ID_MENU_SCREEN0_CB = 501
    ID_MENU_SCREEN1_CB = 502
    ID_MENU_SCREEN2_CB = 503
    ID_MENU_SCREEN3_CB = 504
    ID_MENU_SCREEN4_CB = 505    # 最大ディスプレイ数に合わせること
    ID_MENU_ACTIVE= 600
    ID_MENU_SCREEN0 = 601
    ID_MENU_SCREEN1 = 602
    ID_MENU_SCREEN2 = 603
    ID_MENU_SCREEN3 = 604
    ID_MENU_SCREEN4 = 605    # 最大ディスプレイ数に合わせること
    #--- Exit
    ID_MENU_EXIT = 903

    def __init__(self, frame):
        self.frame = frame
        super(MyScreenShot, self).__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # 初期処理
        self.initialize()

    def CreatePopupMenu(self):
        """Popupメニューの生成 (override)
        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。
        """
        print("CreatePopupMenu")
        menu = wx.Menu()
        # Help
        sub_menu = wx.Menu()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_HELP, 'Show Help', self.on_menu_show_help)
        sub_menu.AppendSeparator()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_ABOUT, 'About...', self.on_menu_show_about)
        menu.AppendSubMenu(sub_menu, 'Help')
        menu.AppendSeparator()
        # Settings
        create_menu_item(menu, MyScreenShot.ID_MENU_SETTINGS, 'Settings...', self.on_menu_settings)
        sub_menu = wx.Menu()
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_MCURSOR, 'Mouse cursor capture', self.on_menu_toggle_mouse_capture, kind = wx.ITEM_CHECK)
        sub_item.Check(self.config.getboolean('other', 'mouse_cursor', fallback = False))
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_DELAYED, 'Time delayed capture', self.on_menu_toggle_delayed_capture, kind = wx.ITEM_CHECK)
        sub_item.Check(self.config.getboolean('other', 'delayed_capture', fallback = False))
        menu.AppendSubMenu(sub_menu, 'Quick setting')
        menu.AppendSeparator()
        # Auto save folder
        sub_menu = wx.Menu()
        value = self.config.get('basic', 'folder0', fallback = r'C:\Users\u1601\Pictures')
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_FOLDER0, f'1: {value}', self.on_menu_select_save_folder, kind = wx.ITEM_RADIO)
        for n in range(1, _MAX_SAVE_FOLDERS):
            value = self.config.get('basic', f'folder{n}', fallback = '')
            if len(value) == 0:
                break
            sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_FOLDER0 + n, f'{n}: {value}', self.on_menu_select_save_folder, kind = wx.ITEM_RADIO)
            self.save_folder_count += 1
            if n == self.config.getint('basic', 'save_folder_index', fallback = 0):
                sub_item.Check()
        menu.AppendSubMenu(sub_menu, 'Auto save folder')
        # Open folder
        sub_menu = wx.Menu()
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_AUTO, '1: Auto save (now)', self.on_menu_open_folder)
        create_menu_item(sub_menu, MyScreenShot.ID_MENU_OPEN_PERIODIC, '2: Periodic', self.on_menu_open_folder)
        menu.AppendSubMenu(sub_menu, 'Open folder')
        menu.AppendSeparator()
        # Periodic caputure settings
        create_menu_item(menu, MyScreenShot.ID_MENU_PERIODIC, 'Periodic capture settings...', self.on_menu_periodic_settings)
        menu.AppendSeparator()
        # Caputure
        sub_menu1 = wx.Menu()
        sub_menu2 = wx.Menu()
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN0_CB, f'1: Screen 0', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN0, f'1: Screen 0', self.on_menu_imagefile)
        if self.dis_count > 1:
            for n in range(0, self.dis_count):
                create_menu_item(sub_menu1, MyScreenShot.ID_MENU_SCREEN1_CB + n, f'{n + 2}: Screen {n + 1}', self.on_menu_clipboard)
                create_menu_item(sub_menu2, MyScreenShot.ID_MENU_SCREEN1 + n, f'{n + 2}: Screen {n + 1}', self.on_menu_imagefile)
        create_menu_item(sub_menu1, MyScreenShot.ID_MENU_ACTIVE_CB, f'{self.dis_count + 1}: Active window', self.on_menu_clipboard)
        create_menu_item(sub_menu2, MyScreenShot.ID_MENU_ACTIVE, f'{self.dis_count + 1}: Active window', self.on_menu_imagefile)
        menu.AppendSubMenu(sub_menu1, 'Copy to clipboard')
        menu.AppendSubMenu(sub_menu2, 'Save to PNG file')
        menu.AppendSeparator()
        # Exit
        create_menu_item(menu, MyScreenShot.ID_MENU_EXIT, 'Exit', self.on_menu_exit)

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
        self._app_icons = wx.IconBundle(os.path.join(_RESRC_PATH, _TRAY_ICON), wx.BITMAP_TYPE_ICO)
        self.SetIcon(self._app_icons.GetIcon(wx.Size(16, 16)), _TRAY_TOOLTIP)
        # 設定値の初期設定と設定値の読み込み
        cwd = os.getcwd()
        self.config = configparser.ConfigParser()
        self.config.add_section('basic')
        self.config.add_section('periodic')
        self.config.add_section('other')
        self.config.add_section('hotkey')
        self.config.set('basic', 'auto_save', str(True))
        self.config.set('basic', 'prefix', str(1))      # 0:yyyymmdd-hhmmss, 1:prefix_string+sequence_number
        self.config.set('basic', 'prefix_string', 'SS')
        self.config.set('basic', 'sequence_digits', str(6))
        self.config.set('basic', 'start_number', str(0))
        self.config.set('basic', 'save_folder_index', str(0))
        self.save_folder_count = 1
        self.config.set('basic', 'folder0', r'C:\Users\u1601\Pictures')
        for n in range(1, _MAX_SAVE_FOLDERS):
            self.config.set('basic', f'folder{n}', '')
        self.config.set('periodic', 'mode', str(False))
        self.config.set('periodic', 'save_folder', r'C:\Users\u1601\Pictures')
        self.config.set('periodic', 'interval', str(3))
        self.config.set('periodic', 'target', str(-1))  # -1:Active window, 0:All screen, 1~:Screen1~
        self.config.set('periodic', 'numbering', str(0))# 0:yyyymmdd-hhmmss, 1:Depends on the auto-save mode setting
        self.config.set('periodic', 'exit_key', 'f11')
        self.config.set('other', 'mouse_cursor', str(False))
        self.config.set('other', 'delayed_capture', str(False))
        self.config.set('other', 'delayed_time', str(5))
        self.config.set('hotkey', 'clipboard', 'ctrl + alt')
        self.config.set('hotkey', 'imagefile', 'ctrl + shift')
        self.config.set('hotkey', 'active_window', 'f9')
        self.load_config()
        # ディスプレイ情報の初期化と読み込み
        self.get_display_info()

    def load_config(self):
        """設定値読み込み処理
        * 各種設定値を設定ファイルから読み込む。
        Args:
            none
        Returns:
            none
        Note:
            ConfigParserモジュール使用
        """
        global _CONFIG_FILE
        if os.path.exists(_CONFIG_FILE):
            try:
                with open(_CONFIG_FILE, 'r') as f:
                    self.config.read_file(f)
            except OSError as e:
                wx.MessageBox(f'Configration file load failed.\n ({e})\n Use default settings.', 'ERROR', wx.ICON_ERROR)
            except configparser.Error as e:
                wx.MessageBox(f'Configration file parse failed.\n ({e})', 'ERROR', wx.ICON_ERROR)
        else:
            wx.MessageBox('Configration file not found.\nCreate default configuration file.', 'Attension', wx.ICON_EXCLAMATION)
            self.save_config()

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

    def get_display_info(self):
        """ディスプレイ情報取得処理
        * ディスプレイ情報（数、サイズ、座標等）を取得する。
        Args:
            none
        Returns:
            none
        Note:
        """
        # 初期化
        self.dis_count = 0      # ディスプレイの枚数
        self.windowx_cd = []    # 最終的に使う数
        self.windowy_cd = []    # 最終的に使う数
        self.windowx_cd = []    # 最終的に使う数
        self.windowy_cd = []    # 最終的に使う数
        self.windowx_size = []  #ディスプレイの解像度(サイズ)
        self.windowy_size = []  #ディスプレイの解像度(サイズ)

        temp_windowx_cd = []    # 仮のディスプレイの左上の座標 X
        temp_windowy_cd = []    # 仮のディスプレイの左上の座標 Y
        min_x_cd = 10000000     # (初期値は適当)
        min_y_cd = 10000000     # (初期値は適当)

        # ディスプレイ数を取得する
        monitors = get_monitors()
        self.dis_count = len(monitors)
        # for d in get_monitors():
        #     self.dis_count = self.dis_count + 1

        Range = range(0, self.dis_count)
        # ディスプレイ情報を取得する
        for d in Range:
            # monitor = get_monitors()[i]
            monitor = monitors[d]
            temp_windowx_cd.append(monitor.x)
            temp_windowy_cd.append(monitor.y)
            self.windowx_size.append(monitor.width)
            self.windowy_size.append(monitor.height)

        # 座標を比較し、切り抜きに使う数値へ変更する
        for i in Range:
            if temp_windowx_cd[i] < min_x_cd:
                min_x_cd = temp_windowx_cd[i]

            if temp_windowy_cd[i] < min_y_cd:
                min_y_cd = temp_windowy_cd[i]

        for j in Range:
            self.windowx_cd.append(-1 * min_x_cd + temp_windowx_cd[j])
            self.windowy_cd.append(-1 * min_y_cd + temp_windowy_cd[j])

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
        print("on_menu_settings")

    def on_menu_toggle_mouse_capture(self, event):
        """Mouse captureメニューイベントハンドラ
        * マウスカーソルのキャプチャーを有効/無効にする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        flag = not self.config.getboolean('other', 'mouse_cursor', fallback = True)
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
            if id == (MyScreenShot.ID_MENU_FOLDER0 + n):
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
        id = event.GetId()
        print(f'on_menu_clipboard ({id})')

    def on_menu_imagefile(self, event):
        """Save to PNG fileメニューイベントハンドラ
        * キャプチャー画像をPNGファイルとして保存する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        id = event.GetId()
        print(f'on_menu_imagefile ({id})')

    def on_menu_exit(self, event):
        """Exitメニューイベントハンドラ
        * アプリケーションを終了する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        print('on_menu_exit')
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
