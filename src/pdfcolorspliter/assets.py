"""应用程序资源路径工具。

本模块提供用于定位应用程序图标和其他资源的辅助函数，
支持开发环境和打包后的环境。

"""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """返回项目的源代码根目录或打包后的应用根目录。

    在开发环境中，返回源代码树的根目录；在 PyInstaller 打包后，
    返回 _MEIPASS 指向的临时解压目录。

    Returns:
        Path: 项目根目录的路径对象。

    Examples:
        >>> root = project_root()
        >>> print(root)
        /path/to/PDFColorSpliter

    """
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root is not None:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[2]


def app_icon_path() -> Path:
    """返回固定的应用程序图标路径。

    图标固定为 assets/icon.ico，不再进行候选路径搜索。

    """
    return project_root() / "assets" / "icon.ico"
