import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import pl from "./locales/pl.json";

function initialLang(): "pl" | "en" {
  try {
    const saved = localStorage.getItem("lang");
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  return "pl";
}

void i18n.use(initReactI18next).init({
  resources: { pl: { translation: pl }, en: { translation: en } },
  lng: initialLang(),
  fallbackLng: "pl",
  interpolation: { escapeValue: false },
});

export function setLang(lang: "pl" | "en"): void {
  void i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
  try {
    localStorage.setItem("lang", lang);
  } catch {
    /* storage unavailable */
  }
}

export default i18n;
