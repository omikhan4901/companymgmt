"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, onAuthChange, refreshSession, setAccessToken } from "@/api/client";
import type { CurrentWorkspace, Me, Token } from "@/api/types";
import i18n, { currentLang, preferredLanguage, setLanguage } from "@/i18n";

interface SessionValue {
  ready: boolean;
  signedIn: boolean;
  me: Me | null;
  workspace: CurrentWorkspace | null;
  can: (permission: string) => boolean;
  hasModule: (module: string) => boolean;
  signIn: (token: Token | { access_token: string }) => Promise<void>;
  signOut: () => Promise<void>;
  switchWorkspace: (tenantId: string) => Promise<void>;
  reload: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [booted, setBooted] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => onAuthChange(setSignedIn), []);

  // The page is pre-rendered in English; switch to the saved or browser language.
  useEffect(() => {
    const lang = preferredLanguage();
    if (lang !== currentLang()) void i18n.changeLanguage(lang);
  }, []);

  // On load, the refresh cookie (if any) gets us a fresh access token.
  useEffect(() => {
    let cancelled = false;
    void refreshSession().finally(() => {
      if (!cancelled) setBooted(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/v1/auth/me"),
    enabled: booted && signedIn,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });

  const me = signedIn ? (meQuery.data ?? null) : null;
  const workspace = me?.workspace ?? null;

  // The user's saved language wins once we know it.
  useEffect(() => {
    if (me && (me.locale === "en" || me.locale === "bn") && me.locale !== currentLang()) {
      setLanguage(me.locale);
    }
  }, [me]);

  const signIn = useCallback(
    async (token: { access_token: string }) => {
      setAccessToken(token.access_token);
      queryClient.clear();
      await queryClient.fetchQuery({ queryKey: ["me"], queryFn: () => api<Me>("/v1/auth/me") });
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    try {
      await api("/v1/auth/logout", { method: "POST" });
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
    }
    setAccessToken(null);
    queryClient.clear();
  }, [queryClient]);

  const switchWorkspace = useCallback(
    async (tenantId: string) => {
      const token = await api<Token>("/v1/auth/switch", { body: { tenant_id: tenantId } });
      await signIn(token);
    },
    [signIn],
  );

  const reload = useCallback(async () => {
    await queryClient.invalidateQueries();
  }, [queryClient]);

  const value = useMemo<SessionValue>(() => {
    const permissions = new Set(workspace?.permissions ?? []);
    const modules = new Set(workspace?.plan.modules ?? []);
    return {
      ready: booted && (!signedIn || !meQuery.isPending),
      signedIn: signedIn && !!me,
      me,
      workspace,
      can: (p) => permissions.has(p),
      hasModule: (m) => modules.has(m),
      signIn,
      signOut,
      switchWorkspace,
      reload,
    };
  }, [booted, signedIn, meQuery.isPending, me, workspace, signIn, signOut, switchWorkspace, reload]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}

/** The current workspace; only use inside routes that require one. */
export function useWorkspace(): CurrentWorkspace {
  const { workspace } = useSession();
  if (!workspace) throw new Error("No workspace");
  return workspace;
}
