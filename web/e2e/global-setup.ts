import { execSync } from "node:child_process";

/** Clears rate-limit counters so repeated local runs aren't throttled. */
export default function globalSetup(): void {
  const url = process.env.E2E_OWNER_DATABASE_URL ?? "postgresql://cm_owner:cm_owner@localhost:5432/companymgmt";
  try {
    execSync(`psql "${url}" -c "DELETE FROM rate_limits"`, { stdio: "ignore" });
  } catch {
    // The table may not exist before the first migration; the API server runs them.
  }
}
