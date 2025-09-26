# -*- coding: UTF-8 -*-
from pathlib import Path

import wx
import wx.lib.agw.multidirdialog as mdd

from app_settings import AppSettings
from PeriodicDialogBase import PeriodicDialogBase
from res import app_icon
from SettingsDialogBase import SettingsDialogBase


class SettingsDialog(SettingsDialogBase):
    """環境設定ダイアログ（実装）"""

    # ruff: noqa: ANN001, ANN002, ANN003
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))
        self.max_save_folders = 0

    def on_save_folder_add(self, event) -> None:
        """自動保存フォルダの追加"""
        if self.list_box_auto_save_folders.Count >= self.max_save_folders:
            wx.MessageBox(
                f"{self.max_save_folders}以上は登録できません。",
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

    def set_prop(self, settings: AppSettings, max_save_folders: int) -> None:
        """設定値をコントロールに反映する"""
        # --- 基本設定
        # 自動/手動
        if settings.auto_save:
            self.radio_btn_auto_save.SetValue(value=True)
        else:
            self.radio_btn_inquire_allways.SetValue(value=True)
        # 自動保存フォルダ
        for folder in settings.save_folders:
            self.list_box_auto_save_folders.Append(folder)
        self.list_box_auto_save_folders.SetSelection(settings.save_folder_index)
        # ナンバリング
        if settings.numbering == 0:
            self.radio_btn_numbering_datetime.SetValue(value=True)
        else:
            self.radio_btn_nubering_prefix_sequence.SetValue(value=True)
        # 接頭語/シーケンス桁数/開始番号
        self.text_ctrl_prefix.SetValue(settings.prefix)
        self.spin_ctrl_sequence_digits.SetValue(settings.sequence_digits)
        self.spin_ctrl_sequence_begin.SetValue(settings.sequence_begin)
        # --- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        self.checkbox_capture_mcursor.SetValue(settings.capture_mcursor)
        self.checkbox_sound_on_capture.SetValue(settings.sound_on_capture)
        # 遅延キャプチャー
        self.checkbox_delayed_capture.SetValue(settings.delayed_capture)
        self.spin_ctrl_delayed_time.SetValue(settings.delayed_time)
        # トリミング
        self.checkbox_trimming.SetValue(settings.trimming)
        self.spin_ctrl_trimming_top.SetValue(settings.trimming_size[0])
        self.spin_ctrl_trimming_bottom.SetValue(settings.trimming_size[1])
        self.spin_ctrl_trimming_left.SetValue(settings.trimming_size[2])
        self.spin_ctrl_trimming_right.SetValue(settings.trimming_size[3])
        # ホット・キー
        if settings.hotkey_clipboard == 0:
            self.radio_btn_hotkey_bmp_ctrl_alt.SetValue(value=True)
            self.radio_btn_hotkey_png_ctrl_shift.SetValue(value=True)
        else:
            self.radio_btn_hotkey_bmp_ctrl_shift.SetValue(value=True)
            self.radio_btn_hotkey_png_ctrl_alt.SetValue(value=True)
        # ターゲット
        self.choice_hotkey_active_window.SetSelection(settings.hotkey_activewin)
        # その他
        self.max_save_folders = max_save_folders

    def get_prop(self, settings: AppSettings) -> None:
        """設定値をプロパティに反映する"""
        # --- 基本設定
        # 自動/手動
        settings.auto_save = self.radio_btn_auto_save.GetValue()
        # 自動保存フォルダ
        settings.save_folders.clear()
        for folder in self.list_box_auto_save_folders.Items:
            settings.save_folders.append(folder)
        settings.save_folder_index = self.list_box_auto_save_folders.GetSelection()
        # ナンバリング
        if self.radio_btn_numbering_datetime.GetValue():
            settings.numbering = 0
        else:
            settings.numbering = 1
        # 接頭語/シーケンス桁数/開始番号
        settings.prefix = self.text_ctrl_prefix.GetValue()
        settings.sequence_digits = self.spin_ctrl_sequence_digits.GetValue()
        settings.sequence_begin = self.spin_ctrl_sequence_begin.GetValue()
        # --- その他の設定
        # マスカーソルをキャプチャーする/キャプチャー終了時に音を鳴らす
        settings.capture_mcursor = self.checkbox_capture_mcursor.GetValue()
        settings.sound_on_capture = self.checkbox_sound_on_capture.GetValue()
        # 遅延キャプチャー
        settings.delayed_capture = self.checkbox_delayed_capture.GetValue()
        settings.delayed_time = self.spin_ctrl_delayed_time.GetValue()
        # トリミング
        settings.trimming = self.checkbox_trimming.GetValue()
        settings.trimming_size = [
            self.spin_ctrl_trimming_top.GetValue(),
            self.spin_ctrl_trimming_bottom.GetValue(),
            self.spin_ctrl_trimming_left.GetValue(),
            self.spin_ctrl_trimming_right.GetValue(),
        ]
        # ホット・キー
        if self.radio_btn_hotkey_bmp_ctrl_alt.GetValue():
            settings.hotkey_clipboard = 0
            settings.hotkey_imagefile = 1
        else:
            settings.hotkey_clipboard = 1
            settings.hotkey_imagefile = 0
        # ターゲット
        settings.hotkey_activewin = self.choice_hotkey_active_window.GetSelection()


class PeriodicDialog(PeriodicDialogBase):
    """定期実行設定ダイアログ（実装）"""

    # ruff: noqa: ANN001, ANN002, ANN003
    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        # Load Application ICON
        icons = wx.IconBundle(app_icon.get_app_icon_stream(), wx.BITMAP_TYPE_ICO)  # pyright: ignore[reportCallIssue,reportArgumentType]
        self.SetIcon(icons.GetIcon(wx.Size(16, 16)))

    def on_save_folder_browse(self, event) -> None:
        """保存フォルダの選択"""
        default_path_str: str = self.text_ctrl_periodic_folder.GetValue()
        if not default_path_str or not Path(default_path_str).exists():
            default_path_str = str(Path.cwd())
        agwstyle: int = mdd.DD_MULTIPLE | mdd.DD_DIR_MUST_EXIST
        with mdd.MultiDirDialog(
            None,
            title="フォルダの選択",
            defaultPath=default_path_str,
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

    def set_prop(self, displays: int, settings: AppSettings) -> None:
        """設定値をコントロールに反映する"""
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not settings.periodic_capture)
        self.button_periodic_stop.Enable(settings.periodic_capture)
        # 保存フォルダ
        self.text_ctrl_periodic_folder.SetValue(settings.periodic_save_folder)
        # 間隔
        self.spin_ctrl_periodic_interval.SetValue(settings.periodic_interval)
        # 停止キー（修飾キー）
        self.choice_periodic_stopkey_modifire.SetSelection(settings.periodic_stop_modifier)
        self.choice_periodic_stop_fkey.SetSelection(settings.periodic_stop_fkey)
        # ターゲット
        for i in range(displays):
            item: str = f"ディスプレイ {i + 1}"
            self.choice_periodic_capture_target.Insert(
                item,
                self.choice_periodic_capture_target.GetCount() - 1,
            )
        if settings.periodic_target == -1:
            self.choice_periodic_capture_target.SetSelection(
                self.choice_periodic_capture_target.GetCount() - 1,
            )
        else:
            self.choice_periodic_capture_target.SetSelection(settings.periodic_target)
        # ナンバリング
        if settings.periodic_numbering == 0:
            self.radio_btn_periodic_numbering_datetime.SetValue(value=True)
        else:
            self.radio_btn_periodic_numbering_autosave.SetValue(value=True)

    def get_prop(self, settings: AppSettings) -> None:
        """設定値をプロパティに反映する"""
        # 実行状態によるボタンの有効/無効設定
        self.button_periodic_start.Enable(not settings.periodic_capture)
        self.button_periodic_stop.Enable(settings.periodic_capture)
        # 保存フォルダ
        settings.periodic_save_folder = self.text_ctrl_periodic_folder.GetValue()
        # 間隔
        settings.periodic_interval = self.spin_ctrl_periodic_interval.GetValue()
        # 停止キー（修飾キー）
        settings.periodic_stop_modifier = self.choice_periodic_stopkey_modifire.GetSelection()
        settings.periodic_stop_fkey = self.choice_periodic_stop_fkey.GetSelection()
        # ターゲット
        index: int = self.choice_periodic_capture_target.GetSelection()
        if index == (self.choice_periodic_capture_target.GetCount() - 1):
            settings.periodic_target = -1
        else:
            settings.periodic_target = index
        # ナンバリング
        if self.radio_btn_periodic_numbering_datetime.GetValue():
            settings.periodic_numbering = 0
        else:
            settings.periodic_numbering = 1
