#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
"""PyScreenShot

スクリーンショットアプリケーション

"""

import argparse
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from queue import Queue
from zoneinfo import ZoneInfo

import wx
from screeninfo import get_monitors
from wx.adv import (
    EVT_TASKBAR_LEFT_DCLICK,
    AboutBox,
    AboutDialogInfo,
    TaskBarIcon,
)

import version as ver
from app_settings import AppSettings
from capture_manager import CaptureManager
from config_manager import ConfigManager
from dialogs import PeriodicDialog, SettingsDialog
from hotkey_manager import HotkeyManager
from myutils.util import (
    get_special_directory,
    platform_info,
    scan_directory,
)
from res import app_icon, menu_image

logger = logging.getLogger(__name__)

# APP_KEY: str = Path(__file__).stem if __name__ == "__main__" else __name__

TRAY_TOOLTIP: str = f"{ver.INFO['APP_NAME']} App"


def create_menu_item(
    menu: wx.Menu,
    menu_id: int = -1,
    label: str = "",
    func: wx.Menu.Bind.handler = None,
    kind: wx.ItemKind = wx.ITEM_NORMAL,
) -> wx.MenuItem:
    """MenuItemの作成"""
    item = wx.MenuItem(menu, menu_id, label, kind=kind)
    if func is not None:
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
    menu.Append(item)

    return item


class ScreenShot(TaskBarIcon):
    # fmt: off
    #--- Menu IDs
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
    # 保存先フォルダ(Base)
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
    #--- ICON Index for ImageList
    ICON_INFO             = 0
    ICON_SETTINGS         = 1
    ICON_QUICK_SETTINGS   = 2
    ICON_AUTO_SAVE_FOLDER = 3
    ICON_OPEN_FOLDER      = 4
    ICON_PERIODIC         = 5
    ICON_COPY_TO_CB       = 6
    ICON_SAVE_TO_PNG      = 7
    ICON_EXIT             = 8
    #--- Other constants
    BASE_DELAY_TIME: int = 400   # (ms)
    MAX_SAVE_FOLDERS: int = 64
    # fmt: on

    # 設定ファイルパス
    CONFIG_FILE: Path = Path()
    # ヘルプファイル（現在未使用）
    HELP_FILE: Path = Path()

    MY_PICTURES: Path = Path()
    disable_hotkeys: bool = False

    def __init__(self, frame: wx.Frame) -> None:
        self.frame = frame
        super().__init__()
        self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_menu_settings)
        # ディスプレイ数取得
        self.display_count = len(get_monitors())

        # 設定管理オブジェクト生成
        self.config = ConfigManager(ScreenShot.CONFIG_FILE, ScreenShot.MY_PICTURES, ScreenShot.MAX_SAVE_FOLDERS)
        self.settings = AppSettings()
        # キャプチャー管理、サウンド管理オブジェクト生成
        self.capture = CaptureManager()
        # ホット・キー管理オブジェクト生成
        self.hotkey = HotkeyManager()

        # キャプチャーHotkeyアクセレーターリスト（0:デスクトップ、1～:ディスプレイ、last:アクティブウィンドウ）
        self.menu_clipboard: list[tuple] = []
        self.menu_imagefile: list[tuple] = []
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
        # Load Application ICON
        self._app_icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(wx.BitmapBundle(self._app_icons.GetIcon(wx.Size(16, 16))), TRAY_TOOLTIP)
        # 設定値の初期設定
        self.config.config_from_settings(self.settings)
        # 設定ファイルの読み込み
        if not self.config.load():
            logger.warning(f"設定ファイルの読み込み/解析に失敗しました。")
        # メニューアイコン画像の展開
        w, h = menu_image.image_size
        self._icon_img = wx.ImageList(w, h)
        for name in menu_image.index:
            self._icon_img.Add(menu_image.catalog[name].GetBitmap())

        # キャプチャーHotkeyアクセレーター展開、設定
        self.add_caputure_hotkeys()
        # 定期実行停止用Hotkey展開、設定
        self.add_periodic_stop_hotkey()

    def add_caputure_hotkeys(self) -> None:
        """キャプチャー用ホット・キー登録処理

        * キャプチャー用ホット・キーとメニューのアクセレーター文字列を展開する
        * キャプチャー用ホット・キーを登録する

        Args:
            none

        Returns:
            none

        """
        if ScreenShot.disable_hotkeys:
            return

        # 設定値(prop)からキャプチャー用の修飾キーを取得し、それぞれのホット・キー文字列を展開する
        # hk_clipbd: str = self.capture_hotkey_tbl[self.settings.hotkey_clipboard]
        hk_clipbd: str = self.hotkey.get_capture_hotkey(self.settings.hotkey_clipboard)
        # hk_imagef: str = self.capture_hotkey_tbl[self.settings.hotkey_imagefile]
        hk_imagef: str = self.hotkey.get_capture_hotkey(self.settings.hotkey_imagefile)

        # Menu, Hotkeyの情報を生成する（[0]:Hotkey, [1]:Menu ID, [2]:Menu name）
        self.menu_clipboard.clear()
        self.menu_imagefile.clear()
        disp: int = self.display_count
        # デスクトップ[0]
        self.menu_clipboard.append((f"{hk_clipbd}+0", ScreenShot.ID_MENU_SCREEN0_CB, "0: デスクトップ"))
        self.menu_imagefile.append((f"{hk_imagef}+0", ScreenShot.ID_MENU_SCREEN0, "0: デスクトップ"))
        # ディスプレイ[1～]
        for n in range(1, disp + 1):
            self.menu_clipboard.append((f"{hk_clipbd}+{n}", ScreenShot.ID_MENU_SCREEN0_CB + n, f"{n}: ディスプレイ {n}"))
            self.menu_imagefile.append((f"{hk_imagef}+{n}", ScreenShot.ID_MENU_SCREEN0 + n, f"{n}: ディスプレイ {n}"))
        # アクティブウィンドウ
        fkey: int = self.settings.hotkey_activewin + 1
        self.menu_clipboard.append(
            (f"{hk_clipbd}+F{fkey}", ScreenShot.ID_MENU_ACTIVE_CB, f"{disp + 1}: アクティブウィンドウ"),
        )
        self.menu_imagefile.append(
            (f"{hk_imagef}+F{fkey}", ScreenShot.ID_MENU_ACTIVE, f"{disp + 1}: アクティブウィンドウ"),
        )

        # Hotkeyの登録（デスクトップ[0]、ディスプレイ[1～]、アクティブウィンドウ[last]）
        for n in range(len(self.menu_clipboard)):
            hotkey_clipboard, id_clipboard, _ = self.menu_clipboard[n]
            hotkey_imagefile, id_imagefile, _ = self.menu_imagefile[n]

            logger.debug(f"Hotkey[{n}]={hotkey_clipboard}, {hotkey_imagefile}, id={id_clipboard}, {id_imagefile}")
            self.hotkey.add_clipboard(hotkey_clipboard, id_clipboard, self.copy_to_clipboard)
            self.hotkey.add_imagefile(hotkey_imagefile, id_imagefile, self.save_to_imagefile)

    def remove_capture_hotkey(self) -> None:
        """キャプチャー用ホット・キー削除処理

        * 現在のキャプチャー用ホット・キーを削除する

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        self.hotkey.remove_capture()

    def add_periodic_stop_hotkey(self) -> None:
        """定期実行停止ホット・キー登録処理

        Args:
            none

        Returns:
            none

        """
        if ScreenShot.disable_hotkeys:
            return

        # 設定値(prop)からホット・キー文字列を展開する
        # modifire: str = self.periodic_stop_hotkey_tbl[self.settings.periodic_stop_modifier]
        modifire: str = self.hotkey.get_periodic_stop_hotkey(self.settings.periodic_stop_modifier)
        fkey: str = f"F{self.settings.periodic_stop_fkey + 1}"

        self.hotkey.add_periodic_stop(fkey if len(modifire) == 0 else f"{modifire}+{fkey}", self.stop_periodic_capture)

    def remove_periodic_stop_hotkey(self) -> None:
        """定期実行停止ホット・キー削除処理

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        self.hotkey.remove_periodic_stop()

    def CreatePopupMenu(self) -> wx.Menu:
        """Popupメニューの生成 (override)

        * タスクトレイアイコンを右クリックした際に、Popupメニューを生成して表示する
        * 現バージョンでは生成したメニューが破棄されて再利用できない。

        Args:
            none

        Returns:
            wx.Menuオブジェクト

        """
        # メニューの生成
        menu = wx.Menu()
        # バージョン情報
        item = create_menu_item(
            menu,
            ScreenShot.ID_MENU_ABOUT,
            "バージョン情報...",
            self.on_menu_show_about,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_INFO)))
        menu.AppendSeparator()
        # 環境設定
        item = create_menu_item(
            menu,
            ScreenShot.ID_MENU_SETTINGS,
            "環境設定...",
            self.on_menu_settings,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_SETTINGS)))
        # クイック設定
        sub_menu = wx.Menu()
        sub_item = create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_MCURSOR,
            "マウスカーソルをキャプチャーする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        # Windowsでは現状マウスカーソルがキャプチャー出来ないので「無効」にしておく
        sub_item.Enable(enable=False)
        sub_item = create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_SOUND,
            "キャプチャー終了時に音を鳴らす",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.settings.sound_on_capture)
        sub_item = create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_DELAYED,
            "遅延キャプチャーをする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.settings.delayed_capture)
        sub_item = create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_TRIMMING,
            "トリミングをする",
            self.on_menu_toggle_item,
            kind=wx.ITEM_CHECK,
        )
        sub_item.Check(self.settings.trimming)
        sub_item = create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_RESET,
            "シーケンス番号のリセット",
            self.on_menu_reset_sequence,
        )
        item = menu.AppendSubMenu(sub_menu, "クイック設定")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_QUICK_SETTINGS)))
        menu.AppendSeparator()
        # 保存フォルダ
        sub_menu = wx.Menu()
        for n, folder in enumerate(self.settings.save_folders):
            sub_item = create_menu_item(
                sub_menu,
                ScreenShot.ID_MENU_FOLDER1 + n,
                f"{n + 1}: {folder}",
                self.on_menu_select_save_folder,
                kind=wx.ITEM_RADIO,
            )
            if n == self.settings.save_folder_index:
                sub_item.Check()
        item = menu.AppendSubMenu(sub_menu, "保存先フォルダ")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_AUTO_SAVE_FOLDER)))
        # フォルダを開く
        sub_menu = wx.Menu()
        create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_OPEN_AUTO,
            "1: 自動保存先フォルダ(選択中)",
            self.on_menu_open_folder,
        )
        create_menu_item(
            sub_menu,
            ScreenShot.ID_MENU_OPEN_PERIODIC,
            "2: 定期実行フォルダ",
            self.on_menu_open_folder,
        )
        item = menu.AppendSubMenu(sub_menu, "フォルダを開く")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_OPEN_FOLDER)))
        menu.AppendSeparator()
        # 定期実行設定
        item = create_menu_item(
            menu,
            ScreenShot.ID_MENU_PERIODIC,
            "定期実行設定...",
            self.on_menu_periodic_settings,
        )
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_PERIODIC)))
        menu.AppendSeparator()
        # キャプチャー（クリップボード、PNGファイル）
        sub_menu1 = wx.Menu()
        sub_menu2 = wx.Menu()
        for n in range(len(self.menu_clipboard)):
            create_menu_item(
                sub_menu1,
                self.menu_clipboard[n][1],
                f"{self.menu_clipboard[n][2]}\t{self.menu_clipboard[n][0] if not ScreenShot.disable_hotkeys else ''}",
                self.on_menu_clipboard,
            )
            create_menu_item(
                sub_menu2,
                self.menu_imagefile[n][1],
                f"{self.menu_imagefile[n][2]}\t{self.menu_imagefile[n][0] if not ScreenShot.disable_hotkeys else ''}",
                self.on_menu_imagefile,
            )
        item = menu.AppendSubMenu(sub_menu1, "クリップボードへコピー")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_COPY_TO_CB)))
        item = menu.AppendSubMenu(sub_menu2, "PNGファイルへ保存")
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_SAVE_TO_PNG)))
        menu.AppendSeparator()
        # 終了
        item = create_menu_item(menu, ScreenShot.ID_MENU_EXIT, "終了", self.on_menu_exit)
        item.SetBitmap(wx.BitmapBundle(self._icon_img.GetBitmap(ScreenShot.ICON_EXIT)))

        return menu

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

        try:
            self.capture.execute_capture(
                moni_no=moni_no,
                filename=filename,
                settings=self.settings,
            )
            logger.debug(
                f"Capture request completed for {filename if filename else 'clipboard'}",
            )
        except Exception:
            logger.exception(f"Capture failed")

    def on_menu_show_about(self, _event: wx.Event) -> None:
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

    def on_menu_settings(self, _event: wx.Event) -> None:
        """Settingメニューイベントハンドラ

        * 環境設定ダイヤログを表示する。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        with SettingsDialog(self.frame, wx.ID_ANY, "") as dlg:
            dlg.set_prop(self.settings, ScreenShot.MAX_SAVE_FOLDERS)  # 設定値をダイアログ側へ渡す
            # 設定ダイアログを表示する
            if dlg.ShowModal() == wx.ID_OK:
                # Keep a copy of old settings for comparison
                old_settings = AppSettings(**self.settings.__dict__)

                dlg.get_prop(self.settings)  # ダイアログの設定状態を取得する

                new_save_folder: str = (
                    self.settings.save_folders[self.settings.save_folder_index]
                    if not self.settings.save_folder_index < 0
                    else ""
                )
                old_save_folder: str = (
                    old_settings.save_folders[old_settings.save_folder_index] if not old_settings.save_folder_index < 0 else ""
                )
                # 自動保存に変更 or 保存フォルダが変更 or (ナンバリングがシーケンス番号に変更) or
                # (接頭語が変更) or シーケンス桁数が変更 or 開始番号が変更 なら
                # 次回シーケンス番号をリセット
                auto_save_change: bool = old_settings.auto_save != self.settings.auto_save and self.settings.auto_save
                save_folder_change: bool = old_save_folder != new_save_folder
                numbering_change: bool = old_settings.numbering != self.settings.numbering and self.settings.numbering == 1
                prefix_change: bool = old_settings.prefix != self.settings.prefix
                sequence_change: bool = self.settings.numbering == 1 and (
                    (old_settings.sequence_digits != self.settings.sequence_digits)
                    or (old_settings.sequence_begin != self.settings.sequence_begin)
                )
                if auto_save_change or save_folder_change or numbering_change or prefix_change or sequence_change:
                    self.sequence = -1
                    logger.debug("Reset sequence No.")
                # キャプチャーHotkeyが変更されたら再登録
                if (
                    old_settings.hotkey_clipboard != self.settings.hotkey_clipboard
                    or old_settings.hotkey_activewin != self.settings.hotkey_activewin
                ):
                    self.remove_capture_hotkey()
                    self.add_caputure_hotkeys()
                    logger.debug("Change capture Hotkey.")

    def on_menu_toggle_item(self, event: wx.Event) -> None:
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
            case ScreenShot.ID_MENU_MCURSOR:  # マウスカーソルキャプチャー
                self.settings.capture_mcursor = not self.settings.capture_mcursor
            case ScreenShot.ID_MENU_SOUND:  # キャプチャー終了時に音を鳴らす
                self.settings.sound_on_capture = not self.settings.sound_on_capture
            case ScreenShot.ID_MENU_DELAYED:  # 遅延キャプチャー
                self.settings.delayed_capture = not self.settings.delayed_capture
            case ScreenShot.ID_MENU_TRIMMING:  # トリミング
                self.settings.trimming = not self.settings.trimming
            case _:
                pass

    def on_menu_reset_sequence(self, _event: wx.Event) -> None:
        """シーケンス番号のリセット

        * 現在保持している次のシーケンス番号をリセットする。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.sequence = -1

    def on_menu_select_save_folder(self, event: wx.Event) -> None:
        """Select save folderメニューイベントハンドラ

        * 自動保存フォルダーを切り替える。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        # old: int = self.prop["save_folder_index"]
        menu_id: int = event.GetId()
        for n in range(len(self.settings.save_folders)):
            if menu_id == (ScreenShot.ID_MENU_FOLDER1 + n):
                self.settings.save_folder_index = n
                break

    def on_menu_open_folder(self, event: wx.Event) -> None:
        """Open folderメニューイベントハンドラ

        * 自動または定期保存フォルダーを開く。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        folder_str: str = (
            self.settings.save_folders[self.settings.save_folder_index]
            if event.GetId() == ScreenShot.ID_MENU_OPEN_AUTO
            else self.settings.periodic_save_folder
        )
        folder_path = Path(folder_str)
        if folder_path.exists():
            # ruff: noqa: S606
            os.startfile(folder_path)

    def on_menu_periodic_settings(self, _event: wx.Event) -> None:
        """Periodic settingsメニューイベントハンドラ

        * 定期実行設定ダイヤログを表示する。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        with PeriodicDialog(self.frame, wx.ID_ANY, "") as dlg:
            # 設定値をダイアログ側へ渡す
            dlg.set_prop(self.settings)
            # 設定ダイアログを表示する
            match dlg.ShowModal():
                case wx.ID_EXECUTE | wx.ID_OK:
                    # 前回値としてコピー
                    old_settings = AppSettings(**self.settings.__dict__)
                    dlg.get_prop(self.settings)  # ダイアログの設定状態を取得する

                    # 保存フォルダが変更 or ナンバリングがシーケンス番号に変更 なら
                    # 次回シーケンス番号をリセット
                    save_folder_change: bool = old_settings.periodic_save_folder != self.settings.periodic_save_folder
                    numbering_change: bool = (
                        old_settings.periodic_numbering != self.settings.periodic_numbering
                        and self.settings.periodic_numbering == 1
                        and self.settings.numbering == 1
                    )
                    if save_folder_change or numbering_change:
                        self.sequence = -1
                        logger.debug("Reset sequence No.")
                    # 停止用Hotkeyが変更されたら再登録
                    if (
                        old_settings.periodic_stop_modifier != self.settings.periodic_stop_modifier
                        or old_settings.periodic_stop_fkey != self.settings.periodic_stop_fkey
                    ):
                        self.remove_periodic_stop_hotkey()
                        self.add_periodic_stop_hotkey()
                        logger.debug("Change periodic stop Hotkey.")
                case wx.ID_EXECUTE:
                    logger.debug("on_menu_periodic_settings closed 'Start'")
                    # 実行開始
                    self.settings.periodic_capture = True
                    wx.CallLater(self.settings.periodic_interval_to_ms(), self.do_periodic)
                case wx.ID_STOP:
                    logger.debug("on_menu_periodic_settings closed 'Stop'")
                    # 実行停止
                    self.settings.periodic_capture = False

    def stop_periodic_capture(self) -> None:
        """定期実行停止処理"""
        # 実行停止
        self.settings.periodic_capture = False
        logger.debug("Stop periodic capture")
        if self.settings.sound_on_capture:
            self.capture.success()

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
        path_str: str = (
            self.settings.periodic_save_folder if periodic else self.settings.save_folders[self.settings.save_folder_index]
        )
        save_dir = Path(path_str)
        if not save_dir.exists():
            wx.MessageBox(f"保存フォルダ '{save_dir}' が見つかりません。", "ERROR", wx.ICON_ERROR)
            return ""

        # ナンバリング種別を取得する
        kind: int = (
            self.settings.numbering
            if not periodic
            else (self.settings.periodic_numbering if self.settings.periodic_numbering == 0 else self.settings.numbering)
        )
        if kind == 0:  # 日時
            filename: str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S") + ".png"
        else:  # 接頭語＋シーケンス番号
            prefix: str = self.settings.prefix
            prefix_len: int = len(prefix)
            digits: int = self.settings.sequence_digits
            begin: int = max(self.settings.sequence_begin, self.sequence)
            logger.debug(f"Sequence No.={begin}")

            filename = f"{prefix}{begin:0>{digits}}.png"
            if (save_dir / filename).exists():
                # 現在のシーケンス番号のファイルが存在した場合、空きを探す
                ptn: str = rf"{prefix}\d{{{digits}}}\.png"
                files: list[str] = scan_directory(str(save_dir), pattern=ptn)
                if not files:
                    # 存在しない -> プレフィックス＋開始番号
                    logger.debug("Sequencial file not found.")
                    filename = f"{prefix}{begin:0>{digits}}.png"
                else:
                    # ファイル名からシーケンス番号のlistを作る
                    nums: list[int] = [int(Path(file).stem[prefix_len:]) for file in files]
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

        return str(save_dir / filename)

    def do_periodic(self) -> None:
        """定期実行処理

        Args:
            none

        Returns:
            none

        """
        if self.settings.periodic_capture:
            # ターゲットを取得
            moni_no: int = self.settings.periodic_target if self.settings.periodic_target != -1 else 90
            filename: str = self.create_filename(periodic=True)
            self.req_queue.put((moni_no, filename))
            wx.CallAfter(self.do_capture)
            # 次回を予約
            wx.CallLater(self.settings.periodic_interval_to_ms(), self.do_periodic)

    def copy_to_clipboard(self, menu_id: int, from_menu: bool = True) -> None:
        """キャプチャー要求処理（Clipboardコピー）

        * メニューとホット・キーイベントから呼ばれる

        Args:
            menu_id (int): EVENT(Menu) ID
            from_menu (bool): True = Menuから

        Returns:
            none

        """
        # ターゲット取得
        moni_no: int = 90 if menu_id == ScreenShot.ID_MENU_ACTIVE_CB else (menu_id - ScreenShot.ID_MENU_SCREEN0_CB)
        self.req_queue.put((moni_no, ""))
        # 遅延時間算出（遅延キャプチャー以外でメニュー経由は"BASE_DELAY_TIME"遅延させる）
        delay_ms: int = (
            self.settings.delayed_time_to_ms()
            if self.settings.delayed_capture
            else 0
            if not from_menu
            else ScreenShot.BASE_DELAY_TIME
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
        # ターゲット取得
        moni_no: int = 90 if menu_id == ScreenShot.ID_MENU_ACTIVE else (menu_id - ScreenShot.ID_MENU_SCREEN0)
        # 保存ファイル名生成
        filename: str = self.create_filename(self.settings.periodic_capture)
        if len(filename) == 0:
            return

        self.req_queue.put((moni_no, filename))
        delay_ms: int = (
            self.settings.delayed_time_to_ms()
            if self.settings.delayed_capture
            else ScreenShot.BASE_DELAY_TIME
            if from_menu
            else 0
        )
        # キャプチャー実行
        wx.CallLater(delay_ms, self.do_capture)

    def on_menu_clipboard(self, event: wx.Event) -> None:
        """クリップボードへコピーメニューイベントハンドラ

        * キャプチャー画像(BMP)をClipboardへコピーする。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.copy_to_clipboard(event.GetId())

    def on_menu_imagefile(self, event: wx.Event) -> None:
        """Save to PNG fileメニューイベントハンドラ

        * キャプチャー画像をPNGファイルとして保存する。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        self.save_to_imagefile(event.GetId())

    def on_menu_exit(self, _event: wx.Event) -> None:
        """Exitメニューイベントハンドラ

        * アプリケーションを終了する。

        Args:
            event (wx.EVENT): EVENTオブジェクト

        Returns:
            none

        """
        # 設定値を保存
        self.config.save()

        wx.CallAfter(self.Destroy)
        self.frame.Close()


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


def app_init() -> None:
    """実行時PATH等初期化

    * 設定ファイル等のPATHを取得する

    Args:
        none

    Returns:
        none

    """
    # 実行ファイルPATHを設定
    exe_path = Path(sys.argv[0]).resolve().parent
    # マイピクチャのPATHを取得
    ScreenShot.MY_PICTURES = Path(get_special_directory()[2])

    # 設定ファイルは実行ファイル（スクリプト）ディレクトリ下
    ScreenShot.CONFIG_FILE = exe_path / f"{ver.INFO['APP_NAME']}.ini"
    ScreenShot.HELP_FILE = exe_path / "manual.html"


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

    app_init()  # 初期化

    logger.info("=== Start ===")

    app = App()
    app.MainLoop()

    logger.info("=== Finish ===")
