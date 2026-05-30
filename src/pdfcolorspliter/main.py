"""pywebview 图形界面入口。"""

from __future__ import annotations

import os
import sys

import webview

from pdfcolorspliter.assets import app_icon_path
from pdfcolorspliter.cli import build_parser, run_cli
from pdfcolorspliter.webview_app import PdfColorSpliterApi, StaticServer, web_root


def should_run_cli(arguments: list[str]) -> bool:
    """判断当前启动参数是否应进入 CLI 模式。"""
    return bool(arguments) and arguments[0] != "--ui"


def normalize_cli_arguments(arguments: list[str]) -> list[str]:
    """移除用于触发 CLI 模式的启动标记。"""
    if arguments and arguments[0] == "--cli":
        return arguments[1:]
    return arguments


def run_cli_mode(arguments: list[str]) -> int:
    """用主入口参数执行原 CLI 工作流。"""
    attach_parent_console()
    parser = build_parser()
    args = parser.parse_args(normalize_cli_arguments(arguments))
    return run_cli(args)


def attach_parent_console() -> None:
    """在 windowed 打包程序中尽量复用启动它的父终端。"""
    if os.name != "nt" or sys.stdout.isatty():
        return

    try:
        import ctypes

        attach_parent_process = -1
        if ctypes.windll.kernel32.AttachConsole(attach_parent_process) == 0:
            return
        # GUI 子系统程序没有标准流，附加父终端后需要重新绑定。
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="ignore")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="ignore")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="ignore")
    except OSError:
        return


def run_ui_mode() -> None:
    """启动 pywebview 桌面应用。"""
    server = StaticServer(web_root())
    server.start()

    api = PdfColorSpliterApi(server)
    window = webview.create_window(
        "PDFColorSpliter",
        server.url("/index.html"),
        js_api=api,
        width=1120,
        height=760,
        min_size=(900, 620),
    )
    api.bind_window(window)

    try:
        webview.start(debug=False, gui="edgechromium", icon=str(app_icon_path()))
    finally:
        api.close()
        server.stop()


def main() -> None:
    """根据启动参数自动选择 CLI 或 UI 模式。"""
    arguments = sys.argv[1:]
    if should_run_cli(arguments):
        raise SystemExit(run_cli_mode(arguments))
    if arguments == ["--ui"]:
        sys.argv = [sys.argv[0]]
    run_ui_mode()


if __name__ == "__main__":
    sys.exit(main())
