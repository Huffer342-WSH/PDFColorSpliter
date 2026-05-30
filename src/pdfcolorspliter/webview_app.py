"""pywebview 后端桥接和本地静态服务。"""

from __future__ import annotations

import json
import mimetypes
import posixpath
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import fitz
import webview

from pdfcolorspliter.assets import project_root
from pdfcolorspliter.detector import detect_document_colors
from pdfcolorspliter.exporter import export_split_pdfs
from pdfcolorspliter.models import PageInfo, PrintMode
from pdfcolorspliter.pdf_ops import open_pdf


def web_root() -> Path:
    """返回前端静态资源目录路径。

    Returns
    -------
    Path
        静态资源目录的绝对路径。
    """
    package_web = Path(__file__).resolve().parent / "web"
    if package_web.exists():
        return package_web
    return project_root() / "web"


class StaticServer:
    """为前端和当前 PDF 提供本地 HTTP 服务。

    Attributes
    ----------
    static_root : Path
        静态资源根目录。
    current_pdf : Path or None
        当前服务的 PDF 文件路径。
    port : int
        服务器监听端口。
    """

    def __init__(self, static_root: Path) -> None:
        """初始化静态服务器。

        Parameters
        ----------
        static_root : Path
            前端静态资源目录路径。
        """
        self.static_root = static_root.resolve()
        self.current_pdf: Path | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    def start(self) -> None:
        """启动后台 HTTP 服务。"""
        handler = self._make_handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止后台 HTTP 服务。"""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def url(self, path: str) -> str:
        """生成本地服务 URL。

        Parameters
        ----------
        path : str
            相对路径。

        Returns
        -------
        str
            完整 URL。
        """
        return f"http://127.0.0.1:{self.port}{path}"

    def current_pdf_url(self) -> str:
        """生成当前 PDF 的可加载 URL。

        Returns
        -------
        str
            PDF 访问 URL，未加载时返回空字符串。
        """
        if self.current_pdf is None:
            return ""
        return self.url(f"/current.pdf?name={quote(self.current_pdf.name)}")

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        """创建请求处理器类。

        Returns
        -------
        type[BaseHTTPRequestHandler]
            自定义 HTTP 请求处理器类。
        """
        server_state = self

        class Handler(BaseHTTPRequestHandler):
            """绑定当前 StaticServer 状态的请求处理器。"""

            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/current.pdf":
                    self._serve_current_pdf(server_state)
                    return
                self._serve_static(server_state, parsed.path)

            def _serve_current_pdf(self, state: StaticServer) -> None:
                pdf_path = state.current_pdf
                if pdf_path is None or not pdf_path.exists():
                    self.send_error(HTTPStatus.NOT_FOUND, "No current PDF")
                    return
                self._send_file(pdf_path, "application/pdf")

            def _serve_static(self, state: StaticServer, raw_path: str) -> None:
                clean_path = posixpath.normpath(unquote(raw_path)).lstrip("/")
                if clean_path in {"", "."}:
                    clean_path = "index.html"
                file_path = (state.static_root / clean_path).resolve()
                if state.static_root not in file_path.parents and file_path != state.static_root:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                if not file_path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
                if file_path.suffix == ".mjs":
                    content_type = "text/javascript"
                self._send_file(file_path, content_type)

            def _send_file(self, file_path: Path, content_type: str) -> None:
                data = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

        return Handler


class PdfColorSpliterApi:
    """暴露给前端 JavaScript 的应用 API。

    Attributes
    ----------
    _server : StaticServer
        静态文件服务器实例。
    _window : webview.Window or None
        pywebview 窗口对象。
    _pdf_path : Path or None
        当前加载的 PDF 路径。
    _document : fitz.Document or None
        当前打开的 PDF 文档对象。
    _pages : list[PageInfo]
        页面信息列表。
    """

    def __init__(self, server: StaticServer) -> None:
        """初始化 API 接口。

        Parameters
        ----------
        server : StaticServer
            静态文件服务器实例。
        """
        # pywebview 会扫描公开属性生成 JS API，内部状态必须保持私有。
        self._server = server
        self._window: webview.Window | None = None
        self._pdf_path: Path | None = None
        self._document: fitz.Document | None = None
        self._pages: list[PageInfo] = []

    def bind_window(self, window: webview.Window) -> None:
        """绑定 pywebview 窗口对象。

        Parameters
        ----------
        window : webview.Window
            pywebview 窗口实例。
        """
        self._window = window

    def close(self) -> None:
        """释放已打开的 PDF 文档。"""
        if self._document is not None:
            self._document.close()
            self._document = None

    def open_pdf_dialog(self) -> dict[str, object]:
        """打开 PDF 文件选择对话框。

        Returns
        -------
        dict
            包含 ok、path、name 或 cancelled 键的结果字典。
        """
        if self._window is None:
            return self._error("窗口尚未准备好")
        selected = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("PDF Files (*.pdf)",),
        )
        if not selected:
            return {"ok": False, "cancelled": True}
        path = Path(selected[0])
        return {"ok": True, "path": str(path), "name": path.name}

    def load_pdf(self, path: str, threshold: int) -> dict[str, object]:
        """加载 PDF 并执行颜色检测。

        Parameters
        ----------
        path : str
            PDF 文件路径。
        threshold : int
            颜色检测阈值。

        Returns
        -------
        dict
            包含 ok、pages、total、colorCount 的成功结果，或包含 error 的错误结果。
        """
        try:
            pdf_path = Path(path).resolve()
            if not pdf_path.exists():
                return self._error(f"PDF 文件不存在: {pdf_path}")
            self.close()
            self._document = open_pdf(pdf_path)
            self._pdf_path = pdf_path
            self._server.current_pdf = pdf_path
            self._pages = detect_document_colors(
                self._document,
                threshold=int(threshold),
                progress_callback=self._detection_progress,
            )
            return self._page_state()
        except Exception as exc:
            self._pdf_path = None
            self._server.current_pdf = None
            self._pages = []
            return self._error(str(exc))

    def redetect(self, threshold: int) -> dict[str, object]:
        """按新阈值重新检测当前 PDF。

        Parameters
        ----------
        threshold : int
            颜色检测阈值。

        Returns
        -------
        dict
            检测结果或错误信息。
        """
        if self._document is None:
            return self._error("请先打开一个 PDF")
        try:
            self._pages = detect_document_colors(
                self._document,
                threshold=int(threshold),
                progress_callback=self._detection_progress,
            )
            return self._page_state()
        except Exception as exc:
            return self._error(str(exc))

    def set_page_color(self, pageIndex: int, isColor: bool) -> dict[str, object]:
        """手动设置单页是否彩印。

        Parameters
        ----------
        pageIndex : int
            页码（从 1 开始）。
        isColor : bool
            是否为彩色页。

        Returns
        -------
        dict
            更新后的页面状态或错误信息。
        """
        page_index = int(pageIndex)
        if page_index < 1 or page_index > len(self._pages):
            return self._error("页码超出范围")
        self._pages[page_index - 1].is_color = bool(isColor)
        return self._page_state()

    def select_output_dir(self) -> dict[str, object]:
        """打开输出目录选择对话框。

        Returns
        -------
        dict
            包含 ok 和 path 的结果字典，或 cancelled 标志。
        """
        if self._window is None:
            return self._error("窗口尚未准备好")
        directory = str(self._pdf_path.parent) if self._pdf_path is not None else ""
        selected = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=directory)
        if not selected:
            return {"ok": False, "cancelled": True}
        return {"ok": True, "path": str(Path(selected[0]))}

    def export_pdf(self, outputDir: str, mode: str) -> dict[str, object]:
        """导出黑白和彩印 PDF。

        Parameters
        ----------
        outputDir : str
            输出目录路径。
        mode : str
            打印模式（a4 或 booklet）。

        Returns
        -------
        dict
            包含 bwPdf、colorPdf、instructions、bwPages、colorPages 的结果，或错误信息。
        """
        if self._pdf_path is None or not self._pages:
            return self._error("请先打开并分析一个 PDF")
        try:
            result = export_split_pdfs(self._pdf_path, self._pages, PrintMode(mode), Path(outputDir).resolve())
            return {
                "ok": True,
                "bwPdf": str(result.bw_pdf),
                "colorPdf": str(result.color_pdf),
                "instructions": str(result.instructions),
                "bwPages": result.bw_pages,
                "colorPages": result.color_pages,
            }
        except Exception as exc:
            return self._error(str(exc))

    def current_pdf_url(self) -> dict[str, object]:
        """返回 PDF.js 可以加载的当前 PDF URL。

        Returns
        -------
        dict
            包含 ok 和 url 的结果，或错误信息。
        """
        if self._pdf_path is None:
            return self._error("尚未加载 PDF")
        return {"ok": True, "url": self._server.current_pdf_url()}

    def _detection_progress(self, current: int, total: int) -> None:
        """推送检测进度到前端。

        Parameters
        ----------
        current : int
            当前处理页数。
        total : int
            总页数。
        """
        if self._window is None:
            return
        payload = json.dumps({"current": current, "total": total})
        try:
            self._window.evaluate_js(f"window.appBridge && window.appBridge.onDetectionProgress({payload})")
        except Exception:
            pass

    def _page_state(self) -> dict[str, object]:
        """返回当前页面状态。

        Returns
        -------
        dict
            包含 ok、pages、total、colorCount 的状态信息。
        """
        color_count = sum(1 for page in self._pages if page.is_color)
        return {
            "ok": True,
            "pages": [{"index": page.index, "is_color": page.is_color} for page in self._pages],
            "total": len(self._pages),
            "colorCount": color_count,
        }

    def _error(self, message: str) -> dict[str, object]:
        """返回统一错误结构。

        Parameters
        ----------
        message : str
            错误消息。

        Returns
        -------
        dict
            包含 ok=False 和 error 消息的字典。
        """
        return {"ok": False, "error": message}
