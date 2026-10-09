"use client";

import React from "react";
import { AlertTriangle, X, ExternalLink, Clock, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface QuotaModalProps {
  open: boolean;
  onClose: () => void;
  errorDetail?: string;
}

export default function QuotaModal({ open, onClose, errorDetail }: QuotaModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-red-200 relative overflow-hidden animate-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
      >
        {/* Accent Bar */}
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-amber-500 via-red-500 to-rose-600" />

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition cursor-pointer"
        >
          <X size={18} />
        </button>

        {/* Header */}
        <div className="flex items-start gap-4 mb-4">
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 shrink-0">
            <ShieldAlert size={28} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-bold px-2 py-0.5 bg-red-100 text-red-800 rounded border border-red-200 uppercase tracking-wide">
                Error 429 • RESOURCE_EXHAUSTED
              </span>
            </div>
            <h3 className="text-lg font-bold text-slate-900 leading-tight">
              Google Gemini API Quota Exhausted
            </h3>
          </div>
        </div>

        {/* Content Body */}
        <div className="space-y-3 text-sm text-slate-600 mb-6">
          <p className="leading-relaxed">
            Your Google Gemini API free-tier daily quota has been reached for <strong className="text-slate-800">gemini-3.1-flash-lite</strong>.
          </p>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 font-mono text-xs text-slate-700 break-words">
            {errorDetail || "429 RESOURCE_EXHAUSTED: Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests (limit: 500 requests/day)."}
          </div>

          <div className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 p-2.5 rounded-lg">
            <Clock size={16} className="shrink-0 mt-0.5 text-amber-600" />
            <span>
              <strong>When will it reset?</strong> Free tier quotas reset daily at <strong>midnight UTC (5:30 AM IST)</strong>. Alternatively, you can attach a billing card in Google AI Studio to unlock pay-as-you-go limits.
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-100">
          <a
            href="https://ai.google.dev/gemini-api/docs/rate-limits"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 hover:underline"
          >
            <span>Gemini Rate Limits Documentation</span>
            <ExternalLink size={12} />
          </a>

          <Button
            onClick={onClose}
            className="bg-slate-900 hover:bg-slate-800 text-white text-xs px-4 py-2"
          >
            Acknowledge & Close
          </Button>
        </div>
      </div>
    </div>
  );
}
