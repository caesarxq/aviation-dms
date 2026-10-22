/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        kfl: {
          dark: "#1a2332",
          teal: "#0d9488",
          "teal-dark": "#0f766e",
        },
      },
    },
  },
  plugins: [],
};
