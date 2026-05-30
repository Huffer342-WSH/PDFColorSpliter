"""PyInstaller 打包构建工具。

本模块提供使用 PyInstaller 将 PDFColorSpliter 混合入口打包为可执行文件的功能。

打包输出:
    - PDFColorSpliter.exe (无参数启动 UI，带参数进入 CLI)

典型用法:
    # 命令行打包
    python -m pdfcolorspliter.build --clean
    
    # 单文件模式打包
    python -m pdfcolorspliter.build --onefile

"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """创建打包命令行的参数解析器。

    Returns:
        argparse.ArgumentParser: 配置好的参数解析器对象。

    Arguments:
        --folder: 打包为文件夹模式（默认为单文件模式）
        --clean: 打包前清理 PyInstaller 缓存

    Examples:
        >>> parser = build_parser()
        >>> args = parser.parse_args(['--clean'])
        >>> print(args.clean)
        True

    """
    parser = argparse.ArgumentParser(description="Build PDFColorSpliter executable files with PyInstaller.")
    parser.add_argument("--folder", action="store_true", help="Build folder-based executables instead of one-file.")
    parser.add_argument("--clean", action="store_true", help="Clean PyInstaller cache before building.")
    return parser


def pyinstaller_command(root: Path, onefile: bool, clean: bool) -> list[str]:
    """生成混合入口可执行目标的 PyInstaller 命令。

    根据配置选项构建完整的 PyInstaller 命令列表，包括 pywebview 后端、
    资源文件、图标等配置。

    Parameters:
        root (Path): 项目根目录路径。
        onefile (bool): 是否打包为单文件模式。
        clean (bool): 是否清理 PyInstaller 缓存。

    Returns:
        list[str]: PyInstaller 命令及其参数的字符串列表。

    Notes:
        - 窗口模式会添加 pywebview Windows 后端的隐藏导入
        - 图标固定使用 assets/icon.ico
        - assets 和 web 目录会被包含在打包文件中

    Examples:
        >>> from pathlib import Path
        >>> cmd = pyinstaller_command(Path('.'), False, False)
        >>> isinstance(cmd, list)
        True

    """
    icon_path = root / "assets" / "icon.ico"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--paths",
        "src",
        "--name",
        "PDFColorSpliter",
        "--windowed",
        "--hidden-import",
        "webview.platforms.edgechromium",
        "--hidden-import",
        "webview.platforms.winforms",
    ]
    excluded_modules = [
        "PIL",
        "Pillow",
        "webview.platforms.android",
        "webview.platforms.cef",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.mshtml",
        "webview.platforms.qt",
    ]
    for module in excluded_modules:
        command.extend(["--exclude-module", module])
    assets_dir = root / "assets"
    if assets_dir.exists():
        command.extend(["--add-data", f"{assets_dir}{os.pathsep}assets"])
    web_dir = root / "src" / "pdfcolorspliter" / "web"
    if web_dir.exists():
        command.extend(["--add-data", f"{web_dir}{os.pathsep}web"])
    if icon_path is not None:
        command.extend(["--icon", str(icon_path)])
    if onefile:
        command.append("--onefile")
    if clean:
        command.append("--clean")
    command.append("src/pdfcolorspliter/main.py")
    return command


def run_command(command: list[str], cwd: Path) -> None:
    """执行单个构建命令，打包错误时立即失败。

    打印执行的命令到标准输出，并使用 subprocess.run 执行，
    设置 check=True 以确保错误时抛出异常。

    Parameters:
        command (list[str]): 要执行的命令及其参数列表。
        cwd (Path): 命令执行的工作目录。

    Raises:
        subprocess.CalledProcessError: 当命令执行失败时抛出。

    Examples:
        >>> from pathlib import Path
        >>> run_command(['echo', 'hello'], Path('.'))  # doctest: +SKIP
        echo hello

    """
    print(" ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    """构建混合入口可执行目标的主函数。

    解析命令行参数，然后为 PDFColorSpliter 混合入口执行打包流程。

    Targets:
        - src/pdfcolorspliter/main.py -> PDFColorSpliter

    Examples:
        $ python -m pdfcolorspliter.build --clean

    """
    args = build_parser().parse_args()
    root = Path.cwd().resolve()
    # 默认为 onefile 模式，除非指定 --folder 参数
    onefile = not args.folder
    run_command(pyinstaller_command(root, onefile, args.clean), root)


if __name__ == "__main__":
    main()
