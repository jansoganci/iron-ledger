/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Exact hex values from docs/design.md §Palette
        canvas: "#FAFAF9",
        surface: "#FFFFFF",
        border: "#E5E4E2",
        text: {
          primary: "#1A1A1A",
          secondary: "#6B6B6B",
        },
        accent: "#0D9488",
        // Severity system — color carries meaning, never decoration
        severity: {
          high: { bg: "#FEE2E2", fg: "#C53030" },
          medium: { bg: "#FEF3C7", fg: "#B45309" },
          normal: { bg: "#F3F4F6", fg: "#6B7280" }, // gray, NOT green
        },
        // Favorable variance direction — green reserved for favorable only
        favorable: { bg: "#ECFDF5", fg: "#166534" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["Source Serif 4", "Georgia", "Cambria", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
