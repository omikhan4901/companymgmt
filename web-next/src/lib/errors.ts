import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/api/client";
import i18n from "@/i18n";

/** A message a person can act on, from any error. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 412) return i18n.t("common.stale");
    if (error.status === 403 && error.code === "forbidden") return i18n.t("common.notAllowed");
    if (error.errors.length && !error.body.detail) return error.errors.map((e) => e.message).join(" ");
    return error.message;
  }
  if (error instanceof TypeError) return i18n.t("common.offline");
  return i18n.t("common.genericError");
}

/**
 * Puts field errors from the API next to the matching form fields. Returns true when at
 * least one field got an error (so the caller can skip a generic message).
 */
export function applyFieldErrors<T extends FieldValues>(setError: UseFormSetError<T>, fields: readonly string[], error: unknown): boolean {
  if (!(error instanceof ApiError) || !error.errors.length) return false;
  let applied = false;
  for (const e of error.errors) {
    if (fields.includes(e.field)) {
      setError(e.field as Path<T>, { type: "server", message: e.message });
      applied = true;
    }
  }
  return applied;
}
