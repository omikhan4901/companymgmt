"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { PageLoading } from "@/components/ui/spinner";

import { useSession } from "./session";

/** Where a signed-in person should be sent, or null if they may stay. */
function redirectFor(pathname: string, me: ReturnType<typeof useSession>["me"]): string | null {
  if (!me) return null;
  if (me.must_change_password && pathname !== "/change-password") return "/change-password";
  if (!me.workspace && !pathname.startsWith("/app/account")) return "/app/account";
  return null;
}

export function RequireSession({ children }: { children: ReactNode }) {
  const { ready, signedIn, me } = useSession();
  const pathname = usePathname();
  const search = useSearchParams();
  const router = useRouter();
  const target = !ready
    ? null
    : !signedIn || !me
      ? `/login${pathname === "/app" ? "" : `?next=${encodeURIComponent(pathname + (search.size ? `?${search}` : ""))}`}`
      : redirectFor(pathname, me);

  useEffect(() => {
    if (target) router.replace(target);
  }, [target, router]);

  if (!ready || target) return <PageLoading />;
  return <>{children}</>;
}

export function PublicOnly({ children }: { children: ReactNode }) {
  const { ready, signedIn } = useSession();
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next");
  const target = ready && signedIn ? (next && next.startsWith("/app") ? next : "/app") : null;

  useEffect(() => {
    if (target) router.replace(target);
  }, [target, router]);

  if (!ready || target) return <PageLoading />;
  return <>{children}</>;
}
