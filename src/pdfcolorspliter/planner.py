"""打印模式的页面规划器。

本模块根据不同的打印模式（A4 双面或 A3 书册）将 PDF 页面规划到物理纸张上，
并标记哪些纸张需要彩色打印。以 sheet（纸张）为基本单位进行规划。

规划策略:
    - A4 双面模式：每张纸包含 2 页（正面 1 页，背面 1 页），顺序排列
    - A3 书册模式：每张纸包含 4 页（正反面各 2 页），特殊排序以适合对折装订

颜色判断规则:
    - 只要一张纸上有任意一页需要彩印，整张纸就标记为需要彩印
    - 这样可以确保同一张纸的正反面使用相同的打印设置

典型用法:
    >>> from pdfcolorspliter.models import PageInfo, PrintMode
    >>> pages = [PageInfo(1, False), PageInfo(2, True), PageInfo(3, False)]
    >>> sheets = plan_sheets(3, pages, PrintMode.A4_DUPLEX)
    >>> len(sheets)
    2
    >>> sheets[0].requires_color  # 第 1 张纸包含页 1,2，页 2 是彩色
    True

"""

from __future__ import annotations

from collections.abc import Iterable

from pdfcolorspliter.booklet import generate_booklet_sheets
from pdfcolorspliter.models import PageInfo, PrintMode, SheetInfo


def generate_a4_duplex_sheets(total_pages: int) -> list[list[int]]:
    """为 A4 双面输出生成连续的两页纸张分组。

    将页面按顺序每两页分为一组，每组代表一张纸的正反两面。
    如果总页数为奇数，最后一张纸只有一页。

    Parameters:
        total_pages (int): PDF 文档的总页数。必须为非负整数。

    Returns:
        list[list[int]]: 二维列表，每个子列表代表一张纸上的页面（1-based）。
                        每个子列表通常包含 2 个页码，最后一页可能只有 1 个。

    Raises:
        ValueError: 当 total_pages 为负数时抛出。

    Examples:
        >>> generate_a4_duplex_sheets(0)
        []
        
        >>> generate_a4_duplex_sheets(1)
        [[1]]
        
        >>> generate_a4_duplex_sheets(4)
        [[1, 2], [3, 4]]
        
        >>> generate_a4_duplex_sheets(5)
        [[1, 2], [3, 4], [5]]

    """
    if total_pages < 0:
        raise ValueError("total_pages must be non-negative")
    return [list(range(start, min(start + 2, total_pages + 1))) for start in range(1, total_pages + 1, 2)]


def color_page_set(pages: Iterable[PageInfo]) -> set[int]:
    """返回标记为彩色打印的页面的基于 1 的索引集合。

    从页面信息列表中提取所有需要彩印的页面索引，用于后续的纸张规划。

    Parameters:
        pages (Iterable[PageInfo]): 页面信息对象的可迭代对象。

    Returns:
        set[int]: 需要彩印的页面索引集合（1-based）。

    Examples:
        >>> pages = [PageInfo(1, False), PageInfo(2, True), PageInfo(3, True)]
        >>> color_page_set(pages)
        {2, 3}
        
        >>> # 空列表返回空集合
        >>> color_page_set([])
        set()

    """
    return {page.index for page in pages if page.is_color}


def plan_sheets(total_pages: int, pages: Iterable[PageInfo], mode: PrintMode) -> list[SheetInfo]:
    """创建纸张规划并标记每个需要彩印的纸张。

    根据指定的打印模式将页面分配到物理纸张上，并根据页面颜色状态
    判断每张纸是否需要彩印。

    Parameters:
        total_pages (int): PDF 文档的总页数。
        pages (Iterable[PageInfo]): 页面信息对象的可迭代对象，包含每页的颜色状态。
        mode (PrintMode): 打印模式（A4_DUPLEX 或 A3_BOOKLET）。

    Returns:
        list[SheetInfo]: 纸张信息列表，每个对象包含页码列表和颜色需求标志。

    Raises:
        ValueError: 当传入不支持的打印模式时抛出。

    Notes:
        - A4 模式：每 2 页一组，顺序排列
        - A3 书册模式：使用特殊的页面排序算法以对折装订
        - 只要纸张上有任意一页需要彩印，整张纸就标记为 requires_color=True

    Examples:
        >>> pages = [PageInfo(1, False), PageInfo(2, True)]
        >>> sheets = plan_sheets(2, pages, PrintMode.A4_DUPLEX)
        >>> len(sheets)
        1
        >>> sheets[0].pages
        [1, 2]
        >>> sheets[0].requires_color
        True

    """
    color_pages = color_page_set(pages)
    if mode == PrintMode.A4_DUPLEX:
        page_groups = generate_a4_duplex_sheets(total_pages)
    elif mode == PrintMode.A3_BOOKLET:
        page_groups = generate_booklet_sheets(total_pages)
    else:
        raise ValueError(f"Unsupported print mode: {mode}")

    return [SheetInfo(group, any(page in color_pages for page in group)) for group in page_groups]


def flatten_sheet_pages(sheets: Iterable[SheetInfo], requires_color: bool) -> list[int]:
    """从匹配请求颜色状态的纸张中返回有序的页面索引列表。

    过滤出符合指定颜色需求的纸张（需要彩印或不需要彩印），
    并将这些纸张上的所有页面按顺序展平为一维列表。

    Parameters:
        sheets (Iterable[SheetInfo]): 纸张信息对象的可迭代对象。
        requires_color (bool): 是否只选择需要彩印的纸张。
                              True 返回彩印纸张的页面，False 返回黑白纸张的页面。

    Returns:
        list[int]: 符合条件的页面索引列表（1-based），保持原始顺序。

    Examples:
        >>> sheets = [
        ...     SheetInfo([1, 2], requires_color=False),
        ...     SheetInfo([3, 4], requires_color=True),
        ...     SheetInfo([5, 6], requires_color=False),
        ... ]
        >>> flatten_sheet_pages(sheets, requires_color=False)
        [1, 2, 5, 6]
        
        >>> flatten_sheet_pages(sheets, requires_color=True)
        [3, 4]
        
        >>> # 空列表返回空列表
        >>> flatten_sheet_pages([], requires_color=False)
        []

    """
    pages: list[int] = []
    for sheet in sheets:
        if sheet.requires_color == requires_color:
            pages.extend(sheet.pages)
    return pages
