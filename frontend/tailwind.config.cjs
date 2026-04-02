/** @type {import("tailwindcss").Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0B0F14",
          gray: "#151A23",
        },
        intent: "#36D399",
        divergence: "#F87171",
        accent: "#6366F1",
      },
      boxShadow: {
        "panel-md": "0 30px 80px rgba(0, 0, 0, 0.55)",
      },
    },
  },
  plugins: [],
};
