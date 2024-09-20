import keyboard
import time

HOTKEY_ALL_SCREEN_PNG = 'ctrl + shift + 0'
HOTKEY_1ST_SCREEN_PNG = 'ctrl + shift + 1'
HOTKEY_2ND_SCREEN_PNG = 'ctrl + shift + 2'
HOTKEY_3RD_SCREEN_PNG = 'ctrl + shift + 3'
HOTKEY_4TH_SCREEN_PNG = 'ctrl + shift + 4'
HOTKEY_ACTIVE_WIN_PNG = 'ctrl + shift + f9'
HOTKEY_ALL_SCREEN_CB = 'ctrl + alt + 0'
HOTKEY_1ST_SCREEN_CB = 'ctrl + alt + 1'
HOTKEY_2ND_SCREEN_CB = 'ctrl + alt + 2'
HOTKEY_3RD_SCREEN_CB = 'ctrl + alt + 3'
HOTKEY_4TH_SCREEN_CB = 'ctrl + alt + 4'
HOTKEY_ACTIVE_WIN_CB = 'ctrl + alt + f9'

keyboard.add_hotkey(HOTKEY_ALL_SCREEN_PNG, lambda: print('ALL_SCREEN_PNG'))
keyboard.add_hotkey(HOTKEY_1ST_SCREEN_PNG, lambda: print('1ST_SCREEN_PNG'))
keyboard.add_hotkey(HOTKEY_2ND_SCREEN_PNG, lambda: print('2ND_SCREEN_PNG'))
keyboard.add_hotkey(HOTKEY_3RD_SCREEN_PNG, lambda: print('3RD_SCREEN_PNG'))
keyboard.add_hotkey(HOTKEY_4TH_SCREEN_PNG, lambda: print('4TH_SCREEN_PNG'))
keyboard.add_hotkey(HOTKEY_ACTIVE_WIN_PNG, lambda: print('ACTIVE_WIN_PNG'))
keyboard.add_hotkey(HOTKEY_ALL_SCREEN_CB, lambda: print('ALL_SCREEN_CB'))
keyboard.add_hotkey(HOTKEY_1ST_SCREEN_CB, lambda: print('1ST_SCREEN_CB'))
keyboard.add_hotkey(HOTKEY_2ND_SCREEN_CB, lambda: print('2ND_SCREEN_CB'))
keyboard.add_hotkey(HOTKEY_3RD_SCREEN_CB, lambda: print('3RD_SCREEN_CB'))
keyboard.add_hotkey(HOTKEY_4TH_SCREEN_CB, lambda: print('4TH_SCREEN_CB'))
keyboard.add_hotkey(HOTKEY_ACTIVE_WIN_CB, lambda: print('ACTIVE_WIN_CB'))

keyboard.wait(hotkey='escape')
