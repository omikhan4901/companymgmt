"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export const MODES = ["light", "dark", "system"] as const;
export const ACCENTS = ["plum", "saffron", "garnet", "ink"] as const;
export type Mode = (typeof MODES)[number];
export type Accent = (typeof ACCENTS)[number];

/** Swatch colours for the pickers (light, dark). Must match globals.css. */
export const ACCENT_SWATCH: Record<Accent, [string, string]> = {
  plum: ["#6d28d9", "#a78bfa"],
  saffron: ["#b45309", "#f59e0b"],
  garnet: ["#9f1239", "#fb7185"],
  ink: ["#18181b", "#e4e4e7"],
};

const MODE_KEY = "cm.theme";
const ACCENT_KEY = "cm.accent";

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage can be blocked; the choice then lasts for this visit only.
  }
}

function systemDark(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Applies a mode and accent to <html> (same rules as public/theme-init.js). */
export function applyTheme(mode: Mode, accent: Accent): void {
  const root = document.documentElement;
  root.classList.toggle("dark", mode === "dark" || (mode === "system" && systemDark()));
  if (accent === "plum") root.removeAttribute("data-accent");
  else root.setAttribute("data-accent", accent);
}

interface ThemeValue {
  mode: Mode;
  accent: Accent;
  /** The mode actually shown (system resolved). */
  resolved: "light" | "dark";
  setMode: (mode: Mode) => void;
  setAccent: (accent: Accent) => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>("light");
  const [accent, setAccentState] = useState<Accent>("plum");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const m = read(MODE_KEY, MODES, "light");
    const a = read(ACCENT_KEY, ACCENTS, "plum");
    setModeState(m);
    setAccentState(a);
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  // Follow the operating system while in "system" mode.
  useEffect(() => {
    if (mode !== "system" || typeof matchMedia !== "function") return;
    const query = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      applyTheme("system", accent);
      setDark(query.matches);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [mode, accent]);

  const setMode = useCallback(
    (next: Mode) => {
      setModeState(next);
      write(MODE_KEY, next);
      applyTheme(next, accent);
      setDark(document.documentElement.classList.contains("dark"));
    },
    [accent],
  );

  const setAccent = useCallback(
    (next: Accent) => {
      setAccentState(next);
      write(ACCENT_KEY, next);
      applyTheme(mode, next);
    },
    [mode],
  );

  const value = useMemo<ThemeValue>(
    () => ({ mode, accent, resolved: dark ? "dark" : "light", setMode, setAccent }),
    [mode, accent, dark, setMode, setAccent],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme outside ThemeProvider");
  return value;
}
