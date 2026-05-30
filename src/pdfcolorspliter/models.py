"""PDFColorSpliter 共享数据模型。

本模块定义应用程序中使用的核心数据结构，包括打印模式枚举、
页面信息、纸张信息和导出结果等数据类。

数据模型说明:
    - PrintMode: 支持的打印模式（A4 双面 / A3 书册）
    - PageInfo: 单个页面的颜色分类信息
    - SheetInfo: 规划后的物理纸张信息及是否需要彩印
    - ExportResult: 导出操作生成的文件路径和页面列表

典型用法:
    >>> from pdfcolorspliter.models import PageInfo, PrintMode
    >>> page = PageInfo(index=1, is_color=True)
    >>> print(page.index, page.is_color)
    1 True
    >>> mode = PrintMode.A4_DUPLEX
    >>> print(mode.value)
    A4 双面

"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PrintMode(str, Enum):
    """支持的打印规划模式。

    定义两种打印模式：A4 双面打印和 A3 书册打印。
    使用字符串枚举以便在 UI 中直接显示中文描述。

    Attributes:
        A4_DUPLEX: A4 纸张双面打印模式，每张纸包含 2 页（正面 1 页，背面 1 页）。
        A3_BOOKLET: A3 纸张书册打印模式，每张纸对折后包含 4 页（正反面各 2 页）。

    Examples:
        >>> PrintMode.A4_DUPLEX.value
        'A4 双面'
        
        >>> PrintMode.A3_BOOKLET.value
        'A3 书册'
        
        >>> # 可以从字符串创建
        >>> mode = PrintMode("A4 双面")
        >>> mode == PrintMode.A4_DUPLEX
        True

    """

    A4_DUPLEX = "A4 双面"
    A3_BOOKLET = "A3 书册"


@dataclass
class PageInfo:
    """PDF 单个页面的颜色分类信息。

    存储页面的索引和颜色状态，用于后续的打印规划和导出。

    Attributes:
        index (int): 页面索引，从 1 开始计数（与 PDF 阅读器一致）。
        is_color (bool): 页面是否为彩色页面。True 表示需要彩印，False 表示可以黑白打印。

    Examples:
        >>> page = PageInfo(index=5, is_color=True)
        >>> page.index
        5
        >>> page.is_color
        True
        
        >>> # 修改颜色状态
        >>> page.is_color = False
        >>> page.is_color
        False

    """

    index: int
    is_color: bool


@dataclass
class SheetInfo:
    """规划后的物理纸张信息及是否需要彩印。

    表示一张物理纸张上包含的页面列表，以及该纸张是否需要进行彩色打印。
    只要纸张上有任意一页需要彩印，整个纸张就标记为需要彩印。

    Attributes:
        pages (list[int]): 该纸张上的页面索引列表（1-based）。
        requires_color (bool): 该纸张是否需要彩色打印。

    Examples:
        >>> sheet = SheetInfo(pages=[1, 2], requires_color=True)
        >>> len(sheet.pages)
        2
        >>> sheet.requires_color
        True
        
        >>> # A4 模式下每 sheet 通常有 2 页
        >>> a4_sheet = SheetInfo(pages=[3, 4], requires_color=False)
        >>> len(a4_sheet.pages)
        2

    """

    pages: list[int]
    requires_color: bool


@dataclass
class ExportResult:
    """导出操作生成的文件路径和页面信息。

    包含导出过程中生成的所有文件路径以及分配到黑白和彩色 PDF 的页面列表。

    Attributes:
        bw_pdf (Path): 黑白 PDF 文件的完整路径。
        color_pdf (Path): 彩色 PDF 文件的完整路径。
        instructions (Path): 打印说明文本文件的完整路径。
        bw_pages (list[int]): 分配到黑白 PDF 的页面索引列表（1-based）。
        color_pages (list[int]): 分配到彩色 PDF 的页面索引列表（1-based）。

    Examples:
        >>> from pathlib import Path
        >>> result = ExportResult(
        ...     bw_pdf=Path("output/document_bw.pdf"),
        ...     color_pdf=Path("output/document_color.pdf"),
        ...     instructions=Path("output/print_instructions.txt"),
        ...     bw_pages=[1, 2, 3],
        ...     color_pages=[4, 5]
        ... )
        >>> result.bw_pdf.name
        'document_bw.pdf'
        >>> len(result.color_pages)
        2

    """

    bw_pdf: Path
    color_pdf: Path
    instructions: Path
    bw_pages: list[int]
    color_pages: list[int]
