import configparser
from pathlib import Path

import wx

from app_settings import AppSettings
from myutils.util import strtobool

_CONFIG_EMPTY = {
    "basic": {},
    "other": {},
    "delayed_capture": {},
    "trimming": {},
    "hotkey": {},
    "periodic": {},
}


class ConfigManager:
    """設定ファイル管理クラス"""

    def __init__(self, config_path: Path, my_pictures_path: Path, max_save_folders: int) -> None:
        """初期処理

        Args:
            config_path(pathlib.Path): 設定ファイルのPath
            my_pictures_path(pathlib.Path): 「ピクチャ」フォルダのPath
            max_save_folders(int): 保存フォルダ履歴の最大数

        Returns:
            none

        """
        self.config_path = config_path
        self.my_pictures_path = my_pictures_path
        self.max_save_folders = max_save_folders
        # 設定ファイル、設定値オブジェクトの生成
        self.config = configparser.ConfigParser()
        self.config.read_dict(_CONFIG_EMPTY)  # 初期化（セクション作成）

    def load(self) -> int:
        """設定値読み込み処理

        Args:
            none

        Returns:
            結果(int): 0=正常、-1=I/Oエラー、-2=書式エラー

        """
        if not self.config_path.exists():
            wx.MessageBox(f"設定ファイルがありません、デフォルト値で作成します。", "エラー", wx.ICON_ERROR)
            self.config_from_settings(AppSettings())
            self.save()

        try:
            with self.config_path.open(encoding="utf-8") as fc:
                self.config.read_file(fc)

        except OSError as e:
            wx.MessageBox(f"設定ファイルの読み込みに失敗しました\n ({e})", "エラー", wx.ICON_ERROR)
            return -1
        except configparser.Error as e:
            wx.MessageBox(f"設定ファイルの解析に失敗しました\n ({e})", "エラー", wx.ICON_ERROR)
            return -2

        return 0

    def save(self) -> int:
        """設定値保存処理

        Args:
            none

        Returns:
            結果(int): 0=正常、-1=I/Oエラー

        """
        try:
            with self.config_path.open("w", encoding="utf-8") as fc:
                self.config.write(fc)

        except OSError as e:
            wx.MessageBox(f"設定ファイルの書き込みに失敗しました\n ({e})", "エラー", wx.ICON_ERROR)
            return -1
        else:
            return 0

    def config_to_settings(self, settings: AppSettings) -> bool:
        """設定情報展開処理

        設定ファイル管理オブジェクトの情報を設定値管理オブジェクトに展開する

        Args:
            settings(AppSettings): 設定値管理オブジェクト

        Returns:
            再保存要求フラグ(bool): True（設定不整合の修正あり）

        """
        resave_req: bool = False
        # basic section
        settings.auto_save = strtobool(self.config["basic"]["auto_save"])
        settings.save_folder_index = int(self.config["basic"]["save_folder_index"])

        settings.save_folders.clear()
        for n in range(1, self.max_save_folders + 1):
            option_name: str = f"folder{n}"
            if not self.config.has_option("basic", option_name):
                break
            settings.save_folders.append(self.config["basic"][option_name])

        if settings.save_folders:
            if not (0 <= settings.save_folder_index < len(settings.save_folders)):
                settings.save_folder_index = 0
                resave_req = True
        else:
            settings.save_folders.append(str(self.my_pictures_path))
            settings.save_folder_index = 0
            resave_req = True

        settings.numbering = int(self.config["basic"]["numbering"])
        settings.prefix = self.config["basic"]["prefix"]
        settings.sequence_digits = int(self.config["basic"]["sequence_digits"])
        settings.sequence_begin = int(self.config["basic"]["sequence_begin"])

        # other section
        settings.capture_mcursor = strtobool(self.config["other"]["mouse_cursor"])
        settings.sound_on_capture = strtobool(self.config["other"]["sound_on_capture"])

        # delayed_capture section
        settings.delayed_capture = strtobool(self.config["delayed_capture"]["delayed_capture"])
        settings.delayed_time = int(self.config["delayed_capture"]["delayed_time"])

        # trimming section
        settings.trimming = strtobool(self.config["trimming"]["trimming"])
        settings.trimming_size = [
            int(self.config["trimming"]["top"]),
            int(self.config["trimming"]["bottom"]),
            int(self.config["trimming"]["left"]),
            int(self.config["trimming"]["right"]),
        ]

        # hotkey section
        settings.hotkey_clipboard = int(self.config["hotkey"]["clipboard"])
        settings.hotkey_imagefile = int(self.config["hotkey"]["imagefile"])
        settings.hotkey_activewin = int(self.config["hotkey"]["activewin"])

        # periodic section
        settings.periodic_save_folder = self.config["periodic"]["save_folder"]
        settings.periodic_interval = int(self.config["periodic"]["interval"])
        settings.periodic_stop_modifier = int(self.config["periodic"]["stop_modifier"])
        settings.periodic_stop_fkey = int(self.config["periodic"]["stop_fkey"])
        settings.periodic_target = int(self.config["periodic"]["target"])
        settings.periodic_numbering = int(self.config["periodic"]["numbering"])

        if not settings.periodic_save_folder:
            settings.periodic_save_folder = str(self.my_pictures_path)
            resave_req = True

        return resave_req

    def config_from_settings(self, settings: AppSettings) -> None:
        """設定情報反映処理

        設定値管理オブジェクトの内容を設定ファイル管理オブジェクトに反映する

        Args:
            settings(AppSettings): 設定値管理オブジェクト

        Returns:
            none

        """
        # basic section
        self.config["basic"]["auto_save"] = str(settings.auto_save)
        self.config["basic"]["save_folder_index"] = str(settings.save_folder_index)
        for n, folder_name in enumerate(settings.save_folders):
            self.config["basic"][f"folder{n + 1}"] = folder_name
        self.config["basic"]["numbering"] = str(settings.numbering)
        self.config["basic"]["prefix"] = settings.prefix
        self.config["basic"]["sequence_digits"] = str(settings.sequence_digits)
        self.config["basic"]["sequence_begin"] = str(settings.sequence_begin)

        # other section
        self.config["other"]["mouse_cursor"] = str(settings.capture_mcursor)
        self.config["other"]["sound_on_capture"] = str(settings.sound_on_capture)

        # delayed_capture section
        self.config["delayed_capture"]["delayed_capture"] = str(settings.delayed_capture)
        self.config["delayed_capture"]["delayed_time"] = str(settings.delayed_time)

        # trimming section
        self.config["trimming"]["trimming"] = str(settings.trimming)
        trim_top, trim_bottom, trim_left, trim_right = settings.trimming_size
        self.config["trimming"]["top"] = str(trim_top)
        self.config["trimming"]["bottom"] = str(trim_bottom)
        self.config["trimming"]["left"] = str(trim_left)
        self.config["trimming"]["right"] = str(trim_right)

        # hotkey section
        self.config["hotkey"]["clipboard"] = str(settings.hotkey_clipboard)
        self.config["hotkey"]["imagefile"] = str(settings.hotkey_imagefile)
        self.config["hotkey"]["activewin"] = str(settings.hotkey_activewin)

        # periodic section
        self.config["periodic"]["save_folder"] = settings.periodic_save_folder
        self.config["periodic"]["interval"] = str(settings.periodic_interval)
        self.config["periodic"]["stop_modifier"] = str(settings.periodic_stop_modifier)
        self.config["periodic"]["stop_fkey"] = str(settings.periodic_stop_fkey)
        self.config["periodic"]["target"] = str(settings.periodic_target)
        self.config["periodic"]["numbering"] = str(settings.periodic_numbering)
