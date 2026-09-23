/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--ink)',
        surface: 'var(--surface)',
        panel: 'var(--panel)',
        'panel-raised': 'var(--panel-raised)',
        line: 'var(--line)',
        accent: 'var(--accent)',
        muted: 'var(--muted)',
        'status-valid': 'var(--status-valid)',
        'status-suspect': 'var(--status-suspect)',
        'status-anomalous': 'var(--status-anomalous)',
        'status-offline': 'var(--status-offline)',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
        md: '4px',
        lg: '4px',
      },
    },
  },
  plugins: [],
};
