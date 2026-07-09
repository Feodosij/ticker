import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Terminal surfaces — no pure black
        bg: {
          base: '#0d1117',
          panel: '#131926',
          raised: '#1a2130',
          deep: '#0a0e16',
        },
        border: {
          DEFAULT: '#232b3a',
          strong: '#30394d',
        },
        // Brand
        accent: '#ecad0a', // yellow
        primary: '#209dd7', // blue
        secondary: '#753991', // purple (buy/submit)
        // Market semantics
        up: '#26a17b',
        down: '#e04b5a',
        muted: '#7d8697',
        faint: '#5a6272',
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        flashUp: {
          '0%': { backgroundColor: 'rgba(38,161,123,0.45)' },
          '100%': { backgroundColor: 'transparent' },
        },
        flashDown: {
          '0%': { backgroundColor: 'rgba(224,75,90,0.45)' },
          '100%': { backgroundColor: 'transparent' },
        },
        pulseDot: {
          '0%,100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
      },
      animation: {
        'flash-up': 'flashUp 0.6s ease-out',
        'flash-down': 'flashDown 0.6s ease-out',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
