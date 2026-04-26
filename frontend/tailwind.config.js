/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── SEMANTIC SURFACE TOKENS (v2) ──────────────────────────────────
        canvas: "#FAFAF8",          // warm stone off-white (was #FAFAF9)
        surface: "#FFFFFF",
        border: "#E9E8E4",          // updated warm stone border (was #E5E4E2)
        "border-strong": "#D5D3CE", // new: stronger divider

        // ── SEMANTIC TEXT TOKENS (v2) ─────────────────────────────────────
        text: {
          primary:   "#252421", // warm stone dark (was #1A1A1A)
          secondary: "#787670", // (was #6B6B6B)
          tertiary:  "#9A9892", // new
          disabled:  "#BAB8B2", // new
        },

        // ── NEUTRAL / WARM STONE SCALE ────────────────────────────────────
        neutral: {
          50:  "#FAFAF8",
          100: "#F4F3F0",
          200: "#E9E8E4",
          300: "#D5D3CE",
          400: "#BAB8B2",
          500: "#9A9892",
          600: "#787670",
          700: "#5A5853",
          800: "#3C3A36",
          900: "#252421",
          950: "#151412",
        },

        // ── AMBER / PRIMARY CTA (replaces teal as primary) ────────────────
        // oklch ~0.68 0.17 54 — warm amber, approachable, high-contrast
        amber: {
          50:  "#FFF8ED",
          100: "#FFEECE",
          200: "#FEDA9A",
          300: "#FDC060",
          400: "#FBA12A",
          500: "#F08408", // --accent-primary
          600: "#C46600", // --accent-primary-dark (hover)
          700: "#9A4D00", // --accent-primary-text (text on light bg)
          800: "#763900",
          900: "#572900",
          950: "#371800",
        },

        // ── EMERALD / REWARD + FAVORABLE ─────────────────────────────────
        // oklch ~0.60 0.16 152 — trustworthy green, replaces Tailwind default
        emerald: {
          50:  "#EDFAF3",
          100: "#D1F4E4",
          200: "#A3E8CA",
          300: "#68D4A8",
          400: "#34BB83",
          500: "#16A066", // --accent-reward
          600: "#0F7F50", // --accent-reward-dark
          700: "#0A613C", // --accent-reward-text
          800: "#07472C",
          900: "#04311E",
          950: "#021E12",
        },

        // ── VIOLET / AGENTIC ──────────────────────────────────────────────
        // oklch ~0.58 0.16 282 — signals AI/agent activity
        violet: {
          50:  "#F3F1FD",
          100: "#E5DFFB",
          200: "#CABEF7",
          300: "#A897F0",
          400: "#8570E6",
          500: "#6651D4", // --accent-agent
          600: "#4F3DAE", // --accent-agent-dark
          700: "#3A2C87", // --accent-agent-text
          800: "#281D63",
          900: "#1A1244",
          950: "#0E0928",
        },

        // ── TEAL / UTILITY (demoted — legacy use only) ────────────────────
        // Teal #0D9488 is now the "utility" accent, not primary.
        // Use only for guardrail badge, verified badge, misc utility UI.
        teal: {
          400: "#2DD4BF",
          500: "#14B8A6",
          600: "#0D9488", // --accent-utility (was primary accent)
          700: "#0F766E",
        },

        // ── PRIMARY ACCENT ALIAS ──────────────────────────────────────────
        // bg-accent / text-accent / ring-accent all point to amber-500 now.
        // Teal is accessed via bg-teal-600 / text-teal-600 where needed.
        accent: "#F08408", // amber-500 — primary CTA color

        // ── SEVERITY SYSTEM (v2) ──────────────────────────────────────────
        // Color carries meaning, never decoration. Revised for v2:
        // medium → amber-family (not yellow); favorable → emerald-family
        severity: {
          high: {
            bg:     "#FEF0F0",
            fg:     "#B91C1C",
            border: "#FECACA",
          },
          medium: {
            bg:     "#FFF8ED", // amber-50 (was yellowish #FEF3C7)
            fg:     "#9A4D00", // amber-700 (was #B45309)
            border: "#FEDA9A", // amber-200
          },
          normal: {
            bg:     "#F4F3F0", // neutral-100 (was #F3F4F6)
            fg:     "#787670", // neutral-600 (was #6B7280)
            border: "#E9E8E4", // neutral-200
          },
        },

        // Favorable variance — emerald-family (not generic green)
        favorable: {
          bg:     "#EDFAF3", // emerald-50 (was #ECFDF5)
          fg:     "#0A613C", // emerald-700 (was #166534)
          border: "#A3E8CA", // emerald-200
        },
      },

      fontFamily: {
        sans:  ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        // Source Serif 4 — used for hero numbers (KPI values, report headers)
        serif: ["Source Serif 4", "Georgia", "Cambria", "serif"],
        // JetBrains Mono — used for data cells, codes, amounts
        mono:  ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },

      // Motion tokens mirror CSS custom properties
      transitionDuration: {
        instant: "80ms",
        fast:    "140ms",
        base:    "220ms",
        slow:    "380ms",
        reward:  "650ms",
      },

      transitionTimingFunction: {
        "ease-out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
        "ease-spring":   "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },

      // Radius tokens
      borderRadius: {
        xs:   "3px",
        sm:   "5px",
        // md / lg / xl use Tailwind defaults (6px, 8px, 12px) — close enough
      },

      // Shadow tokens
      boxShadow: {
        xs:      "0 1px 2px oklch(0.14 0.01 60 / 0.06)",
        sm:      "0 2px 6px oklch(0.14 0.01 60 / 0.08), 0 1px 2px oklch(0.14 0.01 60 / 0.04)",
        md:      "0 4px 16px oklch(0.14 0.01 60 / 0.10), 0 2px 4px oklch(0.14 0.01 60 / 0.05)",
        lg:      "0 8px 32px oklch(0.14 0.01 60 / 0.12), 0 4px 8px oklch(0.14 0.01 60 / 0.06)",
        xl:      "0 20px 60px oklch(0.14 0.01 60 / 0.16), 0 8px 16px oklch(0.14 0.01 60 / 0.08)",
        amber:   "0 4px 20px oklch(0.68 0.17 54 / 0.28)",
        emerald: "0 4px 20px oklch(0.60 0.16 152 / 0.24)",
        violet:  "0 4px 20px oklch(0.58 0.16 282 / 0.24)",
      },
    },
  },
  plugins: [],
};
