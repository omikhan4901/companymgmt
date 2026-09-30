import { useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { AttendanceSettings, AttendanceStatus, Branch, Correction, Department, Plan, Present, Role, Timesheet } from "./types";

export const keys = {
  status: ["attendance", "status"] as const,
  present: ["attendance", "present"] as const,
  corrections: (status: string, mine: boolean) => ["attendance", "corrections", status, mine] as const,
  records: (filters: object) => ["attendance", "records", filters] as const,
  timesheet: (month: string) => ["attendance", "timesheet", month] as const,
  departments: ["departments"] as const,
  branches: ["branches"] as const,
  roles: ["roles"] as const,
  people: (filters: object) => ["people", filters] as const,
  members: (status: string) => ["members", status] as const,
  invites: ["invites"] as const,
  plans: ["plans"] as const,
  sessions: ["sessions"] as const,
  audit: (filters: object) => ["audit", filters] as const,
};

export function useAttendanceStatus(enabled = true) {
  return useQuery({ queryKey: keys.status, queryFn: () => api<AttendanceStatus>("/v1/attendance/status"), enabled, refetchInterval: 60_000 });
}

export function usePresent(enabled = true) {
  return useQuery({ queryKey: keys.present, queryFn: () => api<Present[]>("/v1/attendance/present"), enabled, refetchInterval: 60_000 });
}

export function useCorrections(status = "pending", mine = false, enabled = true) {
  return useQuery({
    queryKey: keys.corrections(status, mine),
    queryFn: () => api<Correction[]>("/v1/attendance/corrections", { query: { status, mine } }),
    enabled,
  });
}

export function useDepartments(enabled = true) {
  return useQuery({ queryKey: keys.departments, queryFn: () => api<Department[]>("/v1/departments"), enabled });
}

export function useBranches(enabled = true) {
  return useQuery({ queryKey: keys.branches, queryFn: () => api<Branch[]>("/v1/branches"), enabled });
}

export function useRoles(enabled = true) {
  return useQuery({ queryKey: keys.roles, queryFn: () => api<Role[]>("/v1/roles"), enabled });
}

export function usePlans() {
  return useQuery({ queryKey: keys.plans, queryFn: () => api<Plan[]>("/v1/plans"), staleTime: 3_600_000 });
}

/** Department options for selects, indented to show the tree. */
export function departmentOptions(departments: Department[] | undefined): { value: string; label: string }[] {
  if (!departments) return [];
  const children = new Map<string | null, Department[]>();
  for (const d of departments) {
    const list = children.get(d.parent_id ?? null) ?? [];
    list.push(d);
    children.set(d.parent_id ?? null, list);
  }
  const out: { value: string; label: string }[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const d of (children.get(parent) ?? []).sort((a, b) => a.name.localeCompare(b.name))) {
      out.push({ value: d.id, label: `${" ".repeat(depth)}${d.name}` });
      if (depth < 20) walk(d.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

export function useTimesheet(month: string, enabled = true) {
  return useQuery({
    queryKey: keys.timesheet(month),
    queryFn: () => api<Timesheet>("/v1/attendance/timesheet", { query: { month } }),
    enabled,
  });
}

export function useAttendanceSettings(enabled = true) {
  return useQuery({ queryKey: ["attendance", "settings"], queryFn: () => api<AttendanceSettings>("/v1/attendance/settings"), enabled });
}
