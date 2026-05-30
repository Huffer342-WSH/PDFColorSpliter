import * as pdfjsLib from "./pdfjs/pdf.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "./pdfjs/pdf.worker.mjs";

const state = {
  fileName: "",
  pages: [],
  selectedIndex: 0,
  pdfDocument: null,
  rendering: false,
};

const els = {
  openButton: document.querySelector("#openButton"),
  exportButton: document.querySelector("#exportButton"),
  modeSelect: document.querySelector("#modeSelect"),
  thresholdSlider: document.querySelector("#thresholdSlider"),
  thresholdValue: document.querySelector("#thresholdValue"),
  fileName: document.querySelector("#fileName"),
  summaryText: document.querySelector("#summaryText"),
  pageList: document.querySelector("#pageList"),
  prevPageButton: document.querySelector("#prevPageButton"),
  nextPageButton: document.querySelector("#nextPageButton"),
  toggleColorButton: document.querySelector("#toggleColorButton"),
  pageIndicator: document.querySelector("#pageIndicator"),
  canvasWrap: document.querySelector("#canvasWrap"),
  canvas: document.querySelector("#pdfCanvas"),
  emptyState: document.querySelector("#emptyState"),
  statusText: document.querySelector("#statusText"),
  resultText: document.querySelector("#resultText"),
};

window.appBridge = {
  onDetectionProgress(payload) {
    setStatus(`正在检测彩页: ${payload.current}/${payload.total}`);
  },
};

window.addEventListener("pywebviewready", () => {
  setStatus("就绪");
});

els.openButton.addEventListener("click", openPdf);
els.exportButton.addEventListener("click", exportPdf);
els.thresholdSlider.addEventListener("input", () => {
  els.thresholdValue.value = els.thresholdSlider.value;
});
els.thresholdSlider.addEventListener("change", redetect);
els.prevPageButton.addEventListener("click", () => selectPage(state.selectedIndex - 1));
els.nextPageButton.addEventListener("click", () => selectPage(state.selectedIndex + 1));
els.toggleColorButton.addEventListener("click", toggleSelectedPage);
els.canvasWrap.addEventListener("wheel", (event) => {
  if (!state.pages.length) return;
  event.preventDefault();
  selectPage(state.selectedIndex + (event.deltaY > 0 ? 1 : -1));
});
window.addEventListener("resize", debounce(renderSelectedPage, 120));

async function openPdf() {
  setBusy(true);
  setStatus("正在打开文件");
  els.resultText.textContent = "";
  try {
    const selected = await window.pywebview.api.open_pdf_dialog();
    if (!selected.ok) {
      setStatus(selected.cancelled ? "已取消打开" : selected.error);
      return;
    }
    state.fileName = selected.name;
    setStatus("正在检测彩页");
    const result = await window.pywebview.api.load_pdf(selected.path, Number(els.thresholdSlider.value));
    requireOk(result);
    applyPageState(result);
    await loadPreviewDocument();
    selectPage(0);
    setStatus("检测完成");
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function redetect() {
  if (!state.pages.length) return;
  setBusy(true);
  setStatus("正在按新阈值重新检测");
  try {
    const previousIndex = state.selectedIndex;
    const result = await window.pywebview.api.redetect(Number(els.thresholdSlider.value));
    requireOk(result);
    applyPageState(result);
    selectPage(Math.min(previousIndex, state.pages.length - 1));
    setStatus("重新检测完成");
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function toggleSelectedPage() {
  const page = state.pages[state.selectedIndex];
  if (!page) return;
  try {
    const result = await window.pywebview.api.set_page_color(page.index, !page.is_color);
    requireOk(result);
    applyPageState(result);
    selectPage(state.selectedIndex, false);
  } catch (error) {
    showError(error);
  }
}

async function exportPdf() {
  if (!state.pages.length) return;
  setBusy(true);
  setStatus("正在选择输出目录");
  try {
    const selected = await window.pywebview.api.select_output_dir();
    if (!selected.ok) {
      setStatus(selected.cancelled ? "已取消导出" : selected.error);
      return;
    }
    setStatus("正在导出 PDF");
    const result = await window.pywebview.api.export_pdf(selected.path, els.modeSelect.value);
    requireOk(result);
    els.resultText.textContent = `已生成: ${fileNameOf(result.bwPdf)}, ${fileNameOf(result.colorPdf)}, ${fileNameOf(result.instructions)}`;
    setStatus("导出完成");
  } catch (error) {
    showError(error);
  } finally {
    setBusy(false);
  }
}

async function loadPreviewDocument() {
  const result = await window.pywebview.api.current_pdf_url();
  requireOk(result);
  if (state.pdfDocument) {
    await state.pdfDocument.destroy();
  }
  state.pdfDocument = await pdfjsLib.getDocument(`${result.url}&t=${Date.now()}`).promise;
}

function applyPageState(result) {
  state.pages = result.pages ?? [];
  els.fileName.textContent = state.fileName || "未加载 PDF";
  els.summaryText.textContent = `总页数: ${result.total ?? 0}    彩印页: ${result.colorCount ?? 0}`;
  els.exportButton.disabled = state.pages.length === 0;
  els.toggleColorButton.disabled = state.pages.length === 0;
  renderPageList();
}

function renderPageList() {
  els.pageList.textContent = "";
  for (const page of state.pages) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `page-row ${page.is_color ? "color" : "bw"}`;
    row.dataset.index = String(page.index - 1);
    row.setAttribute("role", "option");
    row.innerHTML = `<span>Page ${page.index}</span><span class="badge">${page.is_color ? "彩印" : "黑白"}</span>`;
    row.addEventListener("click", () => selectPage(page.index - 1));
    row.addEventListener("dblclick", toggleSelectedPage);
    els.pageList.appendChild(row);
  }
}

function selectPage(index, render = true) {
  if (!state.pages.length) return;
  state.selectedIndex = Math.max(0, Math.min(index, state.pages.length - 1));
  for (const row of els.pageList.querySelectorAll(".page-row")) {
    const selected = Number(row.dataset.index) === state.selectedIndex;
    row.classList.toggle("selected", selected);
    row.setAttribute("aria-selected", selected ? "true" : "false");
    if (selected) row.scrollIntoView({ block: "nearest" });
  }
  els.pageIndicator.textContent = `${state.selectedIndex + 1} / ${state.pages.length}`;
  els.prevPageButton.disabled = state.selectedIndex <= 0;
  els.nextPageButton.disabled = state.selectedIndex >= state.pages.length - 1;
  if (render) renderSelectedPage();
}

async function renderSelectedPage() {
  if (!state.pdfDocument || !state.pages.length || state.rendering) return;
  state.rendering = true;
  try {
    const pageNumber = state.selectedIndex + 1;
    const page = await state.pdfDocument.getPage(pageNumber);
    const wrapRect = els.canvasWrap.getBoundingClientRect();
    const viewport = page.getViewport({ scale: 1 });
    const fitScale = Math.min((wrapRect.width - 36) / viewport.width, (wrapRect.height - 36) / viewport.height);
    const scale = Math.max(0.2, fitScale) * window.devicePixelRatio;
    const scaledViewport = page.getViewport({ scale });
    const context = els.canvas.getContext("2d");

    els.canvas.width = Math.floor(scaledViewport.width);
    els.canvas.height = Math.floor(scaledViewport.height);
    els.canvas.style.width = `${Math.floor(scaledViewport.width / window.devicePixelRatio)}px`;
    els.canvas.style.height = `${Math.floor(scaledViewport.height / window.devicePixelRatio)}px`;
    els.canvas.style.display = "block";
    els.emptyState.style.display = "none";

    await page.render({ canvasContext: context, viewport: scaledViewport }).promise;
  } catch (error) {
    showError(error);
  } finally {
    state.rendering = false;
  }
}

function setBusy(isBusy) {
  els.openButton.disabled = isBusy;
  els.exportButton.disabled = isBusy || state.pages.length === 0;
  els.thresholdSlider.disabled = isBusy;
  els.modeSelect.disabled = isBusy;
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function showError(error) {
  const message = error?.message || String(error);
  setStatus(`错误: ${message}`);
}

function requireOk(result) {
  if (!result?.ok) {
    throw new Error(result?.error || "操作失败");
  }
}

function fileNameOf(path) {
  return String(path).split(/[\\/]/).pop();
}

function debounce(fn, delay) {
  let timer = 0;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}
