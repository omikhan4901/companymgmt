"use client";

import { useEffect, useRef } from "react";

const SITE_KEY: string | undefined = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: { sitekey: string; callback: (token: string) => void; language?: string }) => string;
      remove: (id: string) => void;
    };
  }
}

let loading: Promise<void> | null = null;
function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("captcha"));
      document.head.appendChild(script);
    });
  }
  return loading;
}

export const captchaAvailable = Boolean(SITE_KEY);

/** Cloudflare Turnstile, shown only after repeated failed sign-ins. */
export function Turnstile({ onToken, language }: { onToken: (token: string) => void; language: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!SITE_KEY) return;
    let id: string | undefined;
    void loadScript().then(() => {
      if (ref.current && window.turnstile) {
        id = window.turnstile.render(ref.current, { sitekey: SITE_KEY, callback: onToken, language });
      }
    });
    return () => {
      if (id && window.turnstile) window.turnstile.remove(id);
    };
  }, [onToken, language]);
  return <div ref={ref} className="my-2" />;
}
