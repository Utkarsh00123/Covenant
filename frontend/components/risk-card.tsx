"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RiskFlag, overrideRiskFlag } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function RiskCard({ flag }: { flag: RiskFlag }) {
  const [reason, setReason] = useState("");
  const [showOverrideMenu, setShowOverrideMenu] = useState(false);
  
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: (status: string) => overrideRiskFlag(flag.id, status, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document"] });
      toast({
        title: "Flag Updated",
        description: "The audit log has been permanently recorded.",
      });
    },
    onError: (error: any) => {
      toast({
        variant: "destructive",
        title: "Update Failed",
        description: error?.response?.data?.detail || "Could not record the override.",
      });
    }
  });

  const handleOverride = (status: string) => {
    if (reason.trim().length < 5) {
      toast({
        variant: "destructive",
        title: "Reason Required",
        description: "Please provide a detailed reason (at least 5 characters) for the audit log.",
      });
      return;
    }
    mutation.mutate(status);
  };

  // NEW: Unified heat-map color scaling for both the border and the badge
  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return { border: "border-l-red-700", badge: "bg-red-200 text-red-900 border-red-300" };
      case "HIGH": 
        return { border: "border-l-red-500", badge: "bg-red-100 text-red-800 border-red-200" };
      case "MEDIUM": 
        return { border: "border-l-orange-500", badge: "bg-orange-100 text-orange-800 border-orange-200" };
      case "LOW": 
        return { border: "border-l-yellow-400", badge: "bg-yellow-100 text-yellow-800 border-yellow-300" };
      default: 
        return { border: "border-l-slate-400", badge: "bg-slate-100 text-slate-800 border-slate-200" };
    }
  };

  const severityStyles = getSeverityStyles(flag.severity);

  if (flag.status !== "OPEN") {
    return (
      <div className="p-4 mb-4 border border-slate-200 rounded-lg bg-slate-50 opacity-70 transition-all">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className="font-semibold text-sm line-through text-slate-500">{flag.flag_type}</span>
            {flag.user_override_reason && (
              <span className="text-xs text-slate-400">"{flag.user_override_reason}"</span>
            )}
          </div>
          <Badge variant="outline">{flag.status}</Badge>
        </div>
      </div>
    );
  }

  return (
    <div className={`p-5 mb-4 border-l-4 border-y border-r border-slate-200 rounded-lg bg-white shadow-sm ${severityStyles.border}`}>
      
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          {/* Badge now inherits the heat-map colors dynamically */}
          <Badge variant="outline" className={`mb-2 mr-2 ${severityStyles.badge}`}>
            {flag.severity}
          </Badge>
          <Badge variant="outline" className="mb-2">{flag.flag_type}</Badge>
        </div>
        {flag.similarity_score && (
          <span className="text-xs font-medium text-slate-400 mt-1">
            {Math.round(flag.similarity_score * 100)}% match
          </span>
        )}
      </div>

      <h3 className="text-sm font-semibold text-slate-900 mb-1 flex items-center gap-2">
        Identified Risk
        <AlertCircle className={severityStyles.border.replace('border-l-', 'text-')} size={16} />
      </h3>
      <p className="text-sm text-slate-700 mb-4 bg-slate-50 p-3 rounded-md border border-slate-100">
        {flag.flag_reason}
      </p>

      {/* The Plain-English Recommendation Layer */}
      {flag.plain_english_explanation && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-slate-900 mb-1">Why change this?</h3>
          <p className="text-sm text-blue-800 bg-blue-50 p-3 rounded-md border border-blue-100">
            {flag.plain_english_explanation}
          </p>
        </div>
      )}

      {/* The Redline Diff Renderer */}
      {flag.redline_diff && flag.redline_diff.length > 0 && (
        <div className="mb-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-2">Suggested Redline Edit</h3>
          <div className="p-4 border border-slate-200 rounded-md bg-white text-sm leading-relaxed font-mono whitespace-pre-wrap">
            {flag.redline_diff.map((op, idx) => {
              if (op.operation === "delete") {
                return <span key={idx} className="bg-red-100 text-red-800 line-through rounded-sm decoration-red-500">{op.text}</span>;
              }
              if (op.operation === "insert") {
                return <span key={idx} className="bg-green-100 text-green-800 font-semibold rounded-sm underline decoration-green-500">{op.text}</span>;
              }
              return <span key={idx} className="text-slate-700">{op.text}</span>;
            })}
          </div>
        </div>
      )}

      {/* Action Toolbar (Human-in-the-Loop) */}
      {!showOverrideMenu ? (
        <div className="flex gap-2 mt-2">
          <Button onClick={() => setShowOverrideMenu(true)} className="w-full bg-slate-900 hover:bg-slate-800 gap-2 transition-all">
            <CheckCircle2 size={16} /> Resolve Risk
          </Button>
        </div>
      ) : (
        <div className="p-3 bg-slate-50 rounded-md border border-slate-200 mt-2 animate-in fade-in zoom-in-95 duration-200">
          <p className="text-xs font-semibold mb-2 text-slate-600">Audit Trail Reason (Required)</p>
          <input 
            type="text" 
            placeholder="e.g., 'Approved by Legal' or 'Accepted AI redline'" 
            className="w-full text-sm p-2 mb-3 border border-slate-300 rounded focus:ring-2 focus:ring-slate-500 outline-none transition-all"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={mutation.isPending}
            autoFocus
          />
          <div className="flex gap-2">
            <Button 
              size="sm" 
              onClick={() => handleOverride("ACCEPTED_REDLINE")} 
              className="bg-green-600 hover:bg-green-700 flex-1"
              disabled={mutation.isPending}
            >
              Accept Edit
            </Button>
            <Button 
              size="sm" 
              variant="destructive" 
              onClick={() => handleOverride("DISMISSED")} 
              className="flex-1"
              disabled={mutation.isPending}
            >
              Dismiss Flag
            </Button>
            <Button 
              size="sm" 
              variant="ghost" 
              onClick={() => {
                setShowOverrideMenu(false);
                setReason("");
              }}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}