import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mission: {
          bg: "#05070d",
          panel: "#0b0f1a",
          border: "#1c2333",
          accent: "#5eead4",
          accent2: "#818cf8",
          danger: "#f87171",
          warn: "#fbbf24",
          ok: "#4ade80",
          muted: "#64748b",
        },
      },
      fontFamily: {
        display: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(94, 234, 212, 0.25)",
      },
    },
  },
  plugins: [],
} satisfies Config;
