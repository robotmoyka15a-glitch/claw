/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        room: {
          bg: '#0a0d14',
          floor: '#1b2030',
          wall: '#242b3d',
          accent: '#f5b301',
          panel: '#141822',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
