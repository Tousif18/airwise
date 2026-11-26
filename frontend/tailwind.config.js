/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src//**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"],
      },
      colors: {
        mist: {
          50: "#F4F7F5",
          100: "#EBF1ED",
          200: "#DCE6DF",
        },
        pine: {
          50: "#ECFDF7",
          100: "#D1FAE8",
          600: "#0D9488",
          700: "#0F766E",
          800: "#115E59",
          900: "#134E4A",
        },
      },
    },
  },
  plugins: [],
};
