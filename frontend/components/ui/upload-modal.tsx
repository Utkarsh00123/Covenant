"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadDocument } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { UploadCloud, FileText } from "lucide-react";
// Make sure this path matches where Shadcn installed your toast hook
import { useToast } from "@/hooks/use-toast"; 

export default function UploadModal() {
  const [open, setOpen] = useState(false);
  const [docType, setDocType] = useState("contract");
  
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // 1. Pass both file and type as a single variable object to prevent stale closures
  const mutation = useMutation({
    mutationFn: (variables: { file: File; type: string }) => 
      uploadDocument(variables.file, variables.type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      setOpen(false);
      toast({
        title: "Upload Successful",
        description: "Your document is now being analyzed by the AI.",
      });
    },
    onError: (error: any) => {
      toast({
        variant: "destructive",
        title: "Upload Failed",
        description: error?.response?.data?.detail || "An error occurred while communicating with the server.",
      });
    }
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      // 2. Explicitly pass the current docType state at the exact moment of the drop
      mutation.mutate({ file: acceptedFiles[0], type: docType });
    }
  }, [mutation, docType]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: mutation.isPending // Prevent dropping a second file while uploading
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <UploadCloud size={18} /> Upload Document
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload for AI Analysis</DialogTitle>
        </DialogHeader>
        
        <div className="flex gap-4 mb-4">
          <Button 
            variant={docType === "contract" ? "default" : "outline"} 
            onClick={() => setDocType("contract")}
            disabled={mutation.isPending}
          >
            Contract
          </Button>
          <Button 
            variant={docType === "invoice" ? "default" : "outline"} 
            onClick={() => setDocType("invoice")}
            disabled={mutation.isPending}
          >
            Invoice
          </Button>
        </div>

        <div 
          {...getRootProps()} 
          className={`border-2 border-dashed rounded-xl p-10 text-center transition ${
            mutation.isPending ? "cursor-not-allowed opacity-70" : "cursor-pointer"
          } ${
            isDragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:bg-slate-50"
          }`}
        >
          <input {...getInputProps()} />
          <FileText className="mx-auto h-10 w-10 text-slate-400 mb-4" />
          
          {mutation.isPending ? (
            <p className="text-sm font-medium text-blue-600 animate-pulse">
              Uploading and analyzing...
            </p>
          ) : (
            <p className="text-sm text-slate-600">
              Drag & drop a PDF here, or click to select.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}