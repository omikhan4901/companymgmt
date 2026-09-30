import type { ThemeConfig } from "antd";

/** antd theme from the ResumeX design system (plan §8.1). */
export const theme: ThemeConfig = {
  token: {
    colorPrimary: "#007B7B",
    colorLink: "#007B7B",
    colorTextBase: "#0f1f2a",
    colorBgLayout: "#f8fafc",
    fontFamily: '"Inter Variable", "Noto Sans Bengali", system-ui, sans-serif',
    borderRadius: 10,
    controlHeight: 40,
    // antd's default placeholder/secondary greys fail WCAG AA contrast; slate-500 passes (4.76:1).
    colorTextPlaceholder: "#64748b",
    colorTextQuaternary: "#64748b",
    colorTextTertiary: "#64748b",
    colorTextDescription: "#64748b",
  },
  components: {
    Button: { primaryShadow: "0 6px 16px -6px rgba(0,123,123,.5)", fontWeight: 500 },
    Table: { headerBg: "#f8fafc", headerColor: "#475569" },
    Modal: { titleFontSize: 18 },
  },
};
