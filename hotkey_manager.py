import keyboard
import wx


class HotkeyManager:
    """Hot-Key Manager class"""

    """ Hotkey Modifiers """
    HK_MOD_NONE: str = ""
    HK_MOD_SHIFT: str = "Shift"
    HK_MOD_CTRL: str = "Ctrl"
    HK_MOD_ALT: str = "Alt"
    HK_MOD_CTRL_ALT: str = f"{HK_MOD_CTRL}+{HK_MOD_ALT}"
    HK_MOD_CTRL_SHIFT: str = f"{HK_MOD_CTRL}+{HK_MOD_SHIFT}"
    HK_MOD_SHIFT_ALT: str = f"{HK_MOD_SHIFT}+{HK_MOD_ALT}"

    # ruff: noqa: ANN001
    def __init__(self) -> None:
        # キャプチャーHotkey
        self._capture_hotkey_tbl: tuple = (HotkeyManager.HK_MOD_CTRL_ALT, HotkeyManager.HK_MOD_CTRL_SHIFT)
        # 定期実行停止Hotkey
        self._periodic_stop_hotkey_tbl: tuple = (
            HotkeyManager.HK_MOD_NONE,
            HotkeyManager.HK_MOD_SHIFT,
            HotkeyManager.HK_MOD_CTRL,
            HotkeyManager.HK_MOD_ALT,
        )
        self._to_clipboard: list[str] = []
        self._to_imagefile: list[str] = []
        self._periodic_stop: str = ""

    def get_capture_hotkey(self, kind: int) -> str:
        """キャプチャー用Hotkeyの取得"""
        return self._capture_hotkey_tbl[kind]

    def get_periodic_stop_hotkey(self, kind: int) -> str:
        """定期実行停止用Hotkeyの取得"""
        return self._periodic_stop_hotkey_tbl[kind]

    def add_clipboard(self, hot_key: str, menu_id: int, handler) -> None:
        """（クリップボード向け）キャプチャー用ホット・キー登録処理

        * キャプチャー用ホット・キーを登録する

        Args:
            hot_key(str): Hot-key
            menu_id(int): Menu-ID
            handler: 処理関数

        Returns:
            none

        """
        self._to_clipboard.append(hot_key)
        # Hotkeyの登録
        keyboard.add_hotkey(hot_key, wx.CallAfter, (handler, menu_id, False))

    def add_imagefile(self, hot_key: str, menu_id: int, handler) -> None:
        """（画像ファイル向け）キャプチャー用ホット・キー登録処理

        * キャプチャー用ホット・キーを登録する

        Args:
            hot_key(str): Hot-key
            menu_id(int): Menu-ID
            handler: 処理関数

        Returns:
            none

        """
        self._to_imagefile.append(hot_key)
        # Hotkeyの登録
        keyboard.add_hotkey(hot_key, wx.CallAfter, (handler, menu_id, False))

    def remove_capture(self) -> None:
        """キャプチャー用ホット・キー削除処理

        * 現在のキャプチャー用ホット・キーを全削除する

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        for hotkey in self._to_clipboard:
            keyboard.remove_hotkey(hotkey)
        self._to_clipboard.clear()

        for hotkey in self._to_imagefile:
            keyboard.remove_hotkey(hotkey)
        self._to_imagefile.clear()

    def add_periodic_stop(self, hot_key: str, handler) -> None:
        """定期実行停止ホット・キー登録処理

        Args:
            hot_key(str): Hot-key
            handler: 処理関数

        Returns:
            none

        """
        self._periodic_stop = hot_key
        keyboard.add_hotkey(hot_key, lambda: wx.CallAfter(handler))

    def remove_periodic_stop(self) -> None:
        """定期実行停止ホット・キー削除処理

        Args:
            none

        Returns:
            none

        """
        # 現在のHotkeyを削除
        keyboard.remove_hotkey(self._periodic_stop)
