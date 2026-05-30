"""基于渲染像素的彩色页面检测器。

本模块通过分析 PDF 页面渲染后的 RGB 像素值来检测页面是否为彩色页面。
使用采样渲染和通道差异阈值判断方法，平衡检测速度和准确性。

检测原理:
    1. 将页面渲染为低分辨率 pixmap（默认 35% 缩放）
    2. 遍历每个像素的 R、G、B 三个通道
    3. 如果任意像素的最大最小通道差值 >= 阈值，则判定为彩色

典型用法:
    >>> import fitz
    >>> from pdfcolorspliter.detector import detect_document_colors
    >>> doc = fitz.open("test.pdf")
    >>> pages = detect_document_colors(doc, threshold=18)
    >>> color_pages = [p.index for p in pages if p.is_color]

"""

from __future__ import annotations

from collections.abc import Callable

import fitz

from pdfcolorspliter.models import PageInfo

ProgressCallback = Callable[[int, int], None]


def is_color_page(page: fitz.Page, threshold: int = 18, sample_scale: float = 0.35) -> bool:
    """判断渲染后的页面是否包含有意义的 RGB 通道差异（即是否为彩色页面）。

    通过渲染页面并检查每个像素的 RGB 通道差异来判断。如果任意像素的
    最大通道值与最小通道值之差达到或超过阈值，则认为该页面是彩色的。

    Parameters:
        page (fitz.Page): PyMuPDF 页面对象。
        threshold (int): 颜色检测阈值，范围通常为 5-60。
                        值越小越敏感，值越大越严格。默认值为 18。
        sample_scale (float): 渲染缩放比例，用于降低渲染分辨率以提高速度。
                             默认值为 0.35（35% 原始尺寸）。

    Returns:
        bool: 如果页面包含彩色内容返回 True，否则返回 False。

    Notes:
        - 对于灰度图像（channels < 3），直接返回 False
        - 采用早期退出策略：发现第一个彩色像素即返回 True
        - 阈值 18 是经过测试的平衡点，可根据需要调整

    Examples:
        >>> import fitz
        >>> doc = fitz.open()
        >>> page = doc.new_page()
        >>> is_color_page(page)  # 空白页面通常是黑白的
        False

    """
    pixmap = page.get_pixmap(matrix=fitz.Matrix(sample_scale, sample_scale), alpha=False)
    channels = pixmap.n
    samples = pixmap.samples

    if channels < 3:
        return False

    for offset in range(0, len(samples), channels):
        r = samples[offset]
        g = samples[offset + 1]
        b = samples[offset + 2]
        if max(r, g, b) - min(r, g, b) >= threshold:
            return True

    return False


def detect_document_colors(
    document: fitz.Document,
    threshold: int = 18,
    progress_callback: ProgressCallback | None = None,
) -> list[PageInfo]:
    """检测 PDF 文档中每一页的颜色状态。

    逐页加载并分析文档中的所有页面，返回包含每页颜色信息的列表。
    支持进度回调函数以更新用户界面或显示进度信息。

    Parameters:
        document (fitz.Document): PyMuPDF 文档对象。
        threshold (int): 颜色检测阈值，传递给 is_color_page 函数。默认值为 18。
        progress_callback (ProgressCallback | None): 可选的进度回调函数，
            签名为 callback(current_page, total_pages)。默认值为 None。

    Returns:
        list[PageInfo]: 页面信息对象列表，每个对象包含页码（1-based）和颜色状态。

    Notes:
        - 页码从 1 开始计数（与 PDF 阅读器一致）
        - 检测是同步进行的，大文件可能需要较长时间
        - 建议在 GUI 应用中使用进度回调以提供更好的用户体验

    Examples:
        >>> import fitz
        >>> doc = fitz.open()
        >>> doc.new_page()  # 添加一个空白页
        <fitz.Page object at ...>
        >>> pages = detect_document_colors(doc)
        >>> len(pages)
        1
        >>> pages[0].index
        1
        >>> isinstance(pages[0].is_color, bool)
        True

    """
    result: list[PageInfo] = []
    total_pages = document.page_count

    for page_index in range(total_pages):
        page = document.load_page(page_index)
        result.append(PageInfo(index=page_index + 1, is_color=is_color_page(page, threshold)))
        if progress_callback is not None:
            progress_callback(page_index + 1, total_pages)

    return result
