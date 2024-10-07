#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
"""check_sequence.py
"""
import os
import sys

# ファイルなし
file_list0 = []
# 隙間なし
file_list1 = [
    r'pictures\SS000000.png',
    r'pictures\SS000001.png',
    r'pictures\SS000002.png',
    r'pictures\SS000003.png',
    r'pictures\SS000004.png',
    r'pictures\SS000005.png',
]
# 隙間あり(1)
file_list2 = [
    r'pictures\SS000000.png',
    r'pictures\SS000001.png',
    r'pictures\SS000003.png',
    r'pictures\SS000004.png',
    r'pictures\SS000005.png',
    r'pictures\SS000006.png',
]
# 隙間あり(2)
file_list3 = [
    r'pictures\SS000000.png',
    r'pictures\SS000001.png',
    r'pictures\SS000003.png',
    r'pictures\SS000004.png',
    r'pictures\SS000006.png',
    r'pictures\SS000007.png',
]

sequence = -1

def check_sequence(file_list:list[str]) -> str:
    """
    """
    global sequence

    path:str = 'pictures'
    prefix:str = 'SS'
    digits:int = 6
    begin:int  = sequence if sequence > 0 else 0
    print(f'Sequence No.={begin}')

    filename = f'{prefix}{begin:0>{digits}}.png'
    if os.path.join(path, filename) in file_list:
        # 現在のシーケンス番号のファイルが存在した場合、空きを探す
        # ptn: str = rf'{prefix}\d{{{digits}}}\.png'
        files:list[str] = file_list
        if not files:
            # 存在しない -> プレフィックス＋開始番号
            print('Sequencial file not found.')
            filename = f'{prefix}{begin:0>{digits}}.png'
        else:
            # ToDo: 保存フォルダからprefix+sequencial_no(digits)のファイル名の一覧を取得し、次のファイル名を決定する
            # ファイル名からシーケンス番号のlistを作る
            basenames = [os.path.basename(file) for file in files]
            print(f'Basename list is {basenames}')
            sequences = [(file[len(prefix):])[:digits] for file in basenames]
            print(f'Sequences list is {sequences}')
            nums:list[int] = [int((os.path.basename(file)[len(prefix):])[:digits]) for file in files]
            print(f'Sequencial No. list is {nums}')
            # 空きを確認
            snos:list[int] = [y - 1 for x, y in zip(nums, nums[1:]) if x != y - 1 and y - 1 >= begin]
            # 空きがなければシーケンス番号の最大値+1
            begin = snos[0] if snos else nums[len(nums) - 1] + 1
            print(f'Sequence No. changed to {begin}')
            filename = f'{prefix}{begin:0>{digits}}.png'
    else:
        print(f'No duplicates "{filename}')

    sequence = begin + 1   # 次回のシーケンス番号
    print(f'Filename={filename}, Next sequence No.={sequence}')

    return os.path.join(path, filename)


if __name__ == "__main__":
    print('[TEST] ファイルなし')
    sequence = -1
    check_sequence(file_list0)

    print('[TEST] 不連続なし')
    sequence = -1
    check_sequence(file_list1)

    print('[TEST] 不連続(1)')
    sequence = -1
    check_sequence(file_list2)

    print('[TEST] 不連続(2)')
    sequence = -1
    check_sequence(file_list3)
    check_sequence(file_list3)
    check_sequence(file_list3)

    sys.exit(0)
