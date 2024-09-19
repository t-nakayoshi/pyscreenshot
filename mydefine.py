#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
""" mydefault.py
* デフォルト設定等
"""

_CONFIG_DEFAULT = {
    'basic': {
        'auto_save': 'True',
        'numbering': '0',
        'prefix': 'SS',
        'sequence_digits': '6',
        'sequence_begin': '0',
        'save_folder_index': '-1',
    },
    'other': {
        'mouse_cursor': 'False',
        'sound_on_capture': 'False'
    },
    'delayed_capture': {
        'delayed_capture': 'False',
        'delayed_time': '5'
    },
    'trimming': {
        'trimming': 'False',
        'top': '0',
        'bottom': '0',
        'left': '0',
        'right': '0'
    },
    'hotkey': {
        'clipboard': '0',
        'imagefile': '1',
        'activewin': '8'
    },
    'periodic': {
        'save_folder': '',
        'interval': '3',
        'stop_modifier': '0',
        'stop_fkey': '11',
        'target': '-1',
        'numbering': '0'
    }
}
