/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        kfl: {
          blue: "#1b7abf",
          "blue-deep": "#0b2942",
          "blue-ink": "#123b5d",
          dark: "#0b2942",
          teal: "#1b7abf",
          "teal-dark": "#123b5d",
          canvas: "#f4f7fa",
          "surface-subtle": "#f8fafc",
          border: "#d9e2ec",
          text: "#102a43",
          secondary: "#52606d",
          muted: "#52606d",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 42, 67, 0.04), 0 8px 24px rgba(16, 42, 67, 0.06)",
        popover: "0 12px 32px rgba(16, 42, 67, 0.14)",
      },
      borderRadius: {
        kfl: "10px",
      },
    },
  },
  plugins: [],
};