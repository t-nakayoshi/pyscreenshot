import keyboard

# # ホットキーの設定
# hotkey = 'ctrl+shift+l'

# # ホットキーが押された時の動作
# def on_action():
#     print('Hot-key Pressed!')

# # ホットキーの設定
# keyboard.add_hotkey(hotkey, on_action)
# print(f'Hot-Key [{hotkey}] Added!')

# # [esc]待ち
# keyboard.wait('esc')
# print(f'{keyboard.read_key()} Pressed!')

# keyboard.remove_hotkey(hotkey)
# print(f'Hot-Key [{hotkey}] Removed!')

print("Wait 3 times hotkey press!")
for i in range(3):
    print(keyboard.read_hotkey())

print("Wait [ESC]")
# [esc]待ち
keyboard.wait("esc")
