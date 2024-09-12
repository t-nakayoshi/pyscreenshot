import keyboard

# ホットキーの設定
hotkey = 'ctrl + shift + l'

# ホットキーが押された時の動作
def on_action():
    print('Hot-key Pressed!')

# ホットキーの設定
keyboard.add_hotkey(hotkey, on_action)
print(f'Hot-Key [{hotkey}] Added!')

# [esc]待ち
keyboard.wait('esc')
print('[ESC] Pressed!')

keyboard.remove_hotkey(hotkey)
print(f'Hot-Key [{hotkey}] Removed!')

# [esc]待ち
keyboard.wait('esc')
