/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        tata: {
          blue: "#005DA4",
          "blue-dark": "#004A85",
          "blue-light": "#006BB8",
          "blue-pale": "#E8F2FA",
          menu: "#8AD4F0",
          ink: "#1C2434",
          muted: "#5C6B82",
          bg: "#F7F9FC",
          border: "#D8E4EF",
        },
        steel: {
          50: "#f4f7fa",
          100: "#e4ebf2",
          200: "#c5d4e3",
          300: "#9bb3cc",
          400: "#6b8fb0",
          500: "#3d5a80",
          600: "#2f4663",
          700: "#1b2a41",
          800: "#121c2b",
          900: "#0d1321",
        },
        accent: {
          orange: "#f77f00",
          red: "#d62828",
          green: "#2a9d8f",
          amber: "#fcbf49",
        },
      },
      boxShadow: {
        panel: "0 2px 12px -2px rgba(0, 61, 106, 0.1)",
        card: "0 1px 4px rgba(0, 61, 106, 0.08)",
      },
      backgroundImage: {
        "tata-gradient": "linear-gradient(135deg, #0066B3 0%, #005DAA 50%, #003D71 100%)",
        "tata-gradient-v": "linear-gradient(180deg, #0066B3 0%, #005DAA 55%, #003D71 100%)",
        "grid-pattern":
          "linear-gradient(rgba(0,93,170,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,93,170,0.04) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "24px 24px",
      },
    },
  },
  plugins: [],
};
