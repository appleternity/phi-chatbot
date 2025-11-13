/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    "bg-blue-500",
    "bg-green-500",
    "bg-red-500",
    "bg-yellow-500",
    "bg-purple-500",
    "bg-indigo-500",
    "bg-pink-500",
    "bg-pink-400",
  ],
  theme: {
    extend: {
      colors: {
        // Instagram gradient colors
        'instagram-purple': '#667eea',
        'instagram-pink': '#764ba2',
      },
      backgroundImage: {
        // Instagram gradient for user message bubbles
        'instagram-gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      },
    },
  },
  plugins: [],
}
