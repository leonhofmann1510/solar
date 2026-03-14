/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,js}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
      },
      colors: {
        sf: {
          green: {
            50:  '#f0fdf4',
            100: '#dcfce7',
            500: '#22c55e',
            600: '#16a34a',
            700: '#15803d',
          },
          amber: {
            400: '#fbbf24',
            500: '#f59e0b',
            600: '#d97706',
          },
          red: {
            500: '#ef4444',
          },
          bg:      '#f8fafc',
          surface: '#ffffff',
          border:  '#e2e8f0',
          text: {
            1: '#0f172a',
            2: '#475569',
            3: '#94a3b8',
          },
        },
      },
      borderRadius: {
        sf:      '12px',
        'sf-sm': '8px',
      },
      boxShadow: {
        sf:      '0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04)',
        'sf-md': '0 4px 12px rgba(0,0,0,.08)',
      },
    },
  },
  plugins: [],
}

