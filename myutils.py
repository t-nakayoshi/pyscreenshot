#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ユーティリティモジュール

* class
    IsFileAction        argparse向け、ファイルパスをチェックする（存在しない場合エラーとする）
    IsDirAction         argparse向け、ディレクトリパスをチェックする（存在しない場合エラーとする）
    IsParentAction      argparse向け、ファイルパスの親ディレクトリをチェックする（存在しない場合エラーとする）

* function
    platform_info       実行環境のOS名、バージョン（リリース）、Pythonのバージョン情報を取得する
    get_special_directory
                        特殊ディレクトリのパスを取得する
    get_running_path    実行時ディレクトリとコンソールの有無を取得する
    scan_directory      指定ディレクト内のファイル一覧を取得する（拡張子のフィルタリングあり）
    is_abort            中断問い合わせ

ToDo:
    *

"""
__version__ = '1.2.0'
__author__ = 't-nakayoshi (Takayoshi Tagawa)'

import argparse
import os
import platform
import re
import sys

_PS1_FILE = r'.\myFolders.ps1'
_PS1_SCRIPT = '''#
$shellapp = New-Object -ComObject Shell.Application
$shellapp.Namespace("shell:Personal").Self.Path
$shellapp.Namespace("shell:My Music").Self.Path
$shellapp.Namespace("shell:My Pictures").Self.Path
$shellapp.Namespace("shell:My Video").Self.Path
$shellapp.Namespace("shell:Downloads").Self.Path
'''


def platform_info() -> tuple:
    """実行環境のOS名、バージョン（リリース）、Pythonのバージョン情報を取得する
    Args:
        none

    Returns:
        OS情報 (tuple): ('<OS名>', '<バージョン(リリース)>', '<Pythonのバージョン>')
    
    Examples:
        >>> Windows = ('Windows', '10', '3.10.11')              - Windows 10
        >>> Mac OS  = ('Darwin', '18.2.0', '3.10.11')           - Mojave 10.14.2
        >>> Linux   = ('Linux', '4.15.0-42-generic', '3.10.11') - Ubuntu 18.04.1 LTS
    """
    return platform.system(), platform.release(), platform.python_version()


def get_special_directory() -> tuple:
    """特殊ディレクトリのパスを取得する
    Args:
        none

    Returns:
        特殊ディレクトリパス (tuple): ('<My Documents>', '<My Music>', '<My Pictures>', '<My Videos>', '<Downloads>')
    """
    if platform.system() == 'Windows':
        if not os.path.exists(_PS1_FILE):
            try:
                with open(_PS1_FILE, 'wt') as fc:
                    fc.write(_PS1_SCRIPT)

            except OSError as e:
                sys.stderr.write(f'[error]:"{_PS1_FILE}" is save failed. ({e})\n')
                return ('','','','','')

        PWSH7: str = r'C:\Program Files\Powershell\7\pwsh.exe'
        shell: str = r'pwsh' if os.path.exists(PWSH7) else r'powershell'
        folders: list = os.popen(rf'{shell} {_PS1_FILE}').read().rstrip('\n').split('\n')
    else:
        import glib
        folders: list = [
            glib.get_user_special_dir(glib.USER_DIRECTORY_DOCUMENTS),
            glib.get_user_special_dir(glib.USER_DIRECTORY_MUSIC).
            glib.get_user_special_dir(glib.USER_DIRECTORY_PICTURES),
            glib.get_user_special_dir(glib.USER_DIRECTORY_VIDEOS),
            glib.get_user_special_dir(glib.USER_DIRECTORY_DOWNLOAD)
        ]

    return tuple(folders)


def get_running_path() -> tuple:
    """実行時ディレクトリとコンソールの有無を取得する
    * EXEを展開した一時ディレクトリのPathを返す
    * スクリプト実行の場合はスクリプトのPathを返す

    Arguments:
        none

    Returns:
        実行時ディレクトリとコンソール有無のtuple

    Note:
        * コンソールの有無は暫定
        * EXEファイルがあるディレクトリは、os.path.dirname(sys.argv[0]) で取得する
    """
    # 実行時ディレクトリを取得
    try:
        """EXE化した場合のTenporary実行時ディレクトリを取得
        """
        base_path = sys._MEIPASS
    except:
        # スクリプト実行パスを取得
        base_path = os.path.dirname(__file__)

    no_console = False
    if sys.stderr.fileno() != 2:
        no_console = True

    return base_path, no_console


class IsFileAction(argparse.Action):
    """ファイルが存在するか確認するAction
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        """`__call__`メソッドで受け取る`values`がリストでないことをチェック（`nargs`を制限）
        """
        if nargs is not None and nargs != '?':
            raise ValueError('Invalid `nargs`: multiple arguments not allowed.')
        super(IsFileAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """ファイルが存在しなければエラー
        """
        if not os.path.isfile(str(values)):
            parser.error(f'File not found. ({values})')
        setattr(namespace, self.dest, values)


class IsDirAction(argparse.Action):
    """ディレクトリが存在するか確認するAction
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        """`__call__`メソッドで受け取る`values`がリストでないことをチェック（`nargs`を制限）
        """
        if nargs is not None and nargs != '?':
            raise ValueError('Invalid `nargs`: multiple arguments not allowed.')
        super(IsDirAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """ディレクトリが存在しなければエラー
        """
        if not os.path.isdir(str(values)):
            parser.error(f'Directory not found. ({values})')
        setattr(namespace, self.dest, values)


class IsParentAction(argparse.Action):
    """親ディレクトリが存在するか確認するAction
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        """`__call__`メソッドで受け取る`values`がリストでないことをチェック（`nargs`を制限）
        """
        if nargs is not None and nargs != '?':
            raise ValueError('Invalid `nargs`: multiple arguments not allowed.')
        super(IsDirAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """親ディレクトリが存在しなければエラー
        """
        parent = os.path.dirname(str(values))
        if len(parent) == 0:
            parent = '..'
        if not os.path.isdir(parent):
            parser.error(f'Directory not found. ({values})')
        setattr(namespace, self.dest, values)


def scan_directory(directory: str, ptn: str='', recursive: bool=True) -> list[str]:
    """ファイルの抽出
    指定ディレクトリ内のファイルをリストアップする。（昇順）

    Args:
        directory: ディレクトリ名
        ptn (str) : ファイル名フィルタ（正規表現）
        recursive (bool): 再帰検索フラグ（True=再帰）

    Returns:
        list: ファイル名のリスト

    Exsamples:
        >>> files = scan_directory('abc')

    """
    files = []
    reg = None
    if len(ptn) > 0:
        reg = re.compile(ptn)

    for f in os.listdir(directory):
        child = os.path.join(directory, f)
        if os.path.isdir(child) and recursive:
            files += scan_directory(child, ptn)
        elif os.path.isfile(child):
            if reg is None:
                files.append(child)
            else:
                if reg.search(child, re.IGNORECASE):
                    files.append(child)

    if len(files) != 0:
        files.sort(key=natural_keys)

    return files


def is_abort() -> bool:
    """中断確認

    Args:
        None

    Returns:
        bool: 結果（True=中断）
    """
    ans = input('Abort? Y or [N]: ')
    if len(ans) == 0 or ans[0].lower() == 'y':
        return True
    else:
        return False

def atof(text):
    """浮動小数変換(数値ソート向け)
    """
    try:
        retval = float(text)
    except ValueError:
        retval = text
    return retval


def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    float regex comes from https://stackoverflow.com/a/12643073/190597
    '''
    return [atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text)]

