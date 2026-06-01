/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        kia: { blue: "#0066cc", deep: "#003087", hover: "#0a5bb8" },
      },
      fontFamily: {
        sans: ['-apple-system','BlinkMacSystemFont','"SF Pro Text"','"Helvetica Neue"','Segoe UI','Roboto','system-ui','sans-serif'],
      },
    },
  },
  plugins: [],
}
