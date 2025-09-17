import io
import logging
from functools import partial

import mss
import mss.tools
import win32clipboard
import win32gui
from PIL import Image

from app_settings import AppSettings
from sound_manager import SoundManager

logger = logging.getLogger(__name__)


def _enum_window_callback(hwnd: int, _lparam: int, window_titles: list[str]) -> None:
    if win32gui.IsWindowEnabled(hwnd) == 0:
        return

    if win32gui.IsWindowVisible(hwnd) == 0:
        return

    if win32gui.IsIconic(hwnd) != 0:
        return

    if (window_text := win32gui.GetWindowText(hwnd)) == "":
        return

    class_name = win32gui.GetClassName(hwnd)
    if class_name is None or True in {x in class_name for x in ["QToolTip", "QPopup", "QWindowPopup", "QWindowToolTip"]}:
        return

    if window_text not in window_titles:
        window_titles.append(window_text)


class CaptureManager:
    def __init__(self) -> None:
        self.sound_manager = SoundManager()

    def _get_active_window(self) -> tuple[str, dict] | None:
        window_titles: list[str] = []
        win32gui.EnumWindows(partial(_enum_window_callback, window_titles=window_titles), 0)
        if not window_titles:
            return None

        window_title: str = window_titles[0]
        if (hwnd := win32gui.FindWindow(None, window_title)) == 0:
            return None

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width: int = abs(right - left)
        height: int = abs(bottom - top)
        area: dict = {"left": left, "top": top, "width": width, "height": height}

        return (window_title, area)

    def _copy_bitmap_to_clipboard(self, data: bytes) -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def _trim_image(self, image: Image.Image, trimming_size: list[int]) -> Image.Image:
        width, height = image.size

        top: int = trimming_size[0]
        temp_bottom: int = trimming_size[1]
        left: int = trimming_size[2]
        temp_right: int = trimming_size[3]
        right: int = (width - temp_right) if width > temp_right else width
        bottom: int = (height - temp_bottom) if height > temp_bottom else height

        logger.debug(f"Trimming ({top}, {left})-({right}, {bottom})")
        return image.crop((left, top, right, bottom))

    def execute_capture(self, moni_no: int, filename: str, settings: AppSettings) -> None:
        img = None
        with mss.mss() as sct:
            area_coord: dict = {}
            if moni_no == 90:  # Active window magic number
                info = self._get_active_window()
                if info:
                    window_title, area_coord = info
                    logger.debug(f"Capture 'Active window - [{window_title}]', {area_coord}")
            elif 0 <= moni_no < len(sct.monitors):
                area_coord = sct.monitors[moni_no]
                logger.debug(f"Capture 'Desktop'" if moni_no == 0 else f"'Display-{moni_no}'")

            if area_coord:
                if (sct_img := sct.grab(area_coord)) is not None:
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            else:
                self.sound_manager.beep()

        if img:
            logger.debug(
                f"Captured image has been {'copied to clipboard' if not filename else f'saved to {filename}'}",
            )
            if moni_no == 90 and settings.trimming:
                img = self._trim_image(img, settings.trimming_size)

            if not filename:  # Empty filename means copy to clipboard
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                self._copy_bitmap_to_clipboard(data)
            else:
                img.save(filename)

            if settings.sound_on_capture:
                self.sound_manager.success()
        else:
            logger.error("Can not captured!")
