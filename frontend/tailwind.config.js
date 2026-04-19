/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        canvas: '#0D1117',
        surface: '#161B22',
        'surface-2': '#1C2128',
        border: '#30363D',
        'border-subtle': '#21262D',
        'text-primary': '#E6EDF3',
        'text-muted': '#7D8590',
        'text-faint': '#484F58',
        accent: {
          teal:    { DEFAULT: '#00FFD5', dim: '#00FFD520', border: '#00FFD540' },
          red:     { DEFAULT: '#F04444', dim: '#F0444420', border: '#F0444440' },
          purple:  { DEFAULT: '#8B7CF8', dim: '#8B7CF820', border: '#8B7CF840' },
          cyan:    { DEFAULT: '#22D3EE', dim: '#22D3EE20', border: '#22D3EE40' },
          magenta: { DEFAULT: '#E040FB', dim: '#E040FB20', border: '#E040FB40' },
          blue:    { DEFAULT: '#3B82F6', dim: '#3B82F620', border: '#3B82F640' },
          green:   { DEFAULT: '#22C55E', dim: '#22C55E20', border: '#22C55E40' },
          orange:  { DEFAULT: '#F97316', dim: '#F9731620', border: '#F9731640' },
        },
      },
      boxShadow: {
        card: '0 0 0 1px #30363D',
        glow: '0 0 20px rgba(0, 255, 213, 0.15)',
      },
      keyframes: {
        'slide-in': {
          from: { opacity: 0, transform: 'translateX(20px)' },
          to:   { opacity: 1, transform: 'translateX(0)' },
        },
        'fade-in': {
          from: { opacity: 0, transform: 'translateY(6px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'progress': {
          from: { width: '0%' },
          to:   { width: '100%' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'slide-in':   'slide-in 0.25s ease-out',
        'fade-in':    'fade-in 0.2s ease-out',
        shimmer:      'shimmer 1.8s infinite linear',
      },
    },
  },
  plugins: [],
}
