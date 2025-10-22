/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f5f7ff',
          100: '#ebefff',
          200: '#d6deff',
          300: '#b3c0ff',
          400: '#8c9eff',
          500: '#667eea',
          600: '#5568d3',
          700: '#4553b8',
          800: '#3a4694',
          900: '#323c78',
        },
        secondary: {
          500: '#764ba2',
          600: '#653d8c',
          700: '#553076',
        },
      },
    },
  },
  plugins: [],
}
