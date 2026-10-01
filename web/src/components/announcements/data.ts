"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { Announcement, Receipts } from "@/api/types";

export const newsKeys = {
  all: ["announcements"] as const,
  feed: ["announcements", "feed"] as const,
  unread: ["announcements", "unread"] as const,
  receipts: (id: string) => ["announcements", "receipts", id] as const,
};

export function useFeed(enabled = true) {
  return useQuery({ queryKey: newsKeys.feed, queryFn: () => api<Announcement[]>("/v1/announcements"), enabled });
}

export function useReceipts(id: string | null) {
  return useQuery({ queryKey: newsKeys.receipts(id ?? ""), queryFn: () => api<Receipts>(`/v1/announcements/${id}/receipts`), enabled: !!id });
}

export function useRefreshNews() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: newsKeys.all });
}
