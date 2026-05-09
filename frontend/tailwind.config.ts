import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          500: "#1F497D",
          600: "#1B406B",
          700: "#163558",
        },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
