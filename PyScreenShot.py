#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" PyScreenShot
スクリーンショットアプリケーション
"""
import argparse
import configparser
import io
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from functools import partial
from queue import Queue

import keyboard
import mss
import mss.tools
import win32clipboard
import win32gui
import wx
import wx.lib.agw.multidirdialog as MDD
from PIL import Image
from screeninfo import get_monitors
from wx.adv import (
    EVT_TASKBAR_LEFT_DCLICK,
    AboutBox,
    AboutDialogInfo,
    Sound,
    TaskBarIcon,
)

import mydefine as mydef
import version as ver
from myutils.util import (
    get_special_directory,
    platform_info,
    scan_directory,
)
from res import app_icon, menu_image, sound

logger = logging.getLogger(__name__)

# 設定ファイルパス
_CONFIG_FILE: str = f"{ver.INFO["APP_NAME"]}.ini"
# # ヘルプファイル（アプリからは未使用）
# _HELP_FILE: str = "manual.html"

_TRAY_TOOLTIP: str = f"{ver.INFO["APP_NAME"]} App"


def create_menu_item(
    menu: wx.Menu, id: int = -1, label: str = "", func=None, kind=wx.ITEM_NORMAL
) -> wx.MenuItem:
    """ """
    item = wx.MenuItem(menu, id, label, kind=kind)
    if func is not None:
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)

    return item


def enum_window_callback(hwnd: int, lparam: int, window_titles: list[str]):
    if win32gui.IsWindowEnabled(hwnd) == 0:
        return

    if win32gui.IsWindowVisible(hwnd) == 0:
        return

    if win32gui.IsIconic(hwnd) != 0:
        return

    if (window_text := win32gui.GetWindowText(hwnd)) == "":
        return

    # GW_OWNER = 4
    # if (owner := win32gui.GetWindow(hwnd, GW_OWNER)) != 0:
    #     return

    # if (class_name := win32gui.GetClassName(hwnd)) in ["CabinetWClass"]:
    #     return
    # QtのPopup、ToolTipを除外する
    class_name = win32gui.GetClassName(hwnd)
    if class_name is None or True in {x in class_name for x in ["QToolTip", "QPopup", "QWindowPopup", "QWindowToolTip"]}:
        return

    if window_text not in window_titles:
        window_titles.append(window_text)


def get_active_window() -> tuple[str, dict] | None:
    """アクティブウィンドウの座標（RECT）を取得する
    * 取得したRECT情報とWindowタイトルを返す
    （座標はmssのキャプチャー範囲に変換する）
    """
    window_titles: list[str] = []
    win32gui.EnumWindows(partial(enum_window_callback, window_titles=window_titles), 0)
    # for title in window_titles:
    #     print(title)
    # print("====")
    if not window_titles:
        return None

    # hwnd  = win32gui.GetForegroundWindow()
    # title = win32gui.GetWindowText(hwnd)
    window_title: str = window_titles[0]
    if (hwnd := win32gui.FindWindow(None, window_title)) == 0:
        return None

    # win32gui.SetForegroundWindow(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width: int = abs(right - left)
    height: int = abs(bottom - top)
    area: dict = {"left": left, "top": top, "width": width, "height": height}

    return (window_title, area)


def copy_bitmap_to_clipboard(data):
    """クリップボードにビットマップデータをコピーする"""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()


class MyScreenShot(TaskBarIcon):
    # fmt: off
    """Menu IDs"""
    # バージョン情報
    ID_MENU_HELP: int  = 901         # ヘルプを表示
    ID_MENU_ABOUT: int = 902         # バージョン情報
    # 環境設定
    ID_MENU_SETTINGS: int = 101
    # クイック設定
    ID_MENU_MCURSOR: int  = 102      # マウスカーソルキャプチャーを有効
    ID_MENU_SOUND: int    = 103      # キャプチャー終了時に音を鳴らす
    ID_MENU_DELAYED: int  = 104      # 遅延キャプチャーを有効
    ID_MENU_TRIMMING: int = 105      # トリミングを有効
    ID_MENU_RESET: int    = 106      # シーケンス番号のリセット
    #--- 保存先フォルダ(Base)
    ID_MENU_FOLDER1: int = 201
    # フォルダを開く
    ID_MENU_OPEN_AUTO: int     = 301 # 自動保存フォルダ(選択中)
    ID_MENU_OPEN_PERIODIC: int = 302 # 定期実行フォルダ
    # 定期実行設定
    ID_MENU_PERIODIC: int = 401
    # クリップボードへコピー
    ID_MENU_SCREEN0_CB: int = 501    # デスクトップ
    # ID_MENU_SCREEN1_CB: int = 502    # ディスプレイ1
    ID_MENU_ACTIVE_CB: int  = 590    # アクティブウィンドウ
    # PNG保存
    ID_MENU_SCREEN0: int = 601       # デスクトップ
    # ID_MENU_SCREEN1: int = 602       # ディスプレイ1
    ID_MENU_ACTIVE: int  = 690       # アクティブウィンドウ
    # 終了
    ID_MENU_EXIT: int = 991
    """ ICON Index for ImageList """
    ICON_INFO             = 0
    ICON_SETTINGS         = 1
    ICON_QUICK_SETTINGS   = 2
    ICON_AUTO_SAVE_FOLDER = 3
    ICON_OPEN_FOLDER      = 4
    ICON_PERIODIC         = 5
    ICON_COPY_TO_CB       = 6
    ICON_SAVE_TO_PNG      = 7
    ICON_EXIT             = 8
    """ Hotkey Modifiers """
    HK_MOD_NONE: str       = ""
    HK_MOD_SHIFT: str      = "Shift"
    HK_MOD_CTRL: str       = "Ctrl"
    HK_MOD_ALT: str        = "Alt"
    HK_MOD_CTRL_ALT: str   = f"{HK_MOD_CTRL}+{HK_MOD_ALT}"
    HK_MOD_CTRL_SHIFT: str = f"{HK_MOD_CTRL}+{HK_MOD_SHIFT}"
    HK_MOD_SHIFT_ALT: str  = f"{HK_MOD_SHIFT}+{HK_MOD_ALT}"
    """ Other constants """
    BASE_DELAY_TIME: int = 400   # (ms)
    MAX_SAVE_FOLDERS: int = 64
    # fmt: on
    MY_PICTURES: str = ""
    #
    debug_mode: bool = False
    disable_hotkeys: bool = False

    def __init__(self, frame):
        self.frame = frame
        super(MyScreenShot, self).__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # プロパティ
        myss_cls = MyScreenShot
        self.prop: dict = {
            "display": 1,
            "auto_save": True,
            "save_folders": [],
            "save_folder_index": -1,
            "numbering": 0,
            "prefix": "",
            "sequence_digits": 0,
            "sequence_begin": 0,
            "capture_mcursor": False,
            "sound_on_capture": False,
            "delayed_capture": False,
            "delayed_time": 0,
            "delayed_time_ms": 0,
            "trimming": False,
            "trimming_size": [0, 0, 0, 0],
            "hotkey_clipboard": 0,
            "hotkey_imagefile": 1,
            "hotkey_activewin": 8,
            "periodic_capture": False,
            "periodic_save_folder": "",
            "periodic_interval": 0,
            "periodic_interval_ms": 0,
            "periodic_stop_modifier": 0,
            "periodic_stop_fkey": 0,
            "periodic_target": 0,
            "periodic_numbering": 0,
            "MAX_SAVE_FOLDERS": myss_cls.MAX_SAVE_FOLDERS,  # for SettingDialog
        }
        self.capture_hotkey_tbl = (myss_cls.HK_MOD_CTRL_ALT, myss_cls.HK_MOD_CTRL_SHIFT)
        # キャプチャーHotkeyアクセレーターリスト（0:デスクトップ、1～:ディスプレイ、last:アクティブウィンドウ）
        self.menu_clipboard: list[tuple] = []
        self.menu_imagefile: list[tuple] = []
        # 定期実行停止Hotkey
        self.periodic_stop_hotkey_tbl: tuple = (
            myss_cls.HK_MOD_NONE,
            myss_cls.HK_MOD_SHIFT,
            myss_cls.HK_MOD_CTRL,
            myss_cls.HK_MOD_ALT,
        )
        self.hotkey_periodic_stop: str = ""
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
        self._platform_info: tuple = platform_info()
        # ディスプレイ数取得
        self.prop["display"] = len(get_monitors())
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

    def set_capture_hotkey(self, first: bool = False):
        """キャプチャー用ホット・キー登録処理
        * キャプチャー用ホット・キーとメニューのアクセレーター文字列を展開する
        * キャプチャー用ホット・キーを登録する
        Args:
            first (bool): 初回フラグ（初回はホット・キー削除なし）
        Returns:
            none
        """
        myss_cls = MyScreenShot
        if myss_cls.disable_hotkeys:
            return

        if not first:
            # 現在のHotkeyを削除
            for hotkey, _, _ in self.menu_clipboard:
                keyboard.remove_hotkey(hotkey)
            for hotkey, _, _ in self.menu_imagefile:
                keyboard.remove_hotkey(hotkey)

        # 設定値(prop)からキャプチャー用の修飾キーを取得し、それぞれのホット・キー文字列を展開する
        hk_clipbd: str = self.capture_hotkey_tbl[self.prop["hotkey_clipboard"]]
        hk_imagef: str = self.capture_hotkey_tbl[self.prop["hotkey_imagefile"]]

        # Menu, Hotkeyの情報を生成する（[0]:Hotkey, [1]:Menu ID, [2]:Menu name）
        self.menu_clipboard.clear()
        self.menu_imagefile.clear()
        disp: int = self.prop["display"]
        # デスクトップ[0]
        self.menu_clipboard.append(
            (f"{hk_clipbd}+0", myss_cls.ID_MENU_SCREEN0_CB, "0: デスクトップ")
        )
        self.menu_imagefile.append((f"{hk_imagef}+0", myss_cls.ID_MENU_SCREEN0, "0: デスクトップ"))
        # ディスプレイ[1～]
        for n in range(1, disp + 1):
            self.menu_clipboard.append(
                (f"{hk_clipbd}+{n}", myss_cls.ID_MENU_SCREEN0_CB + n, f"{n}: ディスプレイ {n}")
            )
            self.menu_imagefile.append(
                (f"{hk_imagef}+{n}", myss_cls.ID_MENU_SCREEN0 + n, f"{n}: ディスプレイ {n}")
            )
        # アクティブウィンドウ
        self.menu_clipboard.append(
            (
                f"{hk_clipbd}+F{self.prop["hotkey_activewin"] + 1}",
                myss_cls.ID_MENU_ACTIVE_CB,
                f"{disp + 1}: アクティブウィンドウ",
            )
        )
        self.menu_imagefile.append(
            (
                f"{hk_imagef}+F{self.prop["hotkey_activewin"] + 1}",
                myss_cls.ID_MENU_ACTIVE,
                f"{disp + 1}: アクティブウィンドウ",
            )
        )

        # Hotkeyの登録（デスクトップ[0]、ディスプレイ[1～]、アクティブウィンドウ[last]）
        for n in range(len(self.menu_clipboard)):
            logger.debug(
                f"Hotkey[{n}]={self.menu_clipboard[n][0]}, {self.menu_imagefile[n][0]}, id={self.menu_clipboard[n][1]}, {self.menu_imagefile[n][1]}"
            )
            keyboard.add_hotkey(
                self.menu_clipboard[n][0],
                wx.CallAfter,
                (self.copy_to_clipboard, self.menu_clipboard[n][1], False),
            )
            keyboard.add_hotkey(
                self.menu_imagefile[n][0],
                wx.CallAfter,
                (self.save_to_imagefile, self.menu_imagefile[n][1], False),
            )

    def set_periodic_stop_hotkey(self, first: bool):
        """定期実行停止ホット・キー登録処理
        Args:
            first (bool): 初回フラグ（初回はホット・キー削除なし）
        Returns:
            none
        """
        if MyScreenShot.disable_hotkeys:
            return

        if not first:
            # 現在のHotkeyを削除
            keyboard.remove_hotkey(self.hotkey_periodic_stop)

        # 設定値(prop)からホット・キー文字列を展開する
        modifire: str = self.periodic_stop_hotkey_tbl[self.prop["periodic_stop_modifier"]]
        fkey: str = f"F{self.prop['periodic_stop_fkey'] + 1}"
        self.hotkey_periodic_stop = fkey if len(modifire) == 0 else f"{modifire}+{fkey}"
        keyboard.add_hotkey(
            self.hotkey_periodic_stop, lambda: wx.CallAfter(self.stop_periodic_capture)
        )

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
            with open(_CONFIG_FILE, "r", encoding="utf-8") as fc:
                self.config.read_file(fc)
            result = True
        except OSError as e:
            wx.MessageBox(
                f"設定ファイルの読み込みに失敗しました\n ({e})\n デフォルト設定を使用します",
                "エラー",
                wx.ICON_ERROR,
            )
        except configparser.Error as e:
            wx.MessageBox(f"設定ファイルの解析に失敗しました\n ({e})", "エラー", wx.ICON_ERROR)

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
            with open(_CONFIG_FILE, "w") as fc:
                self.config.write(fc)

        except OSError as e:
            wx.MessageBox(f"設定ファイルの書き込みに失敗しました\n ({e})", "エラー", wx.ICON_ERROR)

    def config_to_property(self) -> bool:
        """設定値展開処理
        * 設定値をプロパティに展開する
        Args:
            none
        Returns:
            none
        """
        myss_cls = MyScreenShot
        save_req: bool = False
        # 自動保存
        self.prop["auto_save"] = self.config.getboolean("basic", "auto_save", fallback=True)
        # 自動保存フォルダ
        self.prop["save_folder_index"] = self.config.getint(
            "basic", "save_folder_index", fallback=-1
        )
        for n in range(1, myss_cls.MAX_SAVE_FOLDERS + 1):
            option_name: str = f"folder{n}"
            if not self.config.has_option("basic", option_name):
                break
            option: str = self.config.get("basic", option_name)
            self.prop["save_folders"].append(option)

        if self.prop["save_folders"]:
            if not (0 <= self.prop["save_folder_index"] < len(self.prop["save_folders"])):
                self.prop["save_folder_index"] = 0
                save_req = True
        else:
            # 自動保存フォルダが無いので、"Pictures"を登録する
            self.prop["save_folders"].append(myss_cls.MY_PICTURES)
            self.prop["save_folder_index"] = 0
            save_req = True
        # 自動保存時のナンバリング
        self.prop["numbering"] = self.config.getint("basic", "numbering", fallback=0)
        self.prop["prefix"] = self.config.get("basic", "prefix", fallback="SS")
        self.prop["sequence_digits"] = self.config.getint("basic", "sequence_digits", fallback=6)
        self.prop["sequence_begin"] = self.config.getint("basic", "sequence_begin", fallback=0)
        self.prop["capture_mcursor"] = self.config.getboolean(
            "other", "mouse_cursor", fallback=False
        )
        self.prop["sound_on_capture"] = self.config.getboolean(
            "other", "sound_on_capture", fallback=False
        )
        self.prop["delayed_capture"] = self.config.getboolean(
            "delayed_capture", "delayed_capture", fallback=False
        )
        self.prop["delayed_time"] = self.config.getint(
            "delayed_capture", "delayed_time", fallback=5
        )
        self.prop["delayed_time_ms"] = self.prop["delayed_time"] * 1000
        # トリミング
        self.prop["trimming"] = self.config.getboolean("trimming", "trimming", fallback=False)
        top: int = self.config.getint("trimming", "top", fallback=0)
        bottom: int = self.config.getint("trimming", "bottom", fallback=0)
        left: int = self.config.getint("trimming", "left", fallback=0)
        right: int = self.config.getint("trimming", "right", fallback=0)
        self.prop["trimming_size"] = [top, bottom, left, right]
        # ホット・キー
        self.prop["hotkey_clipboard"] = self.config.getint("hotkey", "clipboard", fallback=0)
        self.prop["hotkey_imagefile"] = self.config.getint("hotkey", "imagefile", fallback=1)
        self.prop["hotkey_activewin"] = self.config.getint("hotkey", "activewin", fallback=8)
        # 定期実行
        self.prop["periodic_save_folder"] = self.config.get(
            "periodic", "save_folder", fallback=myss_cls.MY_PICTURES
        )
        self.prop["periodic_interval"] = self.config.getint("periodic", "interval", fallback=3)
        self.prop["periodic_interval_ms"] = self.prop["periodic_interval"] * 1000
        self.prop["periodic_stop_modifier"] = self.config.getint(
            "periodic", "stop_modifier", fallback=0
        )
        self.prop["periodic_stop_fkey"] = self.config.getint("periodic", "stop_fkey", fallback=11)
        self.prop["periodic_target"] = self.config.getint("periodic", "target", fallback=0)
        self.prop["periodic_numbering"] = self.config.getint("periodic", "numbering", fallback=0)
        if len(self.prop["periodic_save_folder"]) == 0:
            # 保存フォルダが無いので、"Pictures"を登録する
            self.prop["periodic_save_folder"] = myss_cls.MY_PICTURES
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
        self.config.set("basic", "auto_save", str(self.prop["auto_save"]))
        # 自動保存フォルダ
        self.config.set("basic", "save_folder_index", str(self.prop["save_folder_index"]))
        for n, folder_name in enumerate(self.prop["save_folders"]):
            option_name: str = "folder" + str(n + 1)
            self.config.set("basic", option_name, folder_name)
        # 自動保存時のナンバリング
        self.config.set("basic", "numbering", str(self.prop["numbering"]))
        self.config.set("basic", "prefix", self.prop["prefix"])
        self.config.set("basic", "sequence_digits", str(self.prop["sequence_digits"]))
        self.config.set("basic", "sequence_begin", str(self.prop["sequence_begin"]))
        self.config.set("other", "mouse_cursor", str(self.prop["capture_mcursor"]))
        self.config.set("other", "sound_on_capture", str(self.prop["sound_on_capture"]))
        self.config.set("delayed_capture", "delayed_capture", str(self.prop["delayed_capture"]))
        self.config.set("delayed_capture", "delayed_time", str(self.prop["delayed_time"]))
        # トリミング
        self.config.set("trimming", "trimming", str(self.prop["trimming"]))
        trim_top, trim_bottom, trim_left, trim_right = self.prop["trimming_size"]
        self.config.set("trimming", "top", str(trim_top))
        self.config.set("trimming", "bottom", str(trim_bottom))
        self.config.set("trimming", "left", str(trim_left))
        self.config.set("trimming", "right", str(trim_right))
        # ホット・キー
        self.config.set("hotkey", "clipboard", str(self.prop["hotkey_clipboard"]))
        self.config.set("hotkey", "imagefile", str(self.prop["hotkey_imagefile"]))
        self.config.set("hotkey", "activewin", str(self.prop["hotkey_activewin"]))
        # 定期実行
        self.config.set("periodic", "save_folder", self.prop["periodic_save_folder"])
        self.config.set("periodic", "interval", str(self.prop["periodic_interval"]))
        self.config.set("periodic", "stop_modifier", str(self.prop["periodic_stop_modifier"]))
        self.config.set("periodic", "stop_fkey", str(self.prop["periodic_stop_fkey"]))
        self.config.set("periodic", "target", str(self.prop["periodic_target"]))
        self.config.set("periodic", "numbering", str(self.prop["periodic_numbering"]))

    def CreatePopupMenu(self) -> wx.Menu:
        """Popupメニューの生成 (override)
        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。
        Args:
            none
        Returns:
            wx.Menuオブジェクト
        """
        myss_cls = MyScreenShot
        # メニューの生成
        menu = wx.Menu()
        # バージョン情報
        item = create_menu_item(
            menu, myss_cls.ID_MENU_ABOUT, "バージョン情報...", self.on_menu_show_about
        )
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_INFO))
        menu.AppendSeparator()
        # 環境設定
        item = create_menu_item(
            menu, myss_cls.ID_MENU_SETTINGS, "環境設定...", self.on_menu_settings
        )
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_SETTINGS))
        # クイック設定
        sub_menu = wx.Menu()
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_MCURSOR,
            "マウスカーソルをキャプチャーする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Enable(
            False
        )  # Windowsでは現状マウスカーソルがキャプチャー出来ないので「無効」にしておく
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_SOUND,
            "キャプチャー終了時に音を鳴らす",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.prop["sound_on_capture"])
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_DELAYED,
            "遅延キャプチャーをする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.prop["delayed_capture"])
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_TRIMMING,
            "トリミングをする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.prop["trimming"])
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_RESET,
            "シーケンス番号のリセット",
            self.on_menu_reset_sequence,
        )
        item = menu.AppendSubMenu(sub_menu, "クイック設定")
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_QUICK_SETTINGS))
        menu.AppendSeparator()
        # 保存フォルダ
        sub_menu = wx.Menu()
        for n, folder in enumerate(self.prop["save_folders"]):
            sub_item = create_menu_item(
                sub_menu,
                myss_cls.ID_MENU_FOLDER1 + n,
                f"{n + 1}: {folder}",
                self.on_menu_select_save_folder,
                kind=wx.ITEM_RADIO,
            )
            if n == self.prop["save_folder_index"]:
                sub_item.Check()
        item = menu.AppendSubMenu(sub_menu, "保存先フォルダ")
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_AUTO_SAVE_FOLDER))
        # フォルダを開く
        sub_menu = wx.Menu()
        create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_OPEN_AUTO,
            "1: 自動保存先フォルダ(選択中)",
            self.on_menu_open_folder,
        )
        create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_OPEN_PERIODIC,
            "2: 定期実行フォルダ",
            self.on_menu_open_folder,
        )
        item = menu.AppendSubMenu(sub_menu, "フォルダを開く")
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_OPEN_FOLDER))
        menu.AppendSeparator()
        # 定期実行設定
        item = create_menu_item(
            menu, myss_cls.ID_MENU_PERIODIC, "定期実行設定...", self.on_menu_periodic_settings
        )
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_PERIODIC))
        menu.AppendSeparator()
        # キャプチャー（クリップボード、PNGファイル）
        display_count: int = self.prop["display"]  # ディスプレイ数
        sub_menu1 = wx.Menu()
        sub_menu2 = wx.Menu()
        for n in range(len(self.menu_clipboard)):
            create_menu_item(
                sub_menu1,
                self.menu_clipboard[n][1],
                f"{self.menu_clipboard[n][2]}\t{self.menu_clipboard[n][0] if not myss_cls.disable_hotkeys else ''}",
                self.on_menu_clipboard,
            )
            create_menu_item(
                sub_menu2,
                self.menu_imagefile[n][1],
                f"{self.menu_imagefile[n][2]}\t{self.menu_imagefile[n][0] if not myss_cls.disable_hotkeys else ''}",
                self.on_menu_imagefile,
            )
        item = menu.AppendSubMenu(sub_menu1, "クリップボードへコピー")
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_COPY_TO_CB))
        item = menu.AppendSubMenu(sub_menu2, "PNGファイルへ保存")
        item.SetBitmap(wx.Bitmap(self._icon_img.GetBitmap(myss_cls.ICON_SAVE_TO_PNG)))
        menu.AppendSeparator()
        # 終了
        item = create_menu_item(menu, myss_cls.ID_MENU_EXIT, "終了", self.on_menu_exit)
        item.SetBitmap(self._icon_img.GetBitmap(myss_cls.ICON_EXIT))

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
        logger.debug(f"do_capture {moni_no=}, {filename=}")
        sct_img = None
        with mss.mss() as sct:
            if moni_no == 90:  # アクティブウィンドウ
                if (info := get_active_window()) == None:
                    self._beep.Play()
                    return

                window_title, area_coord = info
                sct_img = sct.grab(area_coord)
            else:
                if not (0 <= moni_no < len(sct.monitors)):
                    self._beep.Play()
                    return

                sct_img = sct.grab(sct.monitors[moni_no])

        if sct_img is not None:
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            width, height = img.size
            """"""
            if MyScreenShot.debug_mode:
                msg: str = ""
                match moni_no:
                    case 90:
                        msg = f"'Active window - [{window_title}]', {area_coord}"
                    case 0:
                        msg = "'Desktop'"
                    case _:
                        msg = f"'Display-{moni_no}'"
                logger.debug(
                    f"Capture {msg}  & {'copy clipboard' if len(filename) == 0 else 'save PNG file'}"
                )
            """"""
            # トリミング（アクティブウィンドウ以外はトリミングしない）
            if moni_no == 90 and self.prop["trimming"]:
                top: int = self.prop["trimming_size"][0]
                temp_bottom: int = self.prop["trimming_size"][1]
                left: int = self.prop["trimming_size"][2]
                temp_right: int = self.prop["trimming_size"][3]
                right: int = width - temp_right if width > temp_right else width
                bottom: int = height - temp_bottom if height > temp_bottom else height

                img = img.crop((left, top, right, bottom))
                logger.debug(f"Trimming ({top}, {left})-({right}, {bottom})")

            if len(filename) == 0:
                # クリップボードへコピー
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                copy_bitmap_to_clipboard(data)
            else:
                # ファイルへ保存
                img.save(filename)

            if self.prop["sound_on_capture"]:
                self._success.Play()

    def on_menu_show_about(self, event):
        """Aboutメニューイベントハンドラ
        * アプリケーションのバージョン情報などを表示する。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        # Aboutダイアログに各種情報を設定する
        info = AboutDialogInfo()
        info.SetIcon(self._app_icons.GetIcon(wx.Size(48, 48)))
        info.SetName(ver.INFO["APP_NAME"])
        info.SetVersion(
            f" Ver.{ver.INFO["VERSION"]}\n on Python {self._platform_info[2]} and wxPython {wx.__version__}."
        )
        info.SetCopyright(ver.COPYRIGHT["COPYRIGHT"])
        info.SetDescription(f"{ver.INFO["FILE_DESCRIPTION"]}\n(Nuitka+MSVCによるEXE化.)")
        info.SetLicense(ver.COPYRIGHT["LICENSE"])
        # info.SetWebSite("")
        info.AddDeveloper(ver.COPYRIGHT["AUTHOR"])
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
            dlg.set_prop(self.prop)  # 設定値をダイアログ側へ渡す
            # 設定ダイアログを表示する
            if dlg.ShowModal() == wx.ID_OK:
                # 前回値をコピー
                auto_save: bool = self.prop["auto_save"]
                save_folder: str = (
                    self.prop["save_folders"][self.prop["save_folder_index"]]
                    if not self.prop["save_folder_index"] < 0
                    else ""
                )
                numbering: int = self.prop["numbering"]
                prefix: str = self.prop["prefix"]
                digits: int = self.prop["sequence_digits"]
                begin: int = self.prop["sequence_begin"]
                hotkey_clipboard: int = self.prop["hotkey_clipboard"]
                hotkey_activewin: int = self.prop["hotkey_activewin"]
                dlg.get_prop(self.prop)  # ダイアログの設定状態を取得する

                new_save_folder: str = (
                    self.prop["save_folders"][self.prop["save_folder_index"]]
                    if not self.prop["save_folder_index"] < 0
                    else ""
                )
                # 自動保存に変更 or 保存フォルダが変更 or (ナンバリングがシーケンス番号に変更) or
                # (接頭語が変更) or シーケンス桁数が変更 or 開始番号が変更 なら
                # 次回シーケンス番号をリセット
                if (
                    (auto_save != self.prop["auto_save"] and self.prop["auto_save"])
                    or (save_folder != new_save_folder)
                    or (numbering != self.prop["numbering"] and self.prop["numbering"] != 0)
                    or (
                        self.prop["numbering"] != 0
                        and (
                            prefix != self.prop["prefix"]
                            or digits != self.prop["sequence_digits"]
                            or begin != self.prop["sequence_begin"]
                        )
                    )
                ):
                    self.sequence = -1
                    logger.debug("Reset sequence No.")
                # キャプチャーHotkeyが変更されたら再登録
                if (
                    hotkey_clipboard != self.prop["hotkey_clipboard"]
                    or hotkey_activewin != self.prop["hotkey_activewin"]
                ):
                    self.set_capture_hotkey()
                    logger.debug("Change capture Hotkey.")

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
        myss_cls = MyScreenShot
        match event.GetId():
            case myss_cls.ID_MENU_MCURSOR:  # マウスカーソルキャプチャー
                self.prop["capture_mcursor"] = not self.prop["capture_mcursor"]
            case myss_cls.ID_MENU_SOUND:  # キャプチャー終了時に音を鳴らす
                self.prop["sound_on_capture"] = not self.prop["sound_on_capture"]
            case myss_cls.ID_MENU_DELAYED:  # 遅延キャプチャー
                self.prop["delayed_capture"] = not self.prop["delayed_capture"]
            case myss_cls.ID_MENU_TRIMMING:  # トリミング
                self.prop["trimming"] = not self.prop["trimming"]
            case _:
                pass

    def on_menu_reset_sequence(self, event):
        """シーケンス番号のリセット
        * 現在保持している次のシーケンス番号をリセットする。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        self.sequence = -1

    def on_menu_select_save_folder(self, event):
        """Select save folderメニューイベントハンドラ
        * 自動保存フォルダーを切り替える。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        # old: int = self.prop["save_folder_index"]
        id: int = event.GetId()
        for n in range(len(self.prop["save_folders"])):
            if id == (MyScreenShot.ID_MENU_FOLDER1 + n):
                self.prop["save_folder_index"] = n
                break

    def on_menu_open_folder(self, event):
        """Open folderメニューイベントハンドラ
        * 自動または定期保存フォルダーを開く。
        Args:
            event (wx.EVENT): EVENTオブジェクト
        Returns:
            none
        """
        folder: str = (
            self.prop["save_folders"][self.prop["save_folder_index"]]
            if event.GetId() == MyScreenShot.ID_MENU_OPEN_AUTO
            else self.prop["periodic_save_folder"]
        )
        if os.path.exists(folder):
            os.startfile(folder)

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
            match dlg.ShowModal():
                case wx.ID_EXECUTE | wx.ID_OK:
                    # 前回値としてコピー
                    save_folder: str = self.prop["periodic_save_folder"]
                    numbering: int = self.prop["periodic_numbering"]
                    stop_modifier: int = self.prop["periodic_stop_modifier"]
                    fkey: str = self.prop["periodic_stop_fkey"]
                    dlg.get_prop(self.prop)  # ダイアログの設定状態を取得する

                    # 保存フォルダが変更 or ナンバリングがシーケンス番号に変更 なら
                    # 次回シーケンス番号をリセット
                    if (save_folder != self.prop["periodic_save_folder"]) or (
                        numbering != self.prop["periodic_numbering"]
                        and self.prop["periodic_numbering"] != 0
                        and self.prop["numbering"] != 0
                    ):
                        self.sequence = -1
                        logger.debug("Reset sequence No.")
                    # 停止用Hotkeyが変更されたら再登録
                    if (
                        stop_modifier != self.prop["periodic_stop_modifier"]
                        or fkey != self.prop["periodic_stop_fkey"]
                    ):
                        self.set_periodic_stop_hotkey(True)
                        logger.debug("Change periodic stop Hotkey.")
                case wx.ID_EXECUTE:
                    logger.debug("on_menu_periodic_settings closed 'Start'")
                    # 実行開始
                    self.prop["periodic_capture"] = True
                    wx.CallLater(self.prop["periodic_interval_ms"], self.do_periodic)
                case wx.ID_STOP:
                    logger.debug("on_menu_periodic_settings closed 'Stop'")
                    # 実行停止
                    self.prop["periodic_capture"] = False

    def stop_periodic_capture(self):
        """定期実行停止処理"""
        # 実行停止
        self.prop["periodic_capture"] = False
        logger.debug("Stop periodic capture")
        if self.prop["sound_on_capture"]:
            self._success.Play()

    def create_filename(self, periodic: bool = False) -> str:
        """PNGファイル名生成処理
        * PNGファイル名を生成する。
        Args:
            periodic (bool): True=定期実行向け
        Returns:
            PNGファイル名 (str)
        """
        # 選択中の保存フォルダを取得する
        path: str = (
            self.prop["periodic_save_folder"]
            if periodic
            else self.prop["save_folders"][self.prop["save_folder_index"]]
        )
        if not os.path.exists(path):
            wx.MessageBox(f"保存フォルダ '{path}' が見つかりません。", "ERROR", wx.ICON_ERROR)
            return ""

        # ナンバリング種別を取得する
        kind: int = (
            self.prop["numbering"]
            if not periodic
            else (
                self.prop["periodic_numbering"]
                if self.prop["periodic_numbering"] == 0
                else self.prop["numbering"]
            )
        )
        if kind == 0:  # 日時
            filename: str = datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        else:  # 接頭語＋シーケンス番号
            prefix: str = self.prop["prefix"]
            prefix_len: int = len(prefix)
            digits: int = self.prop["sequence_digits"]
            begin: int = (
                self.sequence
                if self.sequence > self.prop["sequence_begin"]
                else self.prop["sequence_begin"]
            )
            logger.debug(f"Sequence No.={begin}")

            filename = f"{prefix}{begin:0>{digits}}.png"
            if os.path.exists(os.path.join(path, filename)):
                # 現在のシーケンス番号のファイルが存在した場合、空きを探す
                ptn: str = rf"{prefix}\d{{{digits}}}\.png"
                files: list[str] = scan_directory(path, pattern=ptn, recursive=False)
                if not files:
                    # 存在しない -> プレフィックス＋開始番号
                    logger.debug("Sequencial file not found.")
                    filename = f"{prefix}{begin:0>{digits}}.png"
                else:
                    # ToDo: 保存フォルダからprefix+sequencial_no(digits)のファイル名の一覧を取得し、次のファイル名を決定する
                    # ファイル名からシーケンス番号のlistを作る
                    nums: list[int] = [
                        int(os.path.basename(file)[prefix_len : prefix_len + digits])
                        for file in files
                    ]
                    logger.debug(f"Sequencial No. list is {nums}")
                    # 空きを確認
                    snos: list[int] = [
                        y - 1 for x, y in zip(nums, nums[1:]) if x != y - 1 and y - 1 >= begin
                    ]
                    # 空きがなければシーケンス番号の最大値+1
                    begin = snos[0] if snos else nums[len(nums) - 1] + 1
                    logger.debug(f"Sequence No. changed to {begin}")
                    filename = f"{prefix}{begin:0>{digits}}.png"
            else:
                logger.debug(f"No duplicates '{filename}'")

            self.sequence = begin + 1  # 次回のシーケンス番号
            logger.debug(f"Next sequence No.={self.sequence}")

        return os.path.join(path, filename)

    def do_periodic(self):
        """定期実行処理
        Args:
            none
        Returns:
            none
        """
        if self.prop["periodic_capture"]:
            # ターゲットを取得
            moni_no: int = (
                self.prop["periodic_target"] if self.prop["periodic_target"] != -1 else 90
            )
            filename: str = self.create_filename(True)
            self.req_queue.put((moni_no, filename))
            wx.CallAfter(self.do_capture)
            # 次回を予約
            wx.CallLater(self.prop["periodic_interval_ms"], self.do_periodic)

    def copy_to_clipboard(self, id: int, from_menu: bool = True):
        """キャプチャー要求処理（Clipboardコピー）
        * メニューとホット・キーイベントから呼ばれる
        Args:
            id (int): EVENT(Menu) ID
        Returns:
            none
        """
        myss_cls = MyScreenShot
        # ターゲット取得
        moni_no: int = (
            90 if id == myss_cls.ID_MENU_ACTIVE_CB else (id - myss_cls.ID_MENU_SCREEN0_CB)
        )
        self.req_queue.put((moni_no, ""))
        # 遅延時間算出（遅延キャプチャー以外でメニュー経由は"BASE_DELAY_TIME"遅延させる）
        delay_ms: int = (
            self.prop["delayed_time_ms"]
            if self.prop["delayed_capture"]
            else 0 if not from_menu else myss_cls.BASE_DELAY_TIME
        )
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def save_to_imagefile(self, id: int, from_menu: bool = True):
        """キャプチャー要求処理（PNGファイル保存）
        * メニューとホット・キーイベントから呼ばれる
        Args:
            id (int): EVENT(Menu) ID
        Returns:
            none
        """
        myss_cls = MyScreenShot
        # ターゲット取得
        moni_no: int = 90 if id == myss_cls.ID_MENU_ACTIVE else (id - myss_cls.ID_MENU_SCREEN0)
        # 保存ファイル名生成
        filename: str = self.create_filename(self.prop["periodic_capture"])
        if len(filename) == 0:
            return

        self.req_queue.put((moni_no, filename))
        delay_ms: int = (
            self.prop["delayed_time_ms"]
            if self.prop["delayed_capture"]
            else 0 if not from_menu else myss_cls.BASE_DELAY_TIME
        )
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
        self.save_config()  # 設定値を保存

        wx.CallAfter(self.Destroy)
        self.frame.Close()


class SettingsDialog(wx.Dialog):
    """環境設定ダイアログ（wxGladeで、設計&生成）"""

    # fmt: off
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
    # fmt: on

    def on_save_folder_add(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの追加"""
        myss_cls = MyScreenShot
        if self.list_box_auto_save_folders.Count >= myss_cls.MAX_SAVE_FOLDERS:
            wx.MessageBox(
                f"{myss_cls.MAX_SAVE_FOLDERS}以上は登録できません。", "警告", wx.ICON_WARNING
            )
        else:
            defaultPath: str = os.getcwd()
            agwstyle: int = MDD.DD_MULTIPLE | MDD.DD_DIR_MUST_EXIST
            with MDD.MultiDirDialog(
                None, title="フォルダの追加", defaultPath=defaultPath, agwStyle=agwstyle
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                # 選択されたフォルダをListBoxに追加する
                paths: list = dlg.GetPaths()
                for folder in paths:
                    self.list_box_auto_save_folders.Append(folder)
        event.Skip()

    def on_save_folder_del(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの削除"""
        count: int = self.list_box_auto_save_folders.Count
        index: int = self.list_box_auto_save_folders.GetSelection()
        if not (count > 0 and index != wx.NOT_FOUND):
            wx.MessageBox("フォルダが無いか、選択されていません。", "警告", wx.ICON_WARNING)
        else:
            self.list_box_auto_save_folders.Delete(index)
            # ひとつ前のフォルダを選択状態にする
            if (count - 1) > 0:
                index = index - 1 if index > 0 else 0
                self.list_box_auto_save_folders.SetSelection(index)
        event.Skip()

    def on_save_folder_move(self, event):  # wxGlade: SettingsDialog.<event_handler>
        """自動保存フォルダの移動（上下）"""
        count: int = self.list_box_auto_save_folders.Count
        index: int = self.list_box_auto_save_folders.GetSelection()
        if not (count > 0 and index != wx.NOT_FOUND):
            wx.MessageBox("フォルダが無いか、選択されていません。", "警告", wx.ICON_WARNING)
        else:
            move: int = 0
            movable: bool = False

            if event.GetId() == self.BTN_ID_UP:
                move = -1
                movable = True if index > 0 else False
            else:
                move = 1
                movable = True if index < (count - 1) else False

            if movable:
                folder: str = self.list_box_auto_save_folders.GetString(index)
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
        """設定値をコントロールに反映する"""
        # --- 基本設定
        # 自動/手動
        if prop["auto_save"]:
            self.radio_btn_auto_save.SetValue(True)
        else:
            self.radio_btn_inquire_allways.SetValue(True)
        # 自動保存フォルダ
        for folder in prop["save_folders"]:
            self.list_box_auto_save_folders.Append(folder)
        self.list_box_auto_save_folders.SetSelection(prop["save_folder_index"])
        # ナンバリング
        if prop["numbering"] == 0:
            self.radio_btn_numbering_datetime.SetValue(True)
        else:
            self.radio_btn_nubering_prefix_sequence.SetValue(True)
        # 接頭語/シーケンス桁数/開始番号
        self.text_ctrl_prefix.SetValue(prop["prefix"])
        self.spin_ctrl_sequence_digits.SetValue(prop["sequence_digits"])
        self.spin_ctrl_sequence_begin.SetValue(prop["sequence_begin"])
        # --- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        self.checkbox_capture_mcursor.SetValue(prop["capture_mcursor"])
        self.checkbox_sound_on_capture.SetValue(prop["sound_on_capture"])
        # 遅延キャプチャー
        self.checkbox_delayed_capture.SetValue(prop["delayed_capture"])
        self.spin_ctrl_delayed_time.SetValue(prop["delayed_time"])
        # トリミング
        self.checkbox_trimming.SetValue(prop["trimming"])
        self.spin_ctrl_trimming_top.SetValue(prop["trimming_size"][0])
        self.spin_ctrl_trimming_bottom.SetValue(prop["trimming_size"][1])
        self.spin_ctrl_trimming_left.SetValue(prop["trimming_size"][2])
        self.spin_ctrl_trimming_right.SetValue(prop["trimming_size"][3])
        # ホット・キー
        if prop["hotkey_clipboard"] == 0:
            self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(True)
            self.radio_btn_hotkey_png_ctrl_shift.SetValue(True)
        else:
            self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(True)
            self.radio_btn_hotkey_png_ctrl_alt.SetValue(True)
        # ターゲット
        self.choice_hotkey_active_window.SetSelection(prop["hotkey_activewin"])
        # その他
        MyScreenShot.MAX_SAVE_FOLDERS = prop["MAX_SAVE_FOLDERS"]

    def get_prop(self, prop: dict):
        """設定値をプロパティに反映する"""
        # --- 基本設定
        # 自動/手動
        prop["auto_save"] = self.radio_btn_auto_save.GetValue()
        # 自動保存フォルダ
        prop["save_folders"].clear()
        for folder in self.list_box_auto_save_folders.Items:
            prop["save_folders"].append(folder)
        prop["save_folder_index"] = self.list_box_auto_save_folders.GetSelection()
        # ナンバリング
        if self.radio_btn_numbering_datetime.GetValue():
            prop["numbering"] = 0
        else:
            prop["numbering"] = 1
        # 接頭語/シーケンス桁数/開始番号
        prop["prefix"] = self.text_ctrl_prefix.GetValue()
        prop["sequence_digits"] = self.spin_ctrl_sequence_digits.GetValue()
        prop["sequence_begin"] = self.spin_ctrl_sequence_begin.GetValue()
        # --- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        prop["capture_mcursor"] = self.checkbox_capture_mcursor.GetValue()
        prop["sound_on_capture"] = self.checkbox_sound_on_capture.GetValue()
        # 遅延キャプチャー
        prop["delayed_capture"] = self.checkbox_delayed_capture.GetValue()
        prop["delayed_time"] = self.spin_ctrl_delayed_time.GetValue()
        prop["delayed_time_ms"] = prop["delayed_time"] * 1000
        # トリミング
        prop["trimming"] = self.checkbox_trimming.GetValue()
        prop["trimming_size"] = [
            self.spin_ctrl_trimming_top.GetValue(),
            self.spin_ctrl_trimming_bottom.GetValue(),
            self.spin_ctrl_trimming_left.GetValue(),
            self.spin_ctrl_trimming_right.GetValue(),
        ]
        # ホット・キー
        if self.radio_btn_hotkey_bmp_ctrl_alt.GetValue():
            prop["hotkey_clipboard"] = 0
            prop["hotkey_imagefile"] = 1
        else:
            prop["hotkey_clipboard"] = 1
            prop["hotkey_imagefile"] = 0
        # ターゲット
        prop["hotkey_activewin"] = self.choice_hotkey_active_window.GetSelection()


# end of class SettingsDialog


class PeriodicDialog(wx.Dialog):
    """定期実行設定ダイアログ（wxGladeで、設計&生成）"""

    # fmt: off
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
    # fmt: on

    def on_save_folder_browse(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        """保存フォルダの選択"""
        defaultPath: str = self.text_ctrl_periodic_folder.GetValue()
        if len(defaultPath) == 0 or not os.path.exists(defaultPath):
            defaultPath = os.getcwd()
        agwstyle: int = MDD.DD_MULTIPLE | MDD.DD_DIR_MUST_EXIST
        with MDD.MultiDirDialog(
            None, title="フォルダの選択", defaultPath=defaultPath, agwStyle=agwstyle
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            paths: list = dlg.GetPaths()
            for folder in paths:
                self.text_ctrl_periodic_folder.SetValue(folder)
        event.Skip()

    def on_periodic_capture_ctrl(self, event):  # wxGlade: PeriodicDialog.<event_handler>
        self.EndModal(event.GetId())
        event.Skip()

    def set_prop(self, prop: dict):
        """設定値をコントロールに反映する"""
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not prop["periodic_capture"])
        self.button_periodic_stop.Enable(prop["periodic_capture"])
        # 保存フォルダ
        self.text_ctrl_periodic_folder.SetValue(prop["periodic_save_folder"])
        # 間隔
        self.spin_ctrl_periodic_interval.SetValue(prop["periodic_interval"])
        # 停止キー（修飾キー）
        self.choice_periodic_stopkey_modifire.SetSelection(prop["periodic_stop_modifier"])
        self.choice_periodic_stop_fkey.SetSelection(prop["periodic_stop_fkey"])
        # ターゲット
        for i in range(prop["display"]):
            item: str = f"ディスプレイ {i + 1}"
            self.choice_periodic_capture_target.Insert(
                item, self.choice_periodic_capture_target.GetCount() - 1
            )
        if prop["periodic_target"] == -1:
            self.choice_periodic_capture_target.SetSelection(
                self.choice_periodic_capture_target.GetCount() - 1
            )
        else:
            self.choice_periodic_capture_target.SetSelection(prop["periodic_target"])
        # ナンバリング
        if prop["periodic_numbering"] == 0:
            self.radio_btn_periodic_numbering_datetime.SetValue(True)
        else:
            self.radio_btn_periodic_numbering_autosave.SetValue(True)

    def get_prop(self, prop: dict):
        """設定値をプロパティに反映する"""
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not prop["periodic_capture"])
        self.button_periodic_stop.Enable(prop["periodic_capture"])
        # 保存フォルダ
        prop["periodic_save_folder"] = self.text_ctrl_periodic_folder.GetValue()
        # 間隔
        prop["periodic_interval"] = self.spin_ctrl_periodic_interval.GetValue()
        prop["periodic_interval_ms"] = prop["periodic_interval"] * 1000
        # 停止キー（修飾キー）
        prop["periodic_stop_modifier"] = self.choice_periodic_stopkey_modifire.GetSelection()
        prop["periodic_stop_fkey"] = self.choice_periodic_stop_fkey.GetSelection()
        # ターゲット
        index: int = self.choice_periodic_capture_target.GetSelection()
        if index == (self.choice_periodic_capture_target.GetCount() - 1):
            prop["periodic_target"] = -1
        else:
            prop["periodic_target"] = index
        # ナンバリング
        if self.radio_btn_periodic_numbering_datetime.GetValue():
            prop["periodic_numbering"] = 0
        else:
            prop["periodic_numbering"] = 1


# end of class PeriodicDialog


class App(wx.App):

    def OnInit(self):
        frame = wx.Frame(None)
        frame.Centre()  # AboutBoxをプライマリディスプレイの中心に出すため
        self.SetTopWindow(frame)
        MyScreenShot(frame)

        return True


def app_init() -> bool:
    """アプリケーション初期化
    * 設定ファイル、リソースファイルのPATHを取得等
    Args:
        none
    Returns:
        none
    """
    global _CONFIG_FILE

    # コマンドラインパラメータ解析（デバッグオプションのみ）
    parser = argparse.ArgumentParser(description="My ScreenSHot Tool.")
    parser.add_argument("--debug", action="store_true", help="Debug mode.")
    parser.add_argument("--disable-hotkeys", action="store_true", help="Disable Hot Keys.")
    # 解析結果を格納
    args = parser.parse_args()
    MyScreenShot.debug_mode = args.debug
    MyScreenShot.disable_hotkeys = args.disable_hotkeys
    # ログ設定
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level)
    handler = logging.handlers.RotatingFileHandler(
        filename=f"{ver.INFO["APP_NAME"]}.log", maxBytes=1048576, backupCount=3, encoding="utf-8"
    )
    FORMAT_TML = "%(asctime)s.%(msecs)03d [%(levelname)-8s]"
    FORMAT_DBG = "[%(filename)s:%(lineno)d]"
    FORMAT_MSG = "%(message)s"
    FORMAT = (
        f"{FORMAT_TML} {FORMAT_DBG} {FORMAT_MSG}" if args.debug else f"{FORMAT_TML} {FORMAT_MSG}"
    )
    handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(handler)

    # 実行ファイルPATHを設定
    exe_path = os.path.dirname(sys.argv[0])
    exe_path = "." + os.sep if len(exe_path) == 0 else exe_path
    # マイピクチャのPATHを取得
    MyScreenShot.MY_PICTURES = get_special_directory()[2]

    # 設定ファイルは実行ファイル（スクリプト）ディレクトリ下
    _CONFIG_FILE = os.path.join(exe_path, _CONFIG_FILE)
    if not os.path.exists(_CONFIG_FILE):
        # 設定ファイルが存在しない場合は、デフォルト設定で作成
        logger.warning("設定ファイルがありません。デフォルト設定で作成します。")
        config = configparser.ConfigParser()
        config.read_dict(mydef._CONFIG_DEFAULT)
        try:
            with open(_CONFIG_FILE, "w") as fc:
                config.write(fc)

        except OSError as e:
            logger.warning("設定ファイルが作成できません。")
            return False

    return True


if __name__ == "__main__":
    # 初期化
    if not app_init():
        sys.exit()

    logger.info("=== Start ===")

    app = App(False)
    app.MainLoop()

    logger.info("=== Finish ===")
