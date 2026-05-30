"""A3 书册打印的页面排序生成器。

本模块实现 A3 书册（小册子）打印模式下的页面排序算法，
将普通页面顺序转换为适合对折装订的书册页面顺序。

书册打印说明:
    - A3 纸张对折后形成 A4 大小的两页
    - 页面需要特殊排序以确保折叠后顺序正确
    - 例如：8页文档的书册顺序为 [8,1,2,7,6,3,4,5]

典型用法:
    >>> from pdfcolorspliter.booklet import generate_booklet_sheets
    >>> sheets = generate_booklet_sheets(8)
    >>> print(sheets)
    [[8, 1, 2, 7], [6, 3, 4, 5]]

"""

from __future__ import annotations


def generate_booklet_sheets(total_pages: int) -> list[list[int]]:
    """生成 A3 书册打印的页面顺序，不自动补充空白页。

    使用双指针算法从两端向中间遍历，按照书册装订规则排列页面。
    每张纸包含 4 个页面位置（正面 2 页 + 背面 2 页）。

    Parameters:
        total_pages (int): PDF 文档的总页数。必须为非负整数。

    Returns:
        list[list[int]]: 二维列表，每个子列表代表一张纸上的页面顺序。
                        每个子列表最多包含 4 个页码（1-based）。

    Raises:
        ValueError: 当 total_pages 为负数时抛出。

    Notes:
        - 页码从 1 开始计数
        - 如果总页数不是 4 的倍数，最后一张纸可能少于 4 页
        - 不会自动填充空白页，用户需自行确保页数符合要求

    Examples:
        >>> generate_booklet_sheets(0)
        []
        
        >>> generate_booklet_sheets(4)
        [[4, 1, 2, 3]]
        
        >>> generate_booklet_sheets(8)
        [[8, 1, 2, 7], [6, 3, 4, 5]]
        
        >>> generate_booklet_sheets(6)
        [[6, 1, 2, 5], [4, 3]]

    """
    if total_pages < 0:
        raise ValueError("total_pages must be non-negative")

    sheets: list[list[int]] = []
    left = 1
    right = total_pages

    while left <= right:
        sheet: list[int] = []

        if right >= left:
            sheet.append(right)
            right -= 1
        if left <= right:
            sheet.append(left)
            left += 1
        if left <= right:
            sheet.append(left)
            left += 1
        if right >= left:
            sheet.append(right)
            right -= 1

        if sheet:
            sheets.append(sheet)

    return sheets
