"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { Doc, DocAcks, DocDetail } from "@/api/types";

export const docKeys = {
  all: ["documents"] as const,
  library: (archived: boolean) => ["documents", "library", archived] as const,
  pending: ["documents", "pending"] as const,
  one: (id: string) => ["documents", "one", id] as const,
  acks: (id: string) => ["documents", "acks", id] as const,
};

export const CATEGORIES = ["policy", "handbook", "sop", "form", "other"] as const;

export function useLibrary(archived = false, enabled = true) {
  return useQuery({ queryKey: docKeys.library(archived), queryFn: () => api<Doc[]>("/v1/documents", { query: { archived } }), enabled });
}

export function useToAcknowledge(enabled = true) {
  return useQuery({ queryKey: docKeys.pending, queryFn: () => api<Doc[]>("/v1/documents/to-acknowledge"), enabled });
}

export function useDocument(id: string | null) {
  return useQuery({ queryKey: docKeys.one(id ?? ""), queryFn: () => api<DocDetail>(`/v1/documents/${id}`), enabled: !!id, retry: false });
}

export function useAcks(id: string | null) {
  return useQuery({ queryKey: docKeys.acks(id ?? ""), queryFn: () => api<DocAcks>(`/v1/documents/${id}/acknowledgements`), enabled: !!id });
}

export function useRefreshDocs() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: docKeys.all });
}

/** Send a file as the raw request body, as the API expects. */
export function uploadVersion(documentId: string, file: File, note?: string) {
  return api<DocDetail>(`/v1/documents/${documentId}/versions`, {
    query: { filename: file.name, note: note || undefined },
    rawBody: new Blob([file], { type: "application/octet-stream" }),
  });
}

export function formatSize(bytes: number, locale: string): string {
  const units = ["B", "KB", "MB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: unit ? 1 : 0 }).format(value)} ${units[unit]}`;
}
