/** Friendly names for the generated OpenAPI schema types. */
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["MeOut"];
export type CurrentWorkspace = S["CurrentWorkspace"];
export type WorkspaceRef = S["WorkspaceRef"];
export type Plan = S["PublicPlan"];
export type Workspace = S["WorkspaceOut"];
export type Member = S["MemberOut"];
export type Role = S["RoleOut"];
export type Permission = S["PermissionOut"];
export type Invite = S["InviteOut"];
export type Branch = S["BranchOut"];
export type AuditEvent = S["AuditOut"];
export type Session = S["SessionOut"];
export type Department = S["DepartmentOut"];
export type Employee = S["EmployeeOut"];
export type AttendanceRecord = S["RecordOut"];
export type AttendanceStatus = S["StatusOut"];
export type Correction = S["CorrectionOut"];
export type Timesheet = S["TimesheetOut"];
export type Present = S["PresentOut"];
export type StaffCreated = S["StaffOut"];

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Token {
  access_token: string;
  expires_at: string;
}

export interface LoginResult {
  mfa_required: boolean;
  challenge: string | null;
  access_token: string | null;
}
