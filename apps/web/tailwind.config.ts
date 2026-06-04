import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#17202A",
        muted: "#64748B",
        line: "#D9E2EC",
        wash: "#F6F8FB",
        teal: {
          50: "#ECFDF9",
          100: "#CCFBF1",
          500: "#14B8A6",
          600: "#0D9488",
          700: "#0F766E"
        },
        amber: {
          50: "#FFFBEB",
          100: "#FEF3C7",
          500: "#F59E0B",
          700: "#B45309"
        }
      },
      boxShadow: {
        panel: "0 18px 50px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

