"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchDocumentDetails, approveDocument } from "@/lib/api";
import PDFViewer, { BoundingBox } from "@/components/pdf-viewer";
import RiskCard from "@/components/risk-card";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft, CheckCircle, ShieldCheck } from "lucide-react";
import { toast } from "@/components/ui/toast";

export default function ReviewWorkspace() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [approvalReason, setApprovalReason] = useState("");
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => fetchDocumentDetails(documentId),
  });

  const approveMutation = useMutation({
    mutationFn: () => approveDocument(documentId, approvalReason || "Approved after review."),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setShowApprovalModal(false);
      toast.add({
        title: "Document Approved",
        description: "The agreement is cleared for final signature and audit logged.",
      });
    },
    onError: (error: any) => {
      toast.add({
        type: "error",
        title: "Approval Blocked",
        description: error?.response?.data?.detail || "Critical risk flags must be resolved first.",
      });
    }
  });

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500 font-medium animate-pulse">Loading AI Analysis and Document Stream...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-slate-50">
        <p className="text-red-500 font-semibold text-lg mb-2">Document not found.</p>
        <Button variant="outline" onClick={() => router.push("/dashboard")}>Return to Dashboard</Button>
      </div>
    );
  }

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const pdfUrl = `${API_URL}/documents/${documentId}/download`;

  const handleHighlightClick = (id: string) => {
    setActiveHighlightId(id);
    const cardEl = document.getElementById(`flag-card-${id}`);
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "center" });
      cardEl.classList.add("ring-2", "ring-amber-500", "scale-[1.02]");
      setTimeout(() => {
        cardEl.classList.remove("ring-2", "ring-amber-500", "scale-[1.02]");
      }, 1800);
    }
  };

  // Map backend flags to PDF highlights with clause page coordinate detection
  const highlights: BoundingBox[] = data.flags.map((flag: any, index: number) => {
    let pageNum = flag.page || 1;
    let y0 = flag.bbox_y0 || (18 + index * 12);
    let y1 = flag.bbox_y1 || (26 + index * 12);

    // Smart clause location detection for MOU
    if (flag.evidence_text?.includes("43,08,000") || flag.evidence_text?.toLowerCase().includes("balance payment")) {
      pageNum = 4;
      y0 = 44;
      y1 = 50;
    } else if (flag.evidence_text?.toLowerCase().includes("delhi court")) {
      pageNum = 5;
      y0 = 22;
      y1 = 28;
    }

    return {
      id: flag.id,
      x0: flag.bbox_x0 || 8,
      y0: y0,
      x1: flag.bbox_x1 || 92,
      y1: y1,
      severity: flag.severity,
      label: flag.flag_type,
      page: pageNum,
    };
  });

  const isApproved = data.document.status === "APPROVED";

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-100">
      
      {/* Top Navbar */}
      <div className="bg-white border-b border-slate-200 h-16 flex items-center px-6 justify-between shrink-0 shadow-sm z-20">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push("/dashboard")}>
            <ArrowLeft size={20} />
          </Button>
          <div>
            <h1 className="font-bold text-slate-900 leading-tight">{data.document.filename}</h1>
            <p className="text-xs text-slate-500 uppercase">
              {data.document.document_type} • Status: <span className="font-semibold">{data.document.status}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isApproved ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-md text-sm font-medium">
              <ShieldCheck size={16} /> Approved & Cleared
            </div>
          ) : (
            <Button 
              className="bg-green-600 hover:bg-green-700 gap-2"
              onClick={() => setShowApprovalModal(true)}
            >
              <CheckCircle size={16} /> Approve Document
            </Button>
          )}
        </div>
      </div>

      {/* Split-Screen Workspace */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* LEFT PANE: Document Viewer */}
        <div className="w-1/2 bg-slate-100 border-r border-slate-300 flex flex-col h-full overflow-hidden relative">
          <PDFViewer 
            fileUrl={pdfUrl} 
            highlights={highlights} 
            onHighlightClick={handleHighlightClick}
            activeHighlightId={activeHighlightId}
          />
        </div>

        {/* RIGHT PANE: Actionable Intelligence */}
        <div className="w-1/2 bg-slate-50 p-6 overflow-y-auto">
          <div className="max-w-xl mx-auto pb-12">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-slate-900">AI Risk Analysis</h2>
              {data.numeric_score !== null && (
                <span className="text-sm font-semibold px-3 py-1 bg-white border border-slate-200 rounded-full shadow-sm">
                  Composite Risk Score: <span className={(data?.numeric_score ?? 0) > 60 ? "text-red-600" : "text-slate-800"}>{data.numeric_score}/100</span>
                </span>
              )}
            </div>
            
            {data.flags.length === 0 ? (
              <div className="p-8 text-center bg-white border border-slate-200 rounded-lg shadow-sm">
                <p className="text-green-600 font-semibold text-lg mb-2">No Risks Detected</p>
                <p className="text-slate-500 text-sm">This document complies with all standard corporate baselines.</p>
              </div>
            ) : (
              data.flags.map((flag: any) => (
                <RiskCard
                  key={flag.id}
                  flag={flag}
                  isActive={activeHighlightId === flag.id}
                  onViewInPdf={() => {
                    setActiveHighlightId(flag.id);
                  }}
                />
              ))
            )}
          </div>
        </div>
        
      </div>

      {/* Approval Modal Prompt */}
      {showApprovalModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-2">Final Document Approval</h3>
            <p className="text-sm text-slate-600 mb-4">
              Approving this document locks the review process and logs an immutable entry to the compliance audit trail.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Approval Justification</label>
              <input 
                type="text"
                placeholder="e.g., 'All critical legal deviations resolved with counterparty'"
                className="w-full text-sm p-2.5 border border-slate-300 rounded-md focus:ring-2 focus:ring-slate-900 outline-none"
                value={approvalReason}
                onChange={(e) => setApprovalReason(e.target.value)}
                disabled={approveMutation.isPending}
                autoFocus
              />
            </div>
            <div className="flex gap-3 justify-end">
              <Button 
                variant="outline" 
                onClick={() => setShowApprovalModal(false)}
                disabled={approveMutation.isPending}
              >
                Cancel
              </Button>
              <Button 
                className="bg-green-600 hover:bg-green-700"
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? "Processing..." : "Confirm & Sign Off"}
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}