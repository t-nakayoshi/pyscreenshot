import configparser
from pathlib import Path

import wx

from app_settings import AppSettings


class ConfigManager:
    """設定ファイル管理クラス"""

    def __init__(self, config_path: Path, my_pictures_path: Path) -> None:
        self.config_path = config_path
        self.my_pictures_path = my_pictures_path
        self.config = configparser.ConfigParser()

    def load_config_file(self) -> bool:
        """設定値読み込み処理"""
        if not self.config_path.exists():
            return False

        try:
            with self.config_path.open(encoding="utf-8") as fc:
                self.config.read_file(fc)

        except (OSError, configparser.Error) as e:
            wx.MessageBox(f"設定ファイルの読み込み/解析に失敗しました\n ({e})", "エラー", wx.ICON_ERROR)
            return False

        return True

    def save_config_file(self) -> None:
        """設定値保存処理"""
        try:
            with self.config_path.open("w", encoding="utf-8") as fc:
                self.config.write(fc)

        except OSError as e:
            wx.MessageBox(f"設定ファイルの書き込みに失敗しました\n ({e})", "エラー", wx.ICON_ERROR)

    def to_app_settings(self, settings: AppSettings, max_save_folders: int) -> bool:
        """設定情報クラス展開処理"""
        save_req: bool = False
        # basic section
        settings.auto_save = self.config.getboolean("basic", "auto_save", fallback=True)
        settings.save_folder_index = self.config.getint("basic", "save_folder_index", fallback=-1)

        settings.save_folders.clear()
        for n in range(1, max_save_folders + 1):
            option_name: str = f"folder{n}"
            if not self.config.has_option("basic", option_name):
                break
            option: str = self.config.get("basic", option_name)
            settings.save_folders.append(option)

        if settings.save_folders:
            if not (0 <= settings.save_folder_index < len(settings.save_folders)):
                settings.save_folder_index = 0
                save_req = True
        else:
            settings.save_folders.append(str(self.my_pictures_path))
            settings.save_folder_index = 0
            save_req = True

        settings.numbering = self.config.getint("basic", "numbering", fallback=0)
        settings.prefix = self.config.get("basic", "prefix", fallback="SS")
        settings.sequence_digits = self.config.getint("basic", "sequence_digits", fallback=6)
        settings.sequence_begin = self.config.getint("basic", "sequence_begin", fallback=0)

        # other section
        settings.capture_mcursor = self.config.getboolean("other", "mouse_cursor", fallback=False)
        settings.sound_on_capture = self.config.getboolean(
            "other",
            "sound_on_capture",
            fallback=False,
        )

        # delayed_capture section
        settings.delayed_capture = self.config.getboolean(
            "delayed_capture",
            "delayed_capture",
            fallback=False,
        )
        settings.delayed_time = self.config.getint("delayed_capture", "delayed_time", fallback=5)

        # trimming section
        settings.trimming = self.config.getboolean("trimming", "trimming", fallback=False)
        top = self.config.getint("trimming", "top", fallback=0)
        bottom = self.config.getint("trimming", "bottom", fallback=0)
        left = self.config.getint("trimming", "left", fallback=0)
        right = self.config.getint("trimming", "right", fallback=0)
        settings.trimming_size = [top, bottom, left, right]

        # hotkey section
        settings.hotkey_clipboard = self.config.getint("hotkey", "clipboard", fallback=0)
        settings.hotkey_imagefile = self.config.getint("hotkey", "imagefile", fallback=1)
        settings.hotkey_activewin = self.config.getint("hotkey", "activewin", fallback=8)

        # periodic section
        settings.periodic_save_folder = self.config.get(
            "periodic",
            "save_folder",
            fallback=str(self.my_pictures_path),
        )
        settings.periodic_interval = self.config.getint("periodic", "interval", fallback=3)
        settings.periodic_stop_modifier = self.config.getint(
            "periodic",
            "stop_modifier",
            fallback=0,
        )
        settings.periodic_stop_fkey = self.config.getint("periodic", "stop_fkey", fallback=11)
        settings.periodic_target = self.config.getint("periodic", "target", fallback=0)
        settings.periodic_numbering = self.config.getint("periodic", "numbering", fallback=0)

        if not settings.periodic_save_folder:
            settings.periodic_save_folder = str(self.my_pictures_path)
            save_req = True

        return save_req

    def from_app_settings(self, settings: AppSettings) -> None:
        """設定情報クラス反映処理"""
        # basic section
        self.config.set("basic", "auto_save", str(settings.auto_save))
        self.config.set("basic", "save_folder_index", str(settings.save_folder_index))
        for n, folder_name in enumerate(settings.save_folders):
            option_name: str = f"folder{n + 1}"
            self.config.set("basic", option_name, folder_name)
        self.config.set("basic", "numbering", str(settings.numbering))
        self.config.set("basic", "prefix", settings.prefix)
        self.config.set("basic", "sequence_digits", str(settings.sequence_digits))
        self.config.set("basic", "sequence_begin", str(settings.sequence_begin))

        # other section
        self.config.set("other", "mouse_cursor", str(settings.capture_mcursor))
        self.config.set("other", "sound_on_capture", str(settings.sound_on_capture))

        # delayed_capture section
        self.config.set("delayed_capture", "delayed_capture", str(settings.delayed_capture))
        self.config.set("delayed_capture", "delayed_time", str(settings.delayed_time))

        # trimming section
        self.config.set("trimming", "trimming", str(settings.trimming))
        trim_top, trim_bottom, trim_left, trim_right = settings.trimming_size
        self.config.set("trimming", "top", str(trim_top))
        self.config.set("trimming", "bottom", str(trim_bottom))
        self.config.set("trimming", "left", str(trim_left))
        self.config.set("trimming", "right", str(trim_right))

        # hotkey section
        self.config.set("hotkey", "clipboard", str(settings.hotkey_clipboard))
        self.config.set("hotkey", "imagefile", str(settings.hotkey_imagefile))
        self.config.set("hotkey", "activewin", str(settings.hotkey_activewin))

        # periodic section
        self.config.set("periodic", "save_folder", settings.periodic_save_folder)
        self.config.set("periodic", "interval", str(settings.periodic_interval))
        self.config.set("periodic", "stop_modifier", str(settings.periodic_stop_modifier))
        self.config.set("periodic", "stop_fkey", str(settings.periodic_stop_fkey))
        self.config.set("periodic", "target", str(settings.periodic_target))
        self.config.set("periodic", "numbering", str(settings.periodic_numbering))
