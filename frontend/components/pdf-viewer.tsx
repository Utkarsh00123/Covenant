"use client";

import React, { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";

// CRITICAL FIX: Next.js + PDF.js worker configuration.
// Pointing directly to the CDN with .mjs extension bypasses local Webpack worker compilation errors.
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

export interface BoundingBox {
  x0: number; // Percentage 0-100
  y0: number; // Percentage 0-100
  x1: number; // Percentage 0-100
  y1: number; // Percentage 0-100
  id: string; // Used to link to the specific Risk Flag
}

interface PDFViewerProps {
  fileUrl: string;
  highlights?: BoundingBox[];
  onHighlightClick?: (id: string) => void;
}

export default function PDFViewer({ fileUrl, highlights = [], onHighlightClick }: PDFViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [pageNum, setPageNum] = useState(1);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  // Load the PDF binary
  useEffect(() => {
    const loadingTask = pdfjsLib.getDocument({ url: fileUrl });
    loadingTask.promise
      .then((pdf) => {
        setPdfDoc(pdf);
        setPageNum(1); // Reset to page 1 on new file load
      })
      .catch((err) => console.error("PDF Load Error:", err));
  }, [fileUrl]);

  // Render the specific page onto the Canvas
  useEffect(() => {
    let renderTask: any = null;

    if (pdfDoc && canvasRef.current) {
      pdfDoc.getPage(pageNum).then((page: any) => {
        const viewport = page.getViewport({ scale: 1.5 }); // High-DPI scale
        const canvas = canvasRef.current;
        if (!canvas) return;
        
        const context = canvas.getContext("2d");
        if (!context) return;
        
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        const renderContext = { canvasContext: context, viewport: viewport };
        
        // Execute the render task
        renderTask = page.render(renderContext);
        
        renderTask.promise.catch((err: any) => {
          // Ignore the error if it was intentionally cancelled by our cleanup function
          if (err.name !== "RenderingCancelledException") {
            console.error("Render error", err);
          }
        });

        // Save the exact rendered pixel size for our highlight overlay math
        setCanvasSize({ width: viewport.width, height: viewport.height });
      });
    }

    // Cleanup function: Cancels the previous render if pageNum changes rapidly
    return () => {
      if (renderTask) {
        renderTask.cancel();
      }
    };
  }, [pdfDoc, pageNum]);

  return (
    <div className="relative border border-slate-200 shadow-sm rounded-lg overflow-hidden bg-slate-100 flex flex-col items-center p-4">
      
      {/* Pagination Controls */}
      <div className="mb-4 flex gap-4 items-center">
        <button 
          className="px-3 py-1 bg-white rounded shadow-sm text-sm disabled:opacity-50"
          onClick={() => setPageNum(p => Math.max(1, p - 1))}
          disabled={pageNum <= 1}
        >
          Previous
        </button>
        <span className="text-sm font-medium">Page {pageNum} of {pdfDoc?.numPages || 1}</span>
        <button 
          className="px-3 py-1 bg-white rounded shadow-sm text-sm disabled:opacity-50"
          onClick={() => setPageNum(p => Math.min(pdfDoc?.numPages || 1, p + 1))}
          disabled={!pdfDoc || pageNum >= pdfDoc.numPages}
        >
          Next
        </button>
      </div>

      {/* The Core Rendering Wrapper */}
      <div ref={containerRef} className="relative shadow-md" style={{ width: canvasSize.width, height: canvasSize.height }}>
        
        {/* Layer 1: The actual PDF image */}
        <canvas ref={canvasRef} className="absolute top-0 left-0 bg-white" />
        
        {/* Layer 2: The Interactive SVG Overlay for AI Highlights */}
        <svg 
          className="absolute top-0 left-0 z-10 pointer-events-none" 
          width={canvasSize.width} 
          height={canvasSize.height}
        >
          {highlights.map((box) => {
            // THE MATH: Convert backend percentage coordinates (0-100) to actual pixels
            const px_x0 = (box.x0 / 100) * canvasSize.width;
            const px_y0 = (box.y0 / 100) * canvasSize.height;
            const box_width = ((box.x1 - box.x0) / 100) * canvasSize.width;
            const box_height = ((box.y1 - box.y0) / 100) * canvasSize.height;

            return (
              <rect
                key={box.id}
                x={px_x0}
                y={px_y0}
                width={box_width}
                height={box_height}
                fill="rgba(250, 204, 21, 0.3)" // Translucent Yellow Box
                stroke="#ca8a04" // Solid Yellow Border
                strokeWidth="2"
                className="cursor-pointer pointer-events-auto hover:fill-[rgba(250,204,21,0.5)] transition"
                onClick={() => onHighlightClick && onHighlightClick(box.id)}
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}