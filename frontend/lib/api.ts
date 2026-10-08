import axios from "axios";

// Automatically falls back to localhost if the environment variable is missing
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ---------------------------------------------------------
// TypeScript Interfaces (Aligned with Backend Pydantic)
// ---------------------------------------------------------

export interface DocumentItem {
  id: string;
  filename: string;
  document_type: string;
  status: string;
  created_at: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "PENDING";
  numeric_score?: number | null;
}

export interface DiffOperation {
  operation: "insert" | "delete" | "equal";
  text: string;
}

export interface RiskFlag {
  id: string;
  flag_type: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  flag_reason: string;
  evidence_text: string;
  baseline_text: string | null;
  suggested_redline: string | null;
  plain_english_explanation: string | null;
  redline_diff: DiffOperation[] | null;
  
  // Auditing fields
  similarity_score?: number | null;
  status: string;
  user_override_reason?: string | null;
}

export interface DocumentDetail {
  document: DocumentItem;
  numeric_score?: number | null;
  risk_summary?: Record<string, number> | null;
  extracted_intelligence?: any;
  flags: RiskFlag[];
}

// ---------------------------------------------------------
// API Functions
// ---------------------------------------------------------

export const fetchDocuments = async (): Promise<DocumentItem[]> => {
  const { data } = await apiClient.get("/dashboard/documents");
  return data;
};

export const fetchDocumentDetails = async (id: string): Promise<DocumentDetail> => {
  const { data } = await apiClient.get(`/dashboard/documents/${id}`);
  return data;
};

export const uploadDocument = async (file: File, type: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", type);
  
  // Override the global application/json header so the browser can send the PDF file
  const { data } = await apiClient.post("/documents/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return data;
};

export const overrideRiskFlag = async (flagId: string, status: string, reason: string) => {
  const { data } = await apiClient.post(`/workflow/flags/${flagId}/override`, {
    status,
    reason,
  });
  return data;
};

export const approveDocument = async (documentId: string, reason: string) => {
  const { data } = await apiClient.post(`/workflow/documents/${documentId}/approve`, {
    reason,
  });
  return data;
};