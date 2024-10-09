import time

import keyboard


def key_detected(e):
    print(f"キー{e.name}が押されました")


keyboard.on_press(callback=key_detected)

while True:
    time.sleep(1)
    print("この処理はキーボード入力の検知と並行して実行されます")
