#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
""" res_func.py
リソースデータ向け関数
"""
from base64 import b64encode, b64decode
from io import BytesIO
from zlib import compress, decompress


def convert_base64(filename: str) -> str:
    """ファイルをBASE64エンコード文字列に変換する
    """
    try:
        data = b''
        with open(filename, 'rb') as rfd:
            data = b64encode(compress(rfd.read()))

        return data.decode()

    except OSError as e:
        return ''


def convert_stream(base64str: str):
    """BASE64エンコード文字列をstreamに変換する
    """
    return BytesIO(bytearray(decompress(b64decode(base64str))))
