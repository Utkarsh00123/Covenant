"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Expand,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Hand,
  MousePointer,
  Loader2,
  AlertCircle,
  FileText,
  Bookmark
} from "lucide-react";

// Point PDF.js worker to unpkg CDN
if (typeof window !== "undefined") {
  pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;
}

export interface BoundingBox {
  x0: number; // Percentage 0-100
  y0: number; // Percentage 0-100
  x1: number; // Percentage 0-100
  y1: number; // Percentage 0-100
  id: string; // Linked Risk Flag ID
  page?: number; // 1-indexed page
  severity?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  label?: string;
}

interface PDFViewerProps {
  fileUrl: string;
  highlights?: BoundingBox[];
  onHighlightClick?: (id: string) => void;
  activeHighlightId?: string | null;
}

export default function PDFViewer({
  fileUrl,
  highlights = [],
  onHighlightClick,
  activeHighlightId
}: PDFViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderTaskRef = useRef<any>(null);

  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [pageNum, setPageNum] = useState<number>(1);
  const [numPages, setNumPages] = useState<number>(1);

  // Dimensions & Scale
  const [basePageSize, setBasePageSize] = useState<{ width: number; height: number }>({ width: 612, height: 792 });
  const [scale, setScale] = useState<number>(1.0);
  const [fitMode, setFitMode] = useState<"auto" | "width" | "page" | "custom">("auto");

  // Interaction Tools: "select" vs "pan" (hand tool)
  const [toolMode, setToolMode] = useState<"select" | "pan">("select");
  const [isSpacePressed, setIsSpacePressed] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number; scrollLeft: number; scrollTop: number }>({
    x: 0,
    y: 0,
    scrollLeft: 0,
    scrollTop: 0
  });

  // Loading States
  const [isLoadingDoc, setIsLoadingDoc] = useState<boolean>(true);
  const [isRenderingPage, setIsRenderingPage] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Hovered highlight
  const [hoveredBox, setHoveredBox] = useState<BoundingBox | null>(null);

  // Helper to compute scale for Fit to Width or Fit to Page
  const calculateFitScale = useCallback((mode: "width" | "page", unscaledW: number, unscaledH: number) => {
    if (!viewportRef.current) return 1.0;
    const paddingX = 48;
    const paddingY = 48;
    const availableW = Math.max(300, viewportRef.current.clientWidth - paddingX);
    const availableH = Math.max(300, viewportRef.current.clientHeight - paddingY);

    if (mode === "width") {
      const s = availableW / unscaledW;
      return Math.min(Math.max(s, 0.4), 2.5);
    } else {
      const sW = availableW / unscaledW;
      const sH = availableH / unscaledH;
      return Math.min(Math.max(Math.min(sW, sH), 0.35), 2.5);
    }
  }, []);

  // 1. Load the PDF document binary
  useEffect(() => {
    let isCancelled = false;
    setIsLoadingDoc(true);
    setLoadError(null);

    const loadingTask = pdfjsLib.getDocument({
      url: fileUrl,
      withCredentials: false
    });

    loadingTask.promise
      .then((pdf) => {
        if (isCancelled) return;
        setPdfDoc(pdf);
        setNumPages(pdf.numPages);
        setPageNum(1);
        setIsLoadingDoc(false);
      })
      .catch((err) => {
        if (isCancelled) return;
        console.error("PDF Load Error:", err);
        setLoadError("Failed to load PDF document. Please verify the server connection.");
        setIsLoadingDoc(false);
      });

    return () => {
      isCancelled = true;
      try {
        loadingTask.destroy();
      } catch {
        // ignore
      }
    };
  }, [fileUrl]);

  // 2. Render Page on Canvas with High-DPI support
  const renderCurrentPage = useCallback(async () => {
    if (!pdfDoc || !canvasRef.current) return;

    if (renderTaskRef.current) {
      try {
        renderTaskRef.current.cancel();
      } catch {
        // ignore
      }
    }

    try {
      setIsRenderingPage(true);
      const page = await pdfDoc.getPage(pageNum);
      const unscaled = page.getViewport({ scale: 1.0 });
      setBasePageSize({ width: unscaled.width, height: unscaled.height });

      let currentScale = scale;
      if (fitMode === "auto" || fitMode === "width") {
        currentScale = calculateFitScale("width", unscaled.width, unscaled.height);
        setScale(Number(currentScale.toFixed(2)));
        if (fitMode === "auto") setFitMode("width");
      } else if (fitMode === "page") {
        currentScale = calculateFitScale("page", unscaled.width, unscaled.height);
        setScale(Number(currentScale.toFixed(2)));
      }

      const canvas = canvasRef.current;
      if (!canvas) return;

      const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
      const renderViewport = page.getViewport({ scale: currentScale * dpr });
      const displayW = Math.round(unscaled.width * currentScale);
      const displayH = Math.round(unscaled.height * currentScale);

      canvas.width = renderViewport.width;
      canvas.height = renderViewport.height;
      canvas.style.width = `${displayW}px`;
      canvas.style.height = `${displayH}px`;

      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) return;

      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const renderContext = {
        canvasContext: ctx,
        viewport: renderViewport
      };

      const task = page.render(renderContext);
      renderTaskRef.current = task;
      await task.promise;
      setIsRenderingPage(false);
    } catch (err: any) {
      if (err?.name !== "RenderingCancelledException") {
        console.error("Render Page Error:", err);
      }
      setIsRenderingPage(false);
    }
  }, [pdfDoc, pageNum, scale, fitMode, calculateFitScale]);

  useEffect(() => {
    renderCurrentPage();
  }, [renderCurrentPage]);

  // Window resize listener to recalculate fit scale
  useEffect(() => {
    const handleResize = () => {
      if (fitMode === "width" || fitMode === "page") {
        const newScale = calculateFitScale(fitMode, basePageSize.width, basePageSize.height);
        setScale(Number(newScale.toFixed(2)));
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [fitMode, basePageSize, calculateFitScale]);

  // Spacebar pan mode detection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) {
        e.preventDefault();
        setIsSpacePressed(true);
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        setIsSpacePressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  // Jump to active highlight's page and center scroll if activeHighlightId changes
  useEffect(() => {
    if (!activeHighlightId) return;
    const targetBox = highlights.find((h) => h.id === activeHighlightId);
    if (!targetBox) return;

    if (targetBox.page && targetBox.page !== pageNum) {
      setPageNum(targetBox.page);
    }

    // Scroll to box center after brief render timeout
    setTimeout(() => {
      if (viewportRef.current) {
        const displayH = Math.round(basePageSize.height * scale);
        const targetY = (targetBox.y0 / 100) * displayH;
        const containerH = viewportRef.current.clientHeight;
        viewportRef.current.scrollTo({
          top: Math.max(0, targetY - containerH / 2 + 50),
          behavior: "smooth"
        });
      }
    }, 150);
  }, [activeHighlightId, highlights, pageNum, basePageSize.height, scale]);

  // Zoom control handlers
  const handleZoomIn = () => {
    setFitMode("custom");
    setScale((s) => Math.min(3.0, Number((s + 0.15).toFixed(2))));
  };

  const handleZoomOut = () => {
    setFitMode("custom");
    setScale((s) => Math.max(0.35, Number((s - 0.15).toFixed(2))));
  };

  const handleFitWidth = () => {
    setFitMode("width");
    const s = calculateFitScale("width", basePageSize.width, basePageSize.height);
    setScale(Number(s.toFixed(2)));
  };

  const handleFitPage = () => {
    setFitMode("page");
    const s = calculateFitScale("page", basePageSize.width, basePageSize.height);
    setScale(Number(s.toFixed(2)));
  };

  const handleResetZoom = () => {
    setFitMode("custom");
    setScale(1.0);
  };

  const handleSetScale = (newScale: number) => {
    setFitMode("custom");
    setScale(newScale);
  };

  // Mouse wheel zoom (Ctrl/Cmd + Wheel)
  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setFitMode("custom");
      setScale((s) => Math.min(3.0, Math.max(0.35, Number((s + delta).toFixed(2)))));
    }
  };

  // Drag-to-pan implementation
  const canPan = toolMode === "pan" || isSpacePressed;

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((canPan && e.button === 0) || e.button === 1) {
      if (!viewportRef.current) return;
      e.preventDefault();
      setIsDragging(true);
      setDragStart({
        x: e.clientX,
        y: e.clientY,
        scrollLeft: viewportRef.current.scrollLeft,
        scrollTop: viewportRef.current.scrollTop
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !viewportRef.current) return;
    e.preventDefault();
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    viewportRef.current.scrollLeft = dragStart.scrollLeft - dx;
    viewportRef.current.scrollTop = dragStart.scrollTop - dy;
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Filter highlights for current page
  const pageHighlights = highlights.filter(
    (h) => h.page === undefined || h.page === pageNum
  );

  const displayWidth = Math.round(basePageSize.width * scale);
  const displayHeight = Math.round(basePageSize.height * scale);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full flex flex-col bg-slate-900/5 select-none overflow-hidden font-sans"
    >
      {/* Sleek Top Toolbar */}
      <div className="shrink-0 bg-white border-b border-slate-200 px-4 py-2 flex items-center justify-between gap-3 shadow-xs z-30 flex-wrap">
        
        {/* Left: Page Navigation */}
        <div className="flex items-center gap-1.5">
          <button
            title="Previous Page"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
            onClick={() => setPageNum((p) => Math.max(1, p - 1))}
            disabled={pageNum <= 1 || isLoadingDoc}
          >
            <ChevronLeft size={17} />
          </button>

          <div className="flex items-center text-xs font-medium text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md">
            <span>Page</span>
            <input
              type="number"
              min={1}
              max={numPages}
              value={pageNum}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                if (!isNaN(val) && val >= 1 && val <= numPages) {
                  setPageNum(val);
                }
              }}
              className="w-8 text-center bg-transparent font-semibold text-slate-900 outline-none mx-1"
            />
            <span className="text-slate-400">/ {numPages}</span>
          </div>

          <button
            title="Next Page"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
            onClick={() => setPageNum((p) => Math.min(numPages, p + 1))}
            disabled={pageNum >= numPages || isLoadingDoc}
          >
            <ChevronRight size={17} />
          </button>
        </div>

        {/* Center: Zoom Controls & Presets */}
        <div className="flex items-center gap-1 bg-slate-50 border border-slate-200/80 rounded-lg p-0.5">
          <button
            title="Zoom Out (Ctrl -)"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-md disabled:opacity-30 transition cursor-pointer"
            onClick={handleZoomOut}
            disabled={scale <= 0.35 || isLoadingDoc}
          >
            <ZoomOut size={16} />
          </button>

          {/* Zoom Preset Selector */}
          <select
            value={fitMode === "width" ? "fit-width" : fitMode === "page" ? "fit-page" : Math.round(scale * 100)}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "fit-width") handleFitWidth();
              else if (val === "fit-page") handleFitPage();
              else handleSetScale(parseInt(val) / 100);
            }}
            className="bg-transparent text-xs font-semibold text-slate-800 px-2 py-1 outline-none cursor-pointer hover:bg-white rounded"
          >
            <option value="fit-width">Fit Width</option>
            <option value="fit-page">Fit Page</option>
            <option value="50">50%</option>
            <option value="75">75%</option>
            <option value="100">100%</option>
            <option value="125">125%</option>
            <option value="150">150%</option>
            <option value="200">200%</option>
          </select>

          <button
            title="Zoom In (Ctrl +)"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-md disabled:opacity-30 transition cursor-pointer"
            onClick={handleZoomIn}
            disabled={scale >= 3.0 || isLoadingDoc}
          >
            <ZoomIn size={16} />
          </button>

          <div className="w-[1px] h-4 bg-slate-200 mx-0.5" />

          {/* Fit Width */}
          <button
            title="Fit to Width"
            className={`p-1.5 rounded-md transition cursor-pointer ${
              fitMode === "width" ? "bg-white text-blue-600 shadow-xs" : "text-slate-600 hover:text-slate-900 hover:bg-white"
            }`}
            onClick={handleFitWidth}
          >
            <Maximize2 size={15} />
          </button>

          {/* Fit Entire Page */}
          <button
            title="Fit Page in Screen"
            className={`p-1.5 rounded-md transition cursor-pointer ${
              fitMode === "page" ? "bg-white text-blue-600 shadow-xs" : "text-slate-600 hover:text-slate-900 hover:bg-white"
            }`}
            onClick={handleFitPage}
          >
            <Expand size={15} />
          </button>

          {/* Reset Zoom to 100% */}
          <button
            title="Reset Zoom (100%)"
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded-md transition cursor-pointer"
            onClick={handleResetZoom}
          >
            <RotateCcw size={15} />
          </button>
        </div>

        {/* Right: Interaction Mode Tools (Select Pointer vs Hand Pan) */}
        <div className="flex items-center gap-1.5">
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              title="Select Mode"
              className={`px-2 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition cursor-pointer ${
                toolMode === "select"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
              onClick={() => setToolMode("select")}
            >
              <MousePointer size={14} />
              <span className="hidden sm:inline">Select</span>
            </button>
            <button
              title="Pan Tool (Hold Space to Pan)"
              className={`px-2 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition cursor-pointer ${
                toolMode === "pan"
                  ? "bg-white text-blue-600 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
              onClick={() => setToolMode("pan")}
            >
              <Hand size={14} />
              <span className="hidden sm:inline">Pan</span>
            </button>
          </div>

          {pageHighlights.length > 0 && (
            <span className="text-[11px] font-semibold px-2 py-1 bg-amber-50 text-amber-800 border border-amber-200 rounded-md flex items-center gap-1">
              <Bookmark size={12} className="text-amber-600" />
              {pageHighlights.length} {pageHighlights.length === 1 ? "Risk" : "Risks"}
            </span>
          )}
        </div>
      </div>

      {/* Main Viewport Container */}
      <div
        ref={viewportRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={`flex-1 overflow-auto p-8 flex justify-center items-start transition-colors relative ${
          canPan
            ? isDragging
              ? "cursor-grabbing"
              : "cursor-grab"
            : "cursor-default"
        }`}
        style={{ scrollBehavior: isDragging ? "auto" : "smooth" }}
      >
        {/* Document Loading State */}
        {isLoadingDoc && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-50/80 z-20 backdrop-blur-xs">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-3" />
            <p className="text-sm font-medium text-slate-600">Streaming PDF document...</p>
          </div>
        )}

        {/* Load Error State */}
        {loadError && (
          <div className="m-auto max-w-sm text-center p-6 bg-white border border-red-200 rounded-xl shadow-sm">
            <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-900 mb-1">Preview Unavailable</h4>
            <p className="text-xs text-slate-500 mb-4">{loadError}</p>
            <button
              onClick={() => {
                setIsLoadingDoc(true);
                setLoadError(null);
                setPdfDoc(null);
              }}
              className="px-3 py-1.5 bg-slate-900 text-white rounded-md text-xs font-medium hover:bg-slate-800 transition cursor-pointer"
            >
              Try Again
            </button>
          </div>
        )}

        {/* The PDF Document Page Wrapper */}
        {!loadError && (
          <div
            className="relative shadow-2xl ring-1 ring-slate-900/10 rounded-sm bg-white mx-auto transition-all"
            style={{
              width: `${displayWidth}px`,
              height: `${displayHeight}px`,
              minWidth: `${displayWidth}px`,
              minHeight: `${displayHeight}px`
            }}
          >
            {/* Layer 1: The Crisp Canvas */}
            <canvas
              ref={canvasRef}
              className="block bg-white rounded-sm"
              style={{
                width: `${displayWidth}px`,
                height: `${displayHeight}px`
              }}
            />

            {/* Layer 2: Interactive SVG AI Risk Highlight Overlay */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none z-10"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              style={{ width: `${displayWidth}px`, height: `${displayHeight}px` }}
            >
              {pageHighlights.map((box) => {
                const isActive = activeHighlightId === box.id;
                const isHigh = box.severity === "CRITICAL" || box.severity === "HIGH";

                const width = Math.max(1, box.x1 - box.x0);
                const height = Math.max(1.5, box.y1 - box.y0);

                return (
                  <g key={box.id} className="pointer-events-auto group">
                    <rect
                      x={box.x0}
                      y={box.y0}
                      width={width}
                      height={height}
                      vectorEffect="non-scaling-stroke"
                      fill={
                        isActive
                          ? "rgba(239, 68, 68, 0.35)"
                          : isHigh
                          ? "rgba(239, 68, 68, 0.22)"
                          : "rgba(245, 158, 11, 0.24)"
                      }
                      stroke={isActive ? "#b91c1c" : isHigh ? "#dc2626" : "#d97706"}
                      strokeWidth={isActive ? 3 : 2}
                      strokeDasharray={isActive ? "4,2" : undefined}
                      className="cursor-pointer transition-all duration-200 group-hover:fill-[rgba(239,68,68,0.4)]"
                      onMouseEnter={() => setHoveredBox(box)}
                      onMouseLeave={() => setHoveredBox(null)}
                      onClick={(e) => {
                        e.stopPropagation();
                        onHighlightClick?.(box.id);
                      }}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Hover Tooltip for Highlight */}
            {hoveredBox && (
              <div
                className="absolute z-30 pointer-events-none bg-slate-900 text-white text-[11px] px-2.5 py-1 rounded shadow-lg -translate-x-1/2 whitespace-nowrap"
                style={{
                  left: `${((hoveredBox.x0 + hoveredBox.x1) / 2)}%`,
                  top: `${Math.max(2, hoveredBox.y0 - 3)}%`
                }}
              >
                <div className="font-semibold flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${hoveredBox.severity === "HIGH" ? "bg-red-500" : "bg-amber-400"}`} />
                  {hoveredBox.label || "Risk Flag Detected"}
                </div>
              </div>
            )}

            {/* Re-rendering badge */}
            {isRenderingPage && !isLoadingDoc && (
              <div className="absolute top-3 right-3 bg-white/80 backdrop-blur-xs px-2.5 py-1 rounded-full shadow-xs border border-slate-200 flex items-center gap-1.5 pointer-events-none z-20">
                <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />
                <span className="text-[10px] font-medium text-slate-600">Rendering...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Info Bar */}
      <div className="shrink-0 bg-white border-t border-slate-200/80 px-4 py-1.5 flex items-center justify-between text-[11px] text-slate-500 z-20">
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-slate-400" />
          <span>MOU Agreement Preview</span>
        </div>
        <div className="flex items-center gap-3">
          <span>
            Zoom: <strong className="text-slate-700">{Math.round(scale * 100)}%</strong>
          </span>
          <span className="hidden sm:inline text-slate-300">•</span>
          <span className="hidden sm:inline">
            Hold <kbd className="px-1 py-0.5 bg-slate-100 rounded text-[10px] border border-slate-200 font-mono">Space</kbd> or switch to <kbd className="px-1 py-0.5 bg-slate-100 rounded text-[10px] border border-slate-200 font-mono">Pan</kbd> to drag
          </span>
        </div>
      </div>
    </div>
  );
}