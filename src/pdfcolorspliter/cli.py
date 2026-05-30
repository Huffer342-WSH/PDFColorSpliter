"""PDFColorSpliter 命令行接口。

本模块提供命令行工具，用于检测和拆分 PDF 中的彩色页面。
支持多种打印模式、手动覆盖检测结果以及仅检测模式。

功能特性:
    - 自动检测彩色页面（可调节阈值）
    - 支持 A4 双面和 A3 书册打印模式
    - 手动指定彩色/黑白页面范围
    - 导出分离的黑白和彩色 PDF 文件

典型用法:
    # 基本用法
    pdfcolorspliter input.pdf -o output --mode a4
    
    # 仅检测不导出
    pdfcolorspliter input.pdf --detect-only
    
    # 手动覆盖页面颜色
    pdfcolorspliter input.pdf --color-pages 3,4,8-10 --bw-pages 1,2

"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz

from pdfcolorspliter.detector import detect_document_colors
from pdfcolorspliter.exporter import export_split_pdfs
from pdfcolorspliter.models import PageInfo, PrintMode


def parse_page_numbers(raw: str | None) -> set[int]:
    """解析逗号分隔的页码列表和页码范围（基于 1 的索引）。

    支持单个页码和页码范围的混合格式，例如 "1,3,5-10,15"。
    页码范围使用连字符 "-" 分隔起始和结束页码。

    Parameters:
        raw (str | None): 原始页码字符串，可以为 None 或空字符串。

    Returns:
        set[int]: 解析后的页码集合（基于 1 的索引）。

    Raises:
        ValueError: 当页码范围格式错误或包含非正整数时抛出。

    Examples:
        >>> parse_page_numbers(None)
        set()
        
        >>> parse_page_numbers("")
        set()
        
        >>> parse_page_numbers("1,3,5")
        {1, 3, 5}
        
        >>> parse_page_numbers("1-3,5")
        {1, 2, 3, 5}
        
        >>> parse_page_numbers("5-3")  # doctest: +SKIP
        ValueError: Invalid page range: 5-3

    """
    if raw is None or raw.strip() == "":
        return set()

    pages: set[int] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid page range: {token}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))

    if any(page < 1 for page in pages):
        raise ValueError("Page numbers must be one-based positive integers")
    return pages


def print_mode_from_cli(raw: str) -> PrintMode:
    """将命令行模式字符串转换为 PrintMode 枚举值。

    支持多种模式名称的别名，不区分大小写。

    Parameters:
        raw (str): 命令行传入的模式字符串。

    Returns:
        PrintMode: 对应的打印模式枚举值。

    Raises:
        ValueError: 当传入不支持的模式字符串时抛出。

    Supported Aliases:
        A4 双面模式: "a4", "a4-duplex", "duplex"
        A3 书册模式: "booklet", "a3", "a3-booklet"

    Examples:
        >>> print_mode_from_cli("a4")
        <PrintMode.A4_DUPLEX: 'A4 双面'>
        
        >>> print_mode_from_cli("booklet")
        <PrintMode.A3_BOOKLET: 'A3 书册'>
        
        >>> print_mode_from_cli("invalid")  # doctest: +SKIP
        ValueError: Unsupported mode: invalid

    """
    normalized = raw.strip().lower()
    if normalized in {"a4", "a4-duplex", "duplex"}:
        return PrintMode.A4_DUPLEX
    if normalized in {"booklet", "a3", "a3-booklet"}:
        return PrintMode.A3_BOOKLET
    raise ValueError(f"Unsupported mode: {raw}")


def apply_manual_overrides(pages: list[PageInfo], color_pages: set[int], bw_pages: set[int]) -> None:
    """应用显式的彩色和黑白页面覆盖到已检测的页面列表。

    根据用户手动指定的页面覆盖自动检测结果。彩色页面集合的优先级高于黑白页面集合。

    Parameters:
        pages (list[PageInfo]): 页面信息对象列表，会被直接修改。
        color_pages (set[int]): 强制设为彩色的页码集合（基于 1 的索引）。
        bw_pages (set[int]): 强制设为黑白的页码集合（基于 1 的索引）。

    Raises:
        ValueError: 当覆盖页码超出文档范围时抛出。

    Notes:
        - 先应用彩色覆盖，再应用黑白覆盖
        - 如果同一页面同时出现在两个集合中，最终为黑白（后应用者生效）

    Examples:
        >>> pages = [PageInfo(1, False), PageInfo(2, False)]
        >>> apply_manual_overrides(pages, {1}, set())
        >>> pages[0].is_color
        True

    """
    page_map = {page.index: page for page in pages}
    unknown_pages = (color_pages | bw_pages) - set(page_map)
    if unknown_pages:
        formatted = ", ".join(str(page) for page in sorted(unknown_pages))
        raise ValueError(f"Page override outside document range: {formatted}")

    for page_index in color_pages:
        page_map[page_index].is_color = True
    for page_index in bw_pages:
        page_map[page_index].is_color = False


def build_parser() -> argparse.ArgumentParser:
    """构建命令行接口的参数解析器。

    配置所有命令行参数，包括输入文件、输出目录、打印模式、
    检测阈值、手动覆盖选项等。

    Returns:
        argparse.ArgumentParser: 配置好的参数解析器对象。

    Arguments:
        input_pdf: 输入 PDF 文件路径（必需）
        -o, --output-dir: 输出目录路径（默认当前目录）
        -m, --mode: 打印模式，a4 或 booklet（默认 a4）
        -t, --threshold: 彩色检测阈值，5-60（默认 18）
        --color-pages: 强制彩色页面，如 "3,4,8-10"
        --bw-pages: 强制黑白页面，如 "1,2,5-7"
        --detect-only: 仅检测不导出

    Examples:
        >>> parser = build_parser()
        >>> args = parser.parse_args(['test.pdf', '-o', 'output'])
        >>> print(args.input_pdf)
        test.pdf

    """
    parser = argparse.ArgumentParser(description="Detect and split color sheets from a PDF.")
    parser.add_argument("input_pdf", type=Path, help="Input PDF path.")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path.cwd(), help="Output directory.")
    parser.add_argument(
        "-m",
        "--mode",
        default="a4",
        choices=["a4", "booklet"],
        help="Print mode: a4 or booklet.",
    )
    parser.add_argument("-t", "--threshold", type=int, default=18, help="Color detection threshold.")
    parser.add_argument("--color-pages", help="Force pages to color, e.g. 3,4,8-10.")
    parser.add_argument("--bw-pages", help="Force pages to black-and-white, e.g. 1,2,5-7.")
    parser.add_argument("--detect-only", action="store_true", help="Only print detected color pages.")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    """执行命令行工作流程。

    按照以下顺序执行：
    1. 验证输入文件存在性
    2. 加载并检测 PDF 页面颜色
    3. 应用手动覆盖
    4. 根据模式导出或仅显示检测结果

    Parameters:
        args (argparse.Namespace): 解析后的命令行参数。

    Returns:
        int: 退出状态码，0 表示成功，非 0 表示失败。

    Raises:
        FileNotFoundError: 当输入 PDF 文件不存在时抛出。
        ValueError: 当参数无效时抛出。

    Examples:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     input_pdf=Path('test.pdf'),
        ...     output_dir=Path('.'),
        ...     mode='a4',
        ...     threshold=18,
        ...     color_pages=None,
        ...     bw_pages=None,
        ...     detect_only=True
        ... )
        >>> run_cli(args)  # doctest: +SKIP
        Total pages: 10
        Color pages: 3,5,7
        0

    """
    input_pdf = args.input_pdf.resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    mode = print_mode_from_cli(args.mode)
    color_overrides = parse_page_numbers(args.color_pages)
    bw_overrides = parse_page_numbers(args.bw_pages)

    with fitz.open(input_pdf) as document:
        pages = detect_document_colors(document, threshold=args.threshold)

    apply_manual_overrides(pages, color_overrides, bw_overrides)
    detected_color_pages = [page.index for page in pages if page.is_color]

    if args.detect_only:
        print(f"Total pages: {len(pages)}")
        print("Color pages: " + (",".join(str(page) for page in detected_color_pages) or "none"))
        return 0

    result = export_split_pdfs(input_pdf, pages, mode, args.output_dir.resolve())
    print(f"Black-and-white PDF: {result.bw_pdf}")
    print(f"Color PDF: {result.color_pdf}")
    print(f"Instructions: {result.instructions}")
    print("Color sheet pages: " + (",".join(str(page) for page in result.color_pages) or "none"))
    return 0


def main() -> None:
    """解析命令行参数并以命令状态退出。

    这是命令行工具的入口点，负责参数解析和工作流执行。
    使用 SystemExit 异常来传递退出状态码。

    Examples:
        $ pdfcolorspliter input.pdf -o output --mode a4

    """
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(run_cli(args))


if __name__ == "__main__":
    main()
