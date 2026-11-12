import * as pdfjsLib from 'pdfjs-dist';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';

// Configure local same-origin PDF.js worker (bundled in public/pdf.worker.min.mjs)
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

export async function loadPdfDocument(url: string): Promise<PDFDocumentProxy> {
  const loadingTask = pdfjsLib.getDocument({
    url,
    withCredentials: false,
    isEvalSupported: false,
  });
  return await loadingTask.promise;
}

export async function renderPdfPageToCanvas(
  pdfDoc: PDFDocumentProxy,
  pageNumber: number,
  canvas: HTMLCanvasElement,
  scale: number,
  activeTaskRef?: { current: RenderTask | null }
): Promise<void> {
  if (activeTaskRef?.current) {
    try {
      activeTaskRef.current.cancel();
    } catch {
      // Ignore cancelled render task
    }
    activeTaskRef.current = null;
  }

  const page = await pdfDoc.getPage(pageNumber);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale });
  const outputViewport = page.getViewport({ scale: scale * dpr });

  canvas.width = Math.floor(outputViewport.width);
  canvas.height = Math.floor(outputViewport.height);
  canvas.style.width = `${Math.floor(viewport.width)}px`;
  canvas.style.height = `${Math.floor(viewport.height)}px`;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const renderTask = page.render({
    canvasContext: ctx,
    viewport: outputViewport,
  });

  if (activeTaskRef) {
    activeTaskRef.current = renderTask;
  }

  try {
    await renderTask.promise;
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'name' in err && err.name === 'RenderingCancelledException') {
      return;
    }
    throw err;
  } finally {
    if (activeTaskRef && activeTaskRef.current === renderTask) {
      activeTaskRef.current = null;
    }
  }
}
