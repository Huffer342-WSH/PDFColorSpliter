# 开发说明

本文档记录面向开发者的项目结构、入口规则和构建方式。面向用户的使用说明请看根目录 `README.md`。

## 技术组成

- Python 3.11+
- `pywebview` 作为桌面窗口壳
- 前端使用分离的 HTML、CSS、JavaScript
- PDF 预览使用内置 PDF.js
- PDF 读写和渲染检测使用 PyMuPDF
- 打包使用 PyInstaller

## 入口规则

项目只保留一个混合入口：

```bash
uv run pdfcolorspliter
```

入口位于 `src/pdfcolorspliter/main.py`。

- 无参数：启动图形界面
- `--ui`：显式启动图形界面
- 带 PDF 路径或其他 CLI 参数：进入 CLI 模式
- `--cli`：显式进入 CLI 模式，入口会移除此标记后复用原 CLI 参数解析

独立 `pdfcolorspliter-cli` 脚本和 `PDFColorSpliterCLI.exe` 不再保留。`src/pdfcolorspliter/cli.py` 仍作为混合入口的 CLI 实现模块存在。

## 目录结构

```text
assets/
  icon.ico
src/pdfcolorspliter/
  main.py          混合入口
  webview_app.py   pywebview API 桥接和本地静态服务
  cli.py           CLI 参数解析和执行逻辑
  detector.py      彩页检测
  exporter.py      PDF 拆分导出
  planner.py       打印 sheet 规划
  booklet.py       A3 书册页序
  web/             前端静态资源和 PDF.js
```

## 图标约定

应用图标固定为：

```text
assets/icon.ico
```

运行期和 PyInstaller 打包都直接使用该路径，不再搜索其他候选图标。

## 构建

安装依赖：

```bash
uv sync
```

构建单文件可执行程序：

```bash
uv run build --clean
```

输出位于：

```text
dist/PDFColorSpliter.exe
```

构建脚本位于 `src/pdfcolorspliter/build.py`，只构建一个混合入口可执行文件。

## 验证

建议在改动后至少运行：

```bash
uv run python -m compileall -q src main.py
uv run pdfcolorspliter --help
uv run build --clean
```

如需验证 CLI 行为，可使用一个测试 PDF：

```bash
uv run pdfcolorspliter test/main.pdf --detect-only
```
