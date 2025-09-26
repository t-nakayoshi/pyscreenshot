from dataclasses import dataclass, field


@dataclass
class AppSettings:
    auto_save: bool = True
    save_folders: list[str] = field(default_factory=list)
    save_folder_index: int = -1
    numbering: int = 0
    prefix: str = "SS"
    sequence_digits: int = 6
    sequence_begin: int = 0
    capture_mcursor: bool = False
    sound_on_capture: bool = False
    delayed_capture: bool = False
    delayed_time: int = 5
    trimming: bool = False
    trimming_size: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    hotkey_clipboard: int = 0
    hotkey_imagefile: int = 1
    hotkey_activewin: int = 8
    periodic_capture: bool = False
    periodic_save_folder: str = ""
    periodic_interval: int = 3
    periodic_stop_modifier: int = 0
    periodic_stop_fkey: int = 11
    periodic_target: int = -1
    periodic_numbering: int = 0

    def delayed_time_to_ms(self) -> int:
        return self.delayed_time * 1000

    def periodic_interval_to_ms(self) -> int:
        return self.periodic_interval * 1000
