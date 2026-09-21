/** Tailwind config extended 1:1 from the :root tokens in
 * frontend/ui-reference/sanjeevani-flow.html (see CLAUDE.md "UI-first workflow").
 * Dark theme only — no light-mode variants are defined.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0E1512",
        "bg-2": "#131D1A",
        surface: "#17231F",
        "surface-2": "#1D2C27",
        line: "#25382F",
        "line-soft": "#1F302A",
        accent: "#84D3B8",
        "accent-ink": "#0B1714",
        "accent-dim": "#2E5347",
        "accent-soft": "#1B2F29",
        ok: "#84D3B8",
        warn: "#E3B461",
        "warn-soft": "#2E2718",
        bad: "#E08A7E",
        "bad-soft": "#2E1E1C",
        text: "#E9F1EE",
        "text-2": "#A7BCB5",
        "text-3": "#728880",
      },
      borderRadius: {
        r: "14px",
        "r-lg": "20px",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
