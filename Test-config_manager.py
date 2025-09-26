#!/usr/bin/env python3
# ruff: noqa: S101, N802, ANN001, ANN201
"""Test-config_manager.py"""

import unittest
from pathlib import Path

from config_manager import ConfigManager
from myutils.util import strtobool

"""テスト結果を管理するTextTestResultを継承したクラスを作成してsubTestもカウントする"""


class VerboseTestResult(unittest.TextTestResult):
    # サブテスト毎に呼ばれるaddSubTest()をオーバーライド
    def addSubTest(self, test, subtest, outcome):
        # 元のaddSubTest()を実行して基本的な処理をさせる
        super().addSubTest(test, subtest, outcome)
        # 実行数を加算する
        self.testsRun += 1


class ConfigManagerTest(unittest.TestCase):
    def test_empty_ini(self):
        """空設定"""
        # fmt: off
        patterns = [
            # result                        , expected
            (r"test\config_manager\test.ini", r"test\config_manager\test_empty.ini"),
        ]
        # fmt: on
        print(f"\test_empty_ini [{len(patterns)}]: ", end="")
        for result, expected in patterns:
            with self.subTest(result=result, expected=expected):
                config = ConfigManager(Path(result), Path(".\\"), 10)
                config.save()
                config2 = ConfigManager(Path(expected), Path(".\\"), 10)
                assert config.config == config2.config

    def test_load_ini(self):
        # fmt: off
        patterns = [
            r"test\config_manager\test_default.ini", r"test\config_manager\test_default.ini",
        ]
        # fmt: on
        print(f"\test_load_ini [{len(patterns)}]: ", end="")
        result = patterns[0]
        with self.subTest(result=result):
            config = ConfigManager(Path(result), Path(".\\"), 10)

            config.load()
            assert strtobool(config.config["basic"]["auto_save"])
            assert int(config.config["basic"]["save_folder_index"]) == -1
            assert int(config.config["basic"]["numbering"]) == 0
            assert config.config["basic"]["prefix"] == "SS"
            assert int(config.config["basic"]["sequence_digits"]) == 6
            assert int(config.config["basic"]["sequence_begin"]) == 0
            assert not strtobool(config.config["other"]["mouse_cursor"])
            assert not strtobool(config.config["other"]["sound_on_capture"])
            assert not strtobool(config.config["delayed_capture"]["delayed_capture"])
            assert int(config.config["delayed_capture"]["delayed_time"]) == 5
            assert not strtobool(config.config["trimming"]["trimming"])
            assert int(config.config["trimming"]["top"]) == 0
            assert int(config.config["trimming"]["bottom"]) == 0
            assert int(config.config["trimming"]["left"]) == 0
            assert int(config.config["trimming"]["right"]) == 0
            assert int(config.config["hotkey"]["clipboard"]) == 0
            assert int(config.config["hotkey"]["imagefile"]) == 1
            assert int(config.config["hotkey"]["activewin"]) == 8
            assert config.config["periodic"]["save_folder"] == ""
            assert int(config.config["periodic"]["interval"]) == 3
            assert int(config.config["periodic"]["stop_modifier"]) == 0
            assert int(config.config["periodic"]["stop_fkey"]) == 11
            assert int(config.config["periodic"]["target"]) == -1
            assert int(config.config["periodic"]["numbering"]) == 0


if __name__ == "__main__":
    # unittest.main()

    # 新しく作ったVerboseTestResultを設定したrunnerを作成
    runner = unittest.TextTestRunner(resultclass=VerboseTestResult)  # pyright: ignore[reportArgumentType]
    # このrunnerを使ってunittest.main()を実行
    unittest.main(testRunner=runner)
