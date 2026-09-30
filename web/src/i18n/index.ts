import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import bn from "./bn";
import en from "./en";

export type Lang = "en" | "bn";
const STORAGE_KEY = "cm.lang";

function initialLanguage(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "bn") return saved;
  } catch {
    // Storage can be unavailable (private mode); fall back to the browser language.
  }
  return navigator.language?.toLowerCase().startsWith("bn") ? "bn" : "en";
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, bn: { translation: bn } },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React escapes already
  returnNull: false,
});

function applyLang(lang: string): void {
  document.documentElement.lang = lang;
}
applyLang(i18n.language);
i18n.on("languageChanged", applyLang);

export function setLanguage(lang: Lang): void {
  void i18n.changeLanguage(lang);
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // ignore
  }
}

export function currentLang(): Lang {
  return i18n.language === "bn" ? "bn" : "en";
}

/** Locale for Intl formatting: Bangla digits in Bangla. */
export function intlLocale(): string {
  return currentLang() === "bn" ? "bn-BD" : "en-GB";
}

export default i18n;
