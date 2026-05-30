"""黑白和彩色打印任务 PDF 导出器。

本模块负责根据页面规划结果导出分离的黑白和彩色 PDF 文件，
并生成打印说明文本文件。以 sheet（纸张）为单位进行导出判断：
只要一张纸上有任意页面需要彩印，则整张纸进入彩印 PDF。

导出流程:
    1. 根据打印模式规划页面到纸张的分配
    2. 将需要黑白的纸张页面提取到黑白 PDF
    3. 将需要彩色的纸张页面提取到彩色 PDF
    4. 生成打印说明文件

输出文件:
    - document_bw.pdf: 黑白打印用 PDF
    - document_color.pdf: 彩色打印用 PDF
    - print_instructions.txt: 打印说明文本文件

典型用法:
    >>> from pathlib import Path
    >>> from pdfcolorspliter.models import PageInfo, PrintMode
    >>> pages = [PageInfo(1, False), PageInfo(2, True)]
    >>> result = export_split_pdfs(Path("input.pdf"), pages, PrintMode.A4_DUPLEX, Path("output"))

"""

from __future__ import annotations

from pathlib import Path

import fitz

from pdfcolorspliter.models import ExportResult, PageInfo, PrintMode
from pdfcolorspliter.pdf_ops import insert_pages, save_document
from pdfcolorspliter.planner import flatten_sheet_pages, plan_sheets


def _ensure_non_empty_pdf(document: fitz.Document, label: str) -> None:
    """当输出作业不包含任何实际页面时，添加一个小的占位符页面。

    确保导出的 PDF 文件至少包含一页，避免生成空 PDF 文件导致某些
    PDF 阅读器报错或用户体验不佳。

    Parameters:
        document (fitz.Document): PyMuPDF 文档对象，会被直接修改。
        label (str): 占位符页面上显示的提示文本。

    Notes:
        - 如果文档已有页面，则不做任何操作
        - 占位符页面尺寸为 A4（595x842 points）
        - 文本显示在页面左上角（72, 72）位置

    Examples:
        >>> import fitz
        >>> doc = fitz.open()
        >>> _ensure_non_empty_pdf(doc, "Placeholder")
        >>> doc.page_count
        1

    """
    if document.page_count > 0:
        return
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), label, fontsize=12)


def write_instructions(
    path: Path,
    bw_pdf: Path,
    color_pdf: Path,
    color_pages: list[int],
    mode: PrintMode,
) -> None:
    """写入描述生成输出的文本说明文件。

    生成包含打印模式、输出文件信息和彩色页码列表的说明文件，
    帮助用户正确执行打印任务。

    Parameters:
        path (Path): 说明文件的输出路径。
        bw_pdf (Path): 黑白 PDF 文件路径。
        color_pdf (Path): 彩色 PDF 文件路径。
        color_pages (list[int]): 需要彩色打印的页码列表（1-based）。
        mode (PrintMode): 使用的打印模式。

    Notes:
        - 文件使用 UTF-8 编码保存
        - 如果没有彩色页面，显示"无"
        - 格式为人类可读的纯文本

    Examples:
        >>> from pathlib import Path
        >>> from pdfcolorspliter.models import PrintMode
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        ...     path = Path(f.name)
        >>> write_instructions(path, Path("bw.pdf"), Path("color.pdf"), [1, 3, 5], PrintMode.A4_DUPLEX)
        >>> content = path.read_text(encoding='utf-8')
        >>> "A4 双面" in content
        True
        >>> path.unlink()

    """
    color_page_text = ",".join(str(page) for page in color_pages) if color_pages else "无"
    content = (
        "=== PDFColorSpliter 输出 ===\n\n"
        f"打印模式:\n{mode.value}\n\n"
        f"黑白PDF:\n{bw_pdf.name}\n\n"
        f"彩印PDF:\n{color_pdf.name}\n\n"
        f"彩印页:\n{color_page_text}\n"
    )
    path.write_text(content, encoding="utf-8")


def export_split_pdfs(
    source_pdf: Path,
    pages: list[PageInfo],
    mode: PrintMode,
    output_dir: Path,
) -> ExportResult:
    """根据纸张级别的规划导出黑白和彩色 PDF 文件。

    这是主要的导出函数，协调整个导出流程：
    1. 创建输出目录
    2. 规划页面到纸张的分配
    3. 分别提取黑白和彩色页面
    4. 生成两个 PDF 文件和说明文件

    Parameters:
        source_pdf (Path): 源 PDF 文件路径。
        pages (list[PageInfo]): 页面信息列表，包含每页的颜色状态。
        mode (PrintMode): 打印模式（A4 双面或 A3 书册）。
        output_dir (Path): 输出目录路径，不存在时会自动创建。

    Returns:
        ExportResult: 包含导出文件路径和页面列表的结果对象。

    Raises:
        OSError: 当文件系统操作失败时可能抛出。

    Notes:
        - 输出目录会自动创建（包括父目录）
        - 如果某个输出没有页面，会添加占位符页
        - 现有文件会被覆盖（先删除再保存）
        - 资源管理使用 try-finally 确保文档正确关闭

    Examples:
        >>> from pathlib import Path
        >>> from pdfcolorspliter.models import PageInfo, PrintMode
        >>> # 此示例仅展示类型签名，实际需要有效的 PDF 文件
        >>> # result = export_split_pdfs(Path("test.pdf"), 
        >>> #                            [PageInfo(1, False)], 
        >>> #                            PrintMode.A4_DUPLEX, 
        >>> #                            Path("output"))

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    bw_pdf = output_dir / "document_bw.pdf"
    color_pdf = output_dir / "document_color.pdf"
    instructions = output_dir / "print_instructions.txt"

    with fitz.open(source_pdf) as source:
        sheets = plan_sheets(source.page_count, pages, mode)
        bw_pages = flatten_sheet_pages(sheets, requires_color=False)
        color_pages = flatten_sheet_pages(sheets, requires_color=True)

        bw_document = fitz.open()
        color_document = fitz.open()
        try:
            insert_pages(source, bw_document, bw_pages)
            insert_pages(source, color_document, color_pages)
            _ensure_non_empty_pdf(bw_document, "No black-and-white pages in this output.")
            _ensure_non_empty_pdf(color_document, "No color pages in this output.")
            save_document(bw_document, bw_pdf)
            save_document(color_document, color_pdf)
        finally:
            bw_document.close()
            color_document.close()

    write_instructions(instructions, bw_pdf, color_pdf, color_pages, mode)
    return ExportResult(bw_pdf, color_pdf, instructions, bw_pages, color_pages)
