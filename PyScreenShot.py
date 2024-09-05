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
import io
import os
import mss
from PIL import Image
from screeninfo import get_monitors
import sys
import win32clipboard

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
_APP_ICONS = None


_MAX_MONITERS = 4
_MAX_SAVE_FOLDERS = 16

_CONFIG_DEFAULT = {
    'basic': {
        'mouse_cursor': 'False',
        'sound_on_capture': 'False',
        'auto_save': 'True',
        'prefix': '1',
        'prefix_string': 'SS',
        'sequence_digits': '6',
        'start_number': '0',
        'save_folder_index': '0',
        'folder1': 'ピクチャ'
    },
    'delayed_capture': {
        'delayed_capture': 'False',
        'delayed_time': '5'
    },
    'triming': {
        'triming': 'False',
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
        'target': '-1',
        'numbering': '0',
        'exit_key': 'F11'
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


def copy_clipboard(data):
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

class MyScreenShot(TaskBarIcon):
    """Menu IDs"""
    # Help
    ID_MENU_HELP = 901          # ヘルプを表示
    ID_MENU_ABOUT = 902         # バージョン情報
    # 環境設定
    ID_MENU_SETTINGS = 101
    # クイック設定
    ID_MENU_MCURSOR = 102       # マウスカーソルキャプチャを有効
    ID_MENU_DELAYED = 103       # 遅延キャプチャを有効
    #--- 保存先フォルダ(Base)
    ID_MENU_FOLDER1 = 201
    # フォルダを開く
    ID_MENU_OPEN_AUTO = 301     # 自動保存フォルダ(選択中)
    ID_MENU_OPEN_PERIODIC = 302 # 定期実行フォルダ
    # 定期実行設定
    ID_MENU_PERIODIC = 401
    # クリップボードへコピー
    ID_MENU_SCREEN0_CB = 501    # デスクトップ
    ID_MENU_SCREEN1_CB = 502    # ディスプレイ1
    ID_MENU_ACTIVE_CB = 590     # アクティブウィンドウ
    # PNG保存
    ID_MENU_SCREEN0 = 601       # デスクトップ
    ID_MENU_SCREEN1 = 602       # ディスプレイ1
    ID_MENU_ACTIVE= 690         # アクティブウィンドウ
    # 終了
    ID_MENU_EXIT = 991

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
        # print("CreatePopupMenu")
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
        if self._platform_info[0] == 'Windows':
            sub_item.Enable(False)  # Windowsでは現状マウスカーソルがキャプチャ出来ないので「無効」にしておく
        else:
            sub_item.Check(self.config.getboolean('other', 'mouse_cursor', fallback = False))
        sub_item = create_menu_item(sub_menu, MyScreenShot.ID_MENU_DELAYED, '遅延キャプチャを有効', self.on_menu_toggle_delayed_capture, kind = wx.ITEM_CHECK)
        sub_item.Check(self.config.getboolean('other', 'delayed_capture', fallback = False))
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
        # ディスプレイ情報の初期化と読み込み
        self.get_display_info()
        # メニューアイコン画像の展開
        self._icon_img = wx.ImageList(24, 24)
        for name in menu_image.index:
            self._icon_img.Add(menu_image.catalog[name].GetBitmap())
        # BEEP音
        self._beep = Sound()
        self._beep.CreateFromData(sound.get_snd_beep_bytearray())
        self._success = Sound()
        self._success.CreateFromData(sound.get_snd_success_bytearray())

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
        self.save_folder_count = 1

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
        id = event.GetId()
        sct_img = None
        with mss.mss() as sct:
            match id:
                case MyScreenShot.ID_MENU_ACTIVE_CB:
                    pass
                case _:
                    moni_no = id - MyScreenShot.ID_MENU_SCREEN0_CB
                    if moni_no >= 0:
                        sct_img = sct.grab(sct.monitors[moni_no])

                    if moni_no == 0:
                        print('capture "Desktop"')
                    else:
                        print(f'capture "Display-{moni_no}"')

        if sct_img is not None:
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            output = io.BytesIO()
            img.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]
            output.close()
            copy_clipboard(data)

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
