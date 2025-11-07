/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
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
