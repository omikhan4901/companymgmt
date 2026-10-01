"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { Project, Task, TaskComment, TaskDetail } from "@/api/types";

export const taskKeys = {
  all: ["tasks"] as const,
  projects: (status: string) => ["tasks", "projects", status] as const,
  project: (id: string) => ["tasks", "project", id] as const,
  list: (filters: object) => ["tasks", "list", filters] as const,
  myWork: ["tasks", "my-work"] as const,
  task: (id: string) => ["tasks", "task", id] as const,
  comments: (id: string) => ["tasks", "comments", id] as const,
};

export function useProjects(status = "active", enabled = true) {
  return useQuery({ queryKey: taskKeys.projects(status), queryFn: () => api<Project[]>("/v1/projects", { query: { status } }), enabled });
}

export function useProject(id: string | null) {
  return useQuery({ queryKey: taskKeys.project(id ?? ""), queryFn: () => api<Project>(`/v1/projects/${id}`), enabled: !!id });
}

export function useTasks(filters: { project_id?: string; status?: string }, enabled = true) {
  return useQuery({ queryKey: taskKeys.list(filters), queryFn: () => api<Task[]>("/v1/tasks", { query: filters }), enabled });
}

export function useMyWork(enabled = true) {
  return useQuery({ queryKey: taskKeys.myWork, queryFn: () => api<Task[]>("/v1/tasks/my-work"), enabled });
}

export function useTask(id: string | null) {
  return useQuery({ queryKey: taskKeys.task(id ?? ""), queryFn: () => api<TaskDetail>(`/v1/tasks/${id}`), enabled: !!id, retry: false });
}

export function useComments(id: string | null) {
  return useQuery({ queryKey: taskKeys.comments(id ?? ""), queryFn: () => api<TaskComment[]>(`/v1/tasks/${id}/comments`), enabled: !!id });
}

/** Everything about tasks is refetched after a change: lists, counts and the open task. */
export function useRefreshTasks() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: taskKeys.all });
}

export const STATUSES = ["todo", "doing", "done"] as const;
export const PRIORITIES = ["urgent", "high", "normal", "low"] as const;
export type Status = (typeof STATUSES)[number];
export type Priority = (typeof PRIORITIES)[number];
