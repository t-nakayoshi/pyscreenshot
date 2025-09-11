#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
"""PyScreenShot

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
from itertools import pairwise
from pathlib import Path
from queue import Queue
from zoneinfo import ZoneInfo

import keyboard
import mss
import mss.tools
import win32clipboard
import win32gui
import wx
import wx.lib.agw.multidirdialog as mdd
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
from PeriodicDialogBase import PeriodicDialogBase
from res import app_icon, menu_image, sound
from SettingsDialogBase import SettingsDialogBase

logger = logging.getLogger(__name__)

# APP_KEY: str = Path(__file__).stem if __name__ == "__main__" else __name__

TRAY_TOOLTIP: str = f"{ver.INFO['APP_NAME']} App"


def create_menu_item(
    menu: wx.Menu,
    menu_id: int = -1,
    label: str = "",
    func=None,  # ruff: noqa: ANN001
    kind=wx.ITEM_NORMAL,
) -> wx.MenuItem:
    """MenuItemの作成"""
    item = wx.MenuItem(menu, menu_id, label, kind=kind)
    if func is not None:
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)

    return item


def enum_window_callback(hwnd: int, _lparam: int, window_titles: list[str]) -> None:
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


def copy_bitmap_to_clipboard(data) -> None:
    """クリップボードにビットマップデータをコピーする"""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()


class ScreenShot(TaskBarIcon):
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
    # 設定ファイルパス
    CONFIG_FILE: str = f"{ver.INFO['APP_NAME']}.ini"
    # ヘルプファイル（現在未使用）
    HELP_FILE: str = "manual.html"

    MY_PICTURES: str = ""
    disable_hotkeys: bool = False

    def __init__(self, frame) -> None:
        self.frame = frame
        super().__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # プロパティ
        myss_cls = ScreenShot
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

    def initialize(self) -> None:
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
        self._app_icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(wx.BitmapBundle(self._app_icons.GetIcon(wx.Size(16, 16))), TRAY_TOOLTIP)
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
        self.set_capture_hotkey()
        # 定期実行停止用Hotkey展開、設定
        self.set_periodic_stop_hotkey()

    def remove_capture_hotkey(self) -> None:
        """キャプチャー用ホット・キー削除処理

        * 現在のキャプチャー用ホット・キーを削除する

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        for hotkey, _, _ in self.menu_clipboard:
            keyboard.remove_hotkey(hotkey)
        for hotkey, _, _ in self.menu_imagefile:
            keyboard.remove_hotkey(hotkey)

    def set_capture_hotkey(self) -> None:
        """キャプチャー用ホット・キー登録処理

        * キャプチャー用ホット・キーとメニューのアクセレーター文字列を展開する
        * キャプチャー用ホット・キーを登録する

        Args:
            none

        Returns:
            none

        """
        myss_cls = ScreenShot
        if myss_cls.disable_hotkeys:
            return

        # 設定値(prop)からキャプチャー用の修飾キーを取得し、それぞれのホット・キー文字列を展開する
        hk_clipbd: str = self.capture_hotkey_tbl[self.prop["hotkey_clipboard"]]
        hk_imagef: str = self.capture_hotkey_tbl[self.prop["hotkey_imagefile"]]

        # Menu, Hotkeyの情報を生成する（[0]:Hotkey, [1]:Menu ID, [2]:Menu name）
        self.menu_clipboard.clear()
        self.menu_imagefile.clear()
        disp: int = self.prop["display"]
        # デスクトップ[0]
        self.menu_clipboard.append(
            (f"{hk_clipbd}+0", myss_cls.ID_MENU_SCREEN0_CB, "0: デスクトップ"),
        )
        self.menu_imagefile.append((f"{hk_imagef}+0", myss_cls.ID_MENU_SCREEN0, "0: デスクトップ"))
        # ディスプレイ[1～]
        for n in range(1, disp + 1):
            self.menu_clipboard.append(
                (f"{hk_clipbd}+{n}", myss_cls.ID_MENU_SCREEN0_CB + n, f"{n}: ディスプレイ {n}"),
            )
            self.menu_imagefile.append(
                (f"{hk_imagef}+{n}", myss_cls.ID_MENU_SCREEN0 + n, f"{n}: ディスプレイ {n}"),
            )
        # アクティブウィンドウ
        self.menu_clipboard.append(
            (
                f"{hk_clipbd}+F{self.prop['hotkey_activewin'] + 1}",
                myss_cls.ID_MENU_ACTIVE_CB,
                f"{disp + 1}: アクティブウィンドウ",
            ),
        )
        self.menu_imagefile.append(
            (
                f"{hk_imagef}+F{self.prop['hotkey_activewin'] + 1}",
                myss_cls.ID_MENU_ACTIVE,
                f"{disp + 1}: アクティブウィンドウ",
            ),
        )

        # Hotkeyの登録（デスクトップ[0]、ディスプレイ[1～]、アクティブウィンドウ[last]）
        for n in range(len(self.menu_clipboard)):
            logger.debug(
                f"Hotkey[{n}]={self.menu_clipboard[n][0]}, {self.menu_imagefile[n][0]}, \
                    id={self.menu_clipboard[n][1]}, {self.menu_imagefile[n][1]}",
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

    def remove_periodic_stop_hotkey(self) -> None:
        """定期実行停止ホット・キー削除処理

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        keyboard.remove_hotkey(self.hotkey_periodic_stop)

    def set_periodic_stop_hotkey(self) -> None:
        """定期実行停止ホット・キー登録処理

        Args:
            none

        Returns:
            none

        """
        if ScreenShot.disable_hotkeys:
            return

        # 設定値(prop)からホット・キー文字列を展開する
        modifire: str = self.periodic_stop_hotkey_tbl[self.prop["periodic_stop_modifier"]]
        fkey: str = f"F{self.prop['periodic_stop_fkey'] + 1}"
        self.hotkey_periodic_stop = fkey if len(modifire) == 0 else f"{modifire}+{fkey}"
        keyboard.add_hotkey(
            self.hotkey_periodic_stop,
            lambda: wx.CallAfter(self.stop_periodic_capture),
        )

    def load_config(self) -> None:
        """設定値読み込み処理

        * 各種設定値を初期設定後、設定ファイルから読み込む。

        Args:
            none

        Returns:
            none

        """
        self.config = configparser.ConfigParser()
        result: bool = False
        try:
            with Path(ScreenShot.CONFIG_FILE).open(encoding="utf-8") as fc:
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
            self.config.read_dict(mydef.CONFIG_DEFAULT)

        if self.config_to_property():
            self.save_config()

    def save_config(self) -> None:
        """設定値保存処理

        * 各種設定値をファイルの書き込む。

        Args:
            none

        Returns:
            none

        """
        self.property_to_config()
        try:
            with Path(ScreenShot.CONFIG_FILE).open("w") as fc:
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
        myss_cls = ScreenShot
        save_req: bool = False
        # 自動保存
        self.prop["auto_save"] = self.config.getboolean("basic", "auto_save", fallback=True)
        # 自動保存フォルダ
        self.prop["save_folder_index"] = self.config.getint(
            "basic",
            "save_folder_index",
            fallback=-1,
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
            "other",
            "mouse_cursor",
            fallback=False,
        )
        self.prop["sound_on_capture"] = self.config.getboolean(
            "other",
            "sound_on_capture",
            fallback=False,
        )
        self.prop["delayed_capture"] = self.config.getboolean(
            "delayed_capture",
            "delayed_capture",
            fallback=False,
        )
        self.prop["delayed_time"] = self.config.getint(
            "delayed_capture",
            "delayed_time",
            fallback=5,
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
            "periodic",
            "save_folder",
            fallback=myss_cls.MY_PICTURES,
        )
        self.prop["periodic_interval"] = self.config.getint("periodic", "interval", fallback=3)
        self.prop["periodic_interval_ms"] = self.prop["periodic_interval"] * 1000
        self.prop["periodic_stop_modifier"] = self.config.getint(
            "periodic",
            "stop_modifier",
            fallback=0,
        )
        self.prop["periodic_stop_fkey"] = self.config.getint("periodic", "stop_fkey", fallback=11)
        self.prop["periodic_target"] = self.config.getint("periodic", "target", fallback=0)
        self.prop["periodic_numbering"] = self.config.getint("periodic", "numbering", fallback=0)
        if len(self.prop["periodic_save_folder"]) == 0:
            # 保存フォルダが無いので、"Pictures"を登録する
            self.prop["periodic_save_folder"] = myss_cls.MY_PICTURES
            save_req = True

        return save_req

    def property_to_config(self) -> None:
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
        myss_cls = ScreenShot
        # メニューの生成
        menu = wx.Menu()
        # バージョン情報
        item = create_menu_item(
            menu,
            myss_cls.ID_MENU_ABOUT,
            "バージョン情報...",
            self.on_menu_show_about,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_INFO)))
        menu.AppendSeparator()
        # 環境設定
        item = create_menu_item(
            menu,
            myss_cls.ID_MENU_SETTINGS,
            "環境設定...",
            self.on_menu_settings,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_SETTINGS)))
        # クイック設定
        sub_menu = wx.Menu()
        sub_item = create_menu_item(
            sub_menu,
            myss_cls.ID_MENU_MCURSOR,
            "マウスカーソルをキャプチャーする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        # Windowsでは現状マウスカーソルがキャプチャー出来ないので「無効」にしておく
        sub_item.Enable(enable=False)
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
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_QUICK_SETTINGS)))
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
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_AUTO_SAVE_FOLDER)))
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
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_OPEN_FOLDER)))
        menu.AppendSeparator()
        # 定期実行設定
        item = create_menu_item(
            menu,
            myss_cls.ID_MENU_PERIODIC,
            "定期実行設定...",
            self.on_menu_periodic_settings,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_PERIODIC)))
        menu.AppendSeparator()
        # キャプチャー（クリップボード、PNGファイル）
        # display_count: int = self.prop["display"]
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
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_COPY_TO_CB)))
        item = menu.AppendSubMenu(sub_menu2, "PNGファイルへ保存")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_SAVE_TO_PNG)))
        menu.AppendSeparator()
        # 終了
        item = create_menu_item(menu, myss_cls.ID_MENU_EXIT, "終了", self.on_menu_exit)
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(myss_cls.ICON_EXIT)))

        return menu

    def image_trim(self, image: Image.Image) -> Image.Image:
        """キャプチャー画像のトリミング"""
        width, height = image.size

        top: int = self.prop["trimming_size"][0]
        temp_bottom: int = self.prop["trimming_size"][1]
        left: int = self.prop["trimming_size"][2]
        temp_right: int = self.prop["trimming_size"][3]
        right: int = (width - temp_right) if width > temp_right else width
        bottom: int = (height - temp_bottom) if height > temp_bottom else height

        logger.debug(f"Trimming ({top}, {left})-({right}, {bottom})")
        return image.crop((left, top, right, bottom))

    def capture_screen(self, moni_no: int) -> Image.Image:
        """キャプチャー処理"""
        with mss.mss() as sct:
            area_coord: dict = {}

            if moni_no == 90 and (info := get_active_window()) is not None:  # アクティブウィンドウ
                window_title, area_coord = info
                logger.debug(f"Capture 'Active window - [{window_title}]', {area_coord}")

            elif 0 <= moni_no < len(sct.monitors):
                area_coord = sct.monitors[moni_no]
                logger.debug(f"Capture 'Desktop'" if moni_no == 0 else f"'Display-{moni_no}'")

            if len(area_coord):
                if (sct_img := sct.grab(area_coord)) is not None:
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            else:
                self._beep.Play()

        return img

    def do_capture(self) -> None:
        """キャプチャー実行

        * Queueの要求に従い、キャプチャー画像を処理する

        Args:
            none

        Returns:
            none

        """
        moni_no, filename = self.req_queue.get()
        logger.debug(f"do_capture {moni_no=}, {filename=}")

        if (img := self.capture_screen(moni_no)) is not None:
            logger.debug(
                f"Captured image has been {'copied to clipboard' if len(filename) == 0 else 'saved to a {filename}'}",
            )
            # トリミング（アクティブウィンドウ以外はトリミングしない）
            if moni_no == 90 and self.prop["trimming"]:
                img = self.image_trim(img)

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
        else:
            logger.error("Can not captured!")

    def on_menu_show_about(self, _event) -> None:
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
            f" Ver.{ver.INFO['VERSION']}\n on Python {self._platform_info[2]} and wxPython {wx.__version__}.",
        )
        info.SetCopyright(ver.COPYRIGHT["COPYRIGHT"])
        info.SetDescription(f"{ver.INFO['FILE_DESCRIPTION']}\n(Nuitka+MSVCによるEXE化.)")
        info.SetLicense(ver.COPYRIGHT["LICENSE"])
        # info.SetWebSite("")
        info.AddDeveloper(ver.COPYRIGHT["AUTHOR"])
        # 表示する
        AboutBox(info, self.frame)

    def on_menu_settings(self, _event) -> None:
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
                    self.prop["save_folders"][self.prop["save_folder_index"]] if not self.prop["save_folder_index"] < 0 else ""
                )
                numbering: int = self.prop["numbering"]
                prefix: str = self.prop["prefix"]
                digits: int = self.prop["sequence_digits"]
                begin: int = self.prop["sequence_begin"]
                hotkey_clipboard: int = self.prop["hotkey_clipboard"]
                hotkey_activewin: int = self.prop["hotkey_activewin"]
                dlg.get_prop(self.prop)  # ダイアログの設定状態を取得する

                new_save_folder: str = (
                    self.prop["save_folders"][self.prop["save_folder_index"]] if not self.prop["save_folder_index"] < 0 else ""
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
                if hotkey_clipboard != self.prop["hotkey_clipboard"] or hotkey_activewin != self.prop["hotkey_activewin"]:
                    self.remove_capture_hotkey()
                    self.set_capture_hotkey()
                    logger.debug("Change capture Hotkey.")

    def on_menu_toggle_item(self, event) -> None:
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
        myss_cls = ScreenShot
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

    def on_menu_reset_sequence(self, _event) -> None:
        """シーケンス番号のリセット

        * 現在保持している次のシーケンス番号をリセットする。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.sequence = -1

    def on_menu_select_save_folder(self, event) -> None:
        """Select save folderメニューイベントハンドラ

        * 自動保存フォルダーを切り替える。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        # old: int = self.prop["save_folder_index"]
        menu_id: int = event.GetId()
        for n in range(len(self.prop["save_folders"])):
            if menu_id == (ScreenShot.ID_MENU_FOLDER1 + n):
                self.prop["save_folder_index"] = n
                break

    def on_menu_open_folder(self, event) -> None:
        """Open folderメニューイベントハンドラ

        * 自動または定期保存フォルダーを開く。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        folder: str = (
            self.prop["save_folders"][self.prop["save_folder_index"]]
            if event.GetId() == ScreenShot.ID_MENU_OPEN_AUTO
            else self.prop["periodic_save_folder"]
        )
        if Path(folder).exists():
            # ruff: noqa: S606
            os.startfile(folder)

    def on_menu_periodic_settings(self, _event) -> None:
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
                    if stop_modifier != self.prop["periodic_stop_modifier"] or fkey != self.prop["periodic_stop_fkey"]:
                        self.remove_periodic_stop_hotkey()
                        self.set_periodic_stop_hotkey()
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

    def stop_periodic_capture(self) -> None:
        """定期実行停止処理"""
        # 実行停止
        self.prop["periodic_capture"] = False
        logger.debug("Stop periodic capture")
        if self.prop["sound_on_capture"]:
            self._success.Play()

    # ruff: noqa: FBT001, FBT002
    def create_filename(self, periodic: bool = False) -> str:
        """PNGファイル名生成処理

        * PNGファイル名を生成する。

        Args:
            periodic (bool): True=定期実行向け

        Returns:
            PNGファイル名 (str)

        """
        # 選択中の保存フォルダを取得する
        path: str = self.prop["periodic_save_folder"] if periodic else self.prop["save_folders"][self.prop["save_folder_index"]]
        if not Path(path).exists():
            wx.MessageBox(f"保存フォルダ '{path}' が見つかりません。", "ERROR", wx.ICON_ERROR)
            return ""

        # ナンバリング種別を取得する
        kind: int = (
            self.prop["numbering"]
            if not periodic
            else (self.prop["periodic_numbering"] if self.prop["periodic_numbering"] == 0 else self.prop["numbering"])
        )
        if kind == 0:  # 日時
            filename: str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S") + ".png"
        else:  # 接頭語＋シーケンス番号
            prefix: str = self.prop["prefix"]
            prefix_len: int = len(prefix)
            digits: int = self.prop["sequence_digits"]
            begin: int = max(self.prop["sequence_begin"], self.sequence)
            logger.debug(f"Sequence No.={begin}")

            filename = f"{prefix}{begin:0>{digits}}.png"
            if Path(Path(path) / filename).exists():
                # 現在のシーケンス番号のファイルが存在した場合、空きを探す
                ptn: str = rf"{prefix}\d{{{digits}}}\.png"
                files: list[str] = scan_directory(path, pattern=ptn)
                if not files:
                    # 存在しない -> プレフィックス＋開始番号
                    logger.debug("Sequencial file not found.")
                    filename = f"{prefix}{begin:0>{digits}}.png"
                else:
                    # ファイル名からシーケンス番号のlistを作る
                    nums: list[int] = [int(str(Path(file).name)[prefix_len : prefix_len + digits]) for file in files]
                    logger.debug(f"Sequencial No. list is {nums}")
                    # 空きを確認
                    # snos: list[int] = [y - 1 for x, y in zip(nums, nums[1:], strict=False) if x != y - 1 and y - 1 >= begin]
                    snos: list[int] = [y - 1 for x, y in pairwise(nums) if x != y - 1 and y - 1 >= begin]
                    # 空きがなければシーケンス番号の最大値+1
                    begin = snos[0] if snos else nums[len(nums) - 1] + 1
                    logger.debug(f"Sequence No. changed to {begin}")
                    filename = f"{prefix}{begin:0>{digits}}.png"
            else:
                logger.debug(f"No duplicates '{filename}'")

            self.sequence = begin + 1  # 次回のシーケンス番号
            logger.debug(f"Next sequence No.={self.sequence}")

        return str(Path(path) / filename)

    def do_periodic(self) -> None:
        """定期実行処理

        Args:
            none

        Returns:
            none

        """
        if self.prop["periodic_capture"]:
            # ターゲットを取得
            moni_no: int = self.prop["periodic_target"] if self.prop["periodic_target"] != -1 else 90
            filename: str = self.create_filename(periodic=True)
            self.req_queue.put((moni_no, filename))
            wx.CallAfter(self.do_capture)
            # 次回を予約
            wx.CallLater(self.prop["periodic_interval_ms"], self.do_periodic)

    def copy_to_clipboard(self, menu_id: int, from_menu: bool = True) -> None:
        """キャプチャー要求処理（Clipboardコピー）

        * メニューとホット・キーイベントから呼ばれる

        Args:
            menu_id (int): EVENT(Menu) ID
            from_menu (bool): True = Menuから

        Returns:
            none

        """
        myss_cls = ScreenShot
        # ターゲット取得
        moni_no: int = 90 if menu_id == myss_cls.ID_MENU_ACTIVE_CB else (menu_id - myss_cls.ID_MENU_SCREEN0_CB)
        self.req_queue.put((moni_no, ""))
        # 遅延時間算出（遅延キャプチャー以外でメニュー経由は"BASE_DELAY_TIME"遅延させる）
        delay_ms: int = (
            self.prop["delayed_time_ms"] if self.prop["delayed_capture"] else 0 if not from_menu else myss_cls.BASE_DELAY_TIME
        )
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def save_to_imagefile(self, menu_id: int, from_menu: bool = True) -> None:
        """キャプチャー要求処理（PNGファイル保存）

        * メニューとホット・キーイベントから呼ばれる

        Args:
            menu_id (int): EVENT(Menu) ID
            from_menu (bool): True = Menuから

        Returns:
            none

        """
        myss_cls = ScreenShot
        # ターゲット取得
        moni_no: int = 90 if menu_id == myss_cls.ID_MENU_ACTIVE else (menu_id - myss_cls.ID_MENU_SCREEN0)
        # 保存ファイル名生成
        filename: str = self.create_filename(self.prop["periodic_capture"])
        if len(filename) == 0:
            return

        self.req_queue.put((moni_no, filename))
        delay_ms: int = (
            self.prop["delayed_time_ms"] if self.prop["delayed_capture"] else 0 if not from_menu else myss_cls.BASE_DELAY_TIME
        )
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def on_menu_clipboard(self, event) -> None:
        """クリップボードへコピーメニューイベントハンドラ

        * キャプチャー画像(BMP)をClipboardへコピーする。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.copy_to_clipboard(event.GetId())

    def on_menu_imagefile(self, event) -> None:
        """Save to PNG fileメニューイベントハンドラ

        * キャプチャー画像をPNGファイルとして保存する。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.save_to_imagefile(event.GetId())

    def on_menu_exit(self, _event) -> None:
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


class SettingsDialog(SettingsDialogBase):
    """環境設定ダイアログ（wxGladeで、設計&生成）"""

    # ruff: noqa: ANN001, ANN002, ANN003
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))

    def on_save_folder_add(self, event) -> None:
        """自動保存フォルダの追加"""
        myss_cls = ScreenShot
        if self.list_box_auto_save_folders.Count >= myss_cls.MAX_SAVE_FOLDERS:
            wx.MessageBox(
                f"{myss_cls.MAX_SAVE_FOLDERS}以上は登録できません。",
                "警告",
                wx.ICON_WARNING,
            )
        else:
            default_path: str = str(Path.cwd())
            agwstyle: int = mdd.DD_MULTIPLE | mdd.DD_DIR_MUST_EXIST
            with mdd.MultiDirDialog(
                None,
                title="フォルダの追加",
                defaultPath=default_path,
                agwStyle=agwstyle,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                # 選択されたフォルダをListBoxに追加する
                paths: list = dlg.GetPaths()
                for folder in paths:
                    self.list_box_auto_save_folders.Append(folder)
        event.Skip()

    def on_save_folder_del(self, event) -> None:
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

    def on_save_folder_move(self, event) -> None:
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
                movable = index > 0
            else:
                move = 1
                movable = index < (count - 1)

            if movable:
                folder: str = self.list_box_auto_save_folders.GetString(index)
                self.list_box_auto_save_folders.Delete(index)
                self.list_box_auto_save_folders.Insert(folder, index + move)
                self.list_box_auto_save_folders.SetSelection(index + move)
        event.Skip()

    """ HotKey: 修飾キーの切り替え制御 """

    def on_btn_hotkey_change(self, event) -> None:
        match event.GetId():
            case self.BTN_ID_BMP_CTRL_ALT:
                self.radio_btn_hotkey_png_ctrl_shift.SetValue(value=True)
            case self.BTN_ID_BMP_CTRL_SHIFT:
                self.radio_btn_hotkey_png_ctrl_alt.SetValue(value=True)
            case self.BTN_ID_PNG_CTRL_ALT:
                self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(value=True)
            case self.BTN_ID_PNG_CTRL_SHIFT:
                self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(value=True)
            case _:
                pass
        event.Skip()

    def set_prop(self, prop: dict) -> None:
        """設定値をコントロールに反映する"""
        # --- 基本設定
        # 自動/手動
        if prop["auto_save"]:
            self.radio_btn_auto_save.SetValue(value=True)
        else:
            self.radio_btn_inquire_allways.SetValue(value=True)
        # 自動保存フォルダ
        for folder in prop["save_folders"]:
            self.list_box_auto_save_folders.Append(folder)
        self.list_box_auto_save_folders.SetSelection(prop["save_folder_index"])
        # ナンバリング
        if prop["numbering"] == 0:
            self.radio_btn_numbering_datetime.SetValue(value=True)
        else:
            self.radio_btn_nubering_prefix_sequence.SetValue(value=True)
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
            self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(value=True)
            self.radio_btn_hotkey_png_ctrl_shift.SetValue(value=True)
        else:
            self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(value=True)
            self.radio_btn_hotkey_png_ctrl_alt.SetValue(value=True)
        # ターゲット
        self.choice_hotkey_active_window.SetSelection(prop["hotkey_activewin"])
        # その他
        ScreenShot.MAX_SAVE_FOLDERS = prop["MAX_SAVE_FOLDERS"]

    def get_prop(self, prop: dict) -> None:
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


class PeriodicDialog(PeriodicDialogBase):
    """定期実行設定ダイアログ（wxGladeで、設計&生成）"""

    # ruff: noqa: ANN001, ANN002, ANN003
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))

    def on_save_folder_browse(self, event) -> None:
        """保存フォルダの選択"""
        default_path: str = self.text_ctrl_periodic_folder.GetValue()
        if len(default_path) == 0 or not Path(default_path).exists():
            default_path = str(Path.cwd())
        agwstyle: int = mdd.DD_MULTIPLE | mdd.DD_DIR_MUST_EXIST
        with mdd.MultiDirDialog(
            None,
            title="フォルダの選択",
            defaultPath=default_path,
            agwStyle=agwstyle,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            paths: list = dlg.GetPaths()
            for folder in paths:
                self.text_ctrl_periodic_folder.SetValue(folder)
        event.Skip()

    def on_periodic_capture_ctrl(self, event) -> None:
        self.EndModal(event.GetId())
        event.Skip()

    def set_prop(self, prop: dict) -> None:
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
                item,
                self.choice_periodic_capture_target.GetCount() - 1,
            )
        if prop["periodic_target"] == -1:
            self.choice_periodic_capture_target.SetSelection(
                self.choice_periodic_capture_target.GetCount() - 1,
            )
        else:
            self.choice_periodic_capture_target.SetSelection(prop["periodic_target"])
        # ナンバリング
        if prop["periodic_numbering"] == 0:
            self.radio_btn_periodic_numbering_datetime.SetValue(value=True)
        else:
            self.radio_btn_periodic_numbering_autosave.SetValue(value=True)

    def get_prop(self, prop: dict) -> None:
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


class App(wx.App):
    # ruff: noqa: N802
    def OnInit(self) -> bool:
        self.name = f"{ver.INFO['APP_NAME']}"
        self.instance = wx.SingleInstanceChecker(self.name)
        if self.instance.IsAnotherRunning():
            wx.MessageBox(f"'{self.name}'は既に実行中です", "エラー", wx.ICON_ERROR)
            return False

        frame = wx.Frame(None)
        frame.Centre()  # AboutBoxをプライマリディスプレイの中心に出すため
        self.SetTopWindow(frame)
        ScreenShot(frame)

        return True


def app_init() -> bool:
    """実行時PATH等初期化

    * 設定ファイル、リソースファイルのPATHを取得等

    Args:
        none

    Returns:
        none

    """
    # 実行ファイルPATHを設定
    exe_path = str(Path(sys.argv[0]).parent)
    exe_path = "." + os.sep if len(exe_path) == 0 else exe_path
    # マイピクチャのPATHを取得
    ScreenShot.MY_PICTURES = get_special_directory()[2]

    # 設定ファイルは実行ファイル（スクリプト）ディレクトリ下
    ScreenShot.CONFIG_FILE = str(Path(exe_path) / ScreenShot.CONFIG_FILE)
    ScreenShot.HELP_FILE = str(Path(exe_path) / ScreenShot.HELP_FILE)

    if not Path(ScreenShot.CONFIG_FILE).exists():
        # 設定ファイルが存在しない場合は、デフォルト設定で作成
        logger.warning("設定ファイルがありません。デフォルト設定で作成します。")
        config = configparser.ConfigParser()
        config.read_dict(mydef.CONFIG_DEFAULT)
        try:
            with Path(ScreenShot.CONFIG_FILE).open("w") as fc:
                config.write(fc)

        except OSError as e:
            logger.warning(f"設定ファイルが作成できません。({e.errno})")
            return False

    return True


if __name__ == "__main__":
    # コマンドラインパラメータの取得
    parser = argparse.ArgumentParser(description="My ScreenSHot Tool.")
    parser.add_argument("--debug", action="store_true", help="Debug mode.")
    parser.add_argument("--disable-hotkeys", action="store_true", help="Disable Hot Keys.")
    args = parser.parse_args()
    # ホット・キーの有効/無効設定
    ScreenShot.disable_hotkeys = args.disable_hotkeys

    # ログ設定
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level)
    handler = logging.handlers.RotatingFileHandler(
        filename=f"{ver.INFO['APP_NAME']}.log",
        maxBytes=1048576,
        backupCount=3,
        encoding="utf-8",
    )
    FORMAT_TML: str = "%(asctime)s.%(msecs)03d [%(levelname)-8s]"
    FORMAT_DBG = "[%(filename)s:%(lineno)d]"
    FORMAT_MSG = "%(message)s"
    FORMAT = f"{FORMAT_TML} {FORMAT_DBG} {FORMAT_MSG}" if args.debug else f"{FORMAT_TML} {FORMAT_MSG}"
    handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(handler)

    # 初期化
    if not app_init():
        sys.exit()

    logger.info("=== Start ===")

    app = App()
    app.MainLoop()

    logger.info("=== Finish ===")
