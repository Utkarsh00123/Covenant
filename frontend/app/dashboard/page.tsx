"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDocuments } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import UploadModal from "@/components/ui/upload-modal";

export default function DashboardPage() {
  const router = useRouter();
  
  // React Query automatically handles loading states and caching
  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: fetchDocuments,
    refetchInterval: 5000, // Poll every 5 seconds to update processing status
  });

  const getRiskBadgeColor = (risk: string) => {
    switch (risk) {
      case "LOW": return "bg-green-100 text-green-800 hover:bg-green-200 border-green-200";
      case "MEDIUM": return "bg-yellow-100 text-yellow-800 hover:bg-yellow-200 border-yellow-200";
      case "HIGH": 
      case "CRITICAL": return "bg-red-100 text-red-800 hover:bg-red-200 border-red-200";
      default: return "bg-slate-100 text-slate-800 hover:bg-slate-200 border-slate-200";
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Document Intelligence</h1>
          <p className="text-slate-500 mt-1">Review contracts and invoices for risks.</p>
        </div>
        <UploadModal />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-500 animate-pulse">Loading documents...</div>
        ) : !documents || documents.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            No documents uploaded yet. Click "Upload Document" to begin.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="p-4 font-semibold text-slate-600">Document Name</th>
                <th className="p-4 font-semibold text-slate-600">Type</th>
                <th className="p-4 font-semibold text-slate-600">Status</th>
                <th className="p-4 font-semibold text-slate-600">Risk Score</th> {/* NEW COLUMN */}
                <th className="p-4 font-semibold text-slate-600">Risk Level</th>
                <th className="p-4 font-semibold text-slate-600 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} className="border-b border-slate-100 hover:bg-slate-50 transition">
                  <td className="p-4 font-medium text-slate-900">{doc.filename}</td>
                  <td className="p-4 text-slate-600 uppercase">{doc.document_type}</td>
                  <td className="p-4 text-slate-600">
                    <span className="capitalize">{doc.status.toLowerCase()}</span>
                  </td>
                  <td className="p-4 text-slate-600 font-medium">
                    {/* Display the calculated score we built in the backend */}
                    {doc.numeric_score !== null && doc.numeric_score !== undefined 
                      ? <span className={doc.numeric_score > 60 ? "text-red-600" : ""}>{doc.numeric_score} / 100</span>
                      : "-"}
                  </td>
                  <td className="p-4">
                    <Badge 
                      variant="outline" // Forces Shadcn to drop the black background
                      className={`${getRiskBadgeColor(doc.risk_level)} border`}
                    >
                      {doc.risk_level}
                    </Badge>
                  </td>
                  <td className="p-4 text-right">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => router.push(`/dashboard/review/${doc.id}`)}
                      disabled={doc.status === "PENDING" || doc.status === "FAILED"}
                    >
                      {doc.status === "PENDING" ? "Processing..." : "Review"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}