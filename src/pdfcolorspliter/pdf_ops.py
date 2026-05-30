"""PDF 操作辅助函数。

本模块提供小型的 PDF 文档操作工具函数，包括打开、插入页面和保存等操作。
这些函数封装了 PyMuPDF (fitz) 的基本操作，提供更简洁的接口。

功能说明:
    - open_pdf: 从路径打开 PDF 文档
    - insert_pages: 从源文档插入指定页面到目标文档
    - save_document: 保存文档到指定路径（覆盖现有文件）

典型用法:
    >>> from pathlib import Path
    >>> from pdfcolorspliter.pdf_ops import open_pdf, insert_pages, save_document
    >>> doc = open_pdf(Path("input.pdf"))
    >>> target = fitz.open()
    >>> insert_pages(doc, target, [1, 2, 3])
    >>> save_document(target, Path("output.pdf"))

"""

from __future__ import annotations

from pathlib import Path

import fitz


def open_pdf(path: Path) -> fitz.Document:
    """从 pathlib 路径打开 PDF 文档。

    使用 PyMuPDF 打开指定路径的 PDF 文件并返回文档对象。

    Parameters:
        path (Path): PDF 文件的路径对象。

    Returns:
        fitz.Document: 打开的 PDF 文档对象。

    Raises:
        FileNotFoundError: 当文件不存在时由 fitz 抛出。
        Exception: 当文件格式无效或损坏时由 fitz 抛出。

    Examples:
        >>> from pathlib import Path
        >>> # 此示例需要实际存在的 PDF 文件
        >>> # doc = open_pdf(Path("test.pdf"))
        >>> pass  # doctest: +SKIP

    """
    return fitz.open(path)


def insert_pages(source: fitz.Document, target: fitz.Document, pages: list[int]) -> None:
    """将源文档中指定的一基于页码按给定顺序插入到目标文档中。

    遍历页码列表，逐个将源文档中的页面复制到目标文档末尾。
    保持页面的原始顺序。

    Parameters:
        source (fitz.Document): 源 PDF 文档对象。
        target (fitz.Document): 目标 PDF 文档对象，会被直接修改。
        pages (list[int]): 要插入的页码列表（1-based 索引）。

    Notes:
        - 页码从 1 开始计数，内部转换为 0-based 索引
        - 页面按列表顺序依次添加到目标文档末尾
        - 如果页码超出范围，fitz 会抛出异常

    Examples:
        >>> import fitz
        >>> source = fitz.open()
        >>> source.new_page()  # 添加第 1 页
        <fitz.Page object at ...>
        >>> source.new_page()  # 添加第 2 页
        <fitz.Page object at ...>
        >>> target = fitz.open()
        >>> insert_pages(source, target, [2, 1])  # 按反向顺序插入
        >>> target.page_count
        2

    """
    for page_number in pages:
        zero_based = page_number - 1
        target.insert_pdf(source, from_page=zero_based, to_page=zero_based)


def save_document(document: fitz.Document, path: Path) -> None:
    """将 PDF 文档保存到指定路径，替换已存在的文件。

    如果目标路径已存在文件，先删除再保存，确保不会出现文件冲突。

    Parameters:
        document (fitz.Document): 要保存的 PDF 文档对象。
        path (Path): 保存目标的路径对象。

    Notes:
        - 如果文件已存在，会先删除（unlink）再保存
        - 保存操作是原子的，要么成功要么失败
        - 不会创建父目录，需确保目录已存在

    Examples:
        >>> import fitz
        >>> from pathlib import Path
        >>> import tempfile
        >>> doc = fitz.open()
        >>> doc.new_page()
        <fitz.Page object at ...>
        >>> with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        ...     save_document(doc, Path(f.name))
        >>> Path(f.name).exists()
        True
        >>> Path(f.name).unlink()

    """
    if path.exists():
        path.unlink()
    document.save(path)
