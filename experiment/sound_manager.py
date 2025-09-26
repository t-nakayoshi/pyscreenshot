from wx.adv import Sound

from res import sound


class SoundManager:
    def __init__(self) -> None:
        self._beep: Sound = Sound()
        self._beep.CreateFromData(sound.get_snd_beep_bytearray())
        self._success: Sound = Sound()
        self._success.CreateFromData(sound.get_snd_success_bytearray())

    def success(self) -> None:
        """成功時サウンド"""
        self._success.Play()

    def beep(self) -> None:
        """エラー時サウンド"""
        self._beep.Play()
