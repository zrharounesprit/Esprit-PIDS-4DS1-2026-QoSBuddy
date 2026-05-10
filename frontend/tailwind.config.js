/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        canvas:         '#08090D',
        'canvas-light': '#0C0E14',
        surface:        '#12141C',
        'surface-2':    '#181A24',
        'surface-3':    '#1E2130',
        border:         '#262938',
        'border-subtle':'#1C1F2E',
        'text-primary': '#EAEDF3',
        'text-secondary':'#B0B8C8',
        'text-muted':   '#6B7280',
        'text-faint':   '#3D4455',
        accent: {
          teal:    { DEFAULT: '#00E8C6', dim: '#00E8C612', border: '#00E8C625' },
          red:     { DEFAULT: '#FF5A5A', dim: '#FF5A5A12', border: '#FF5A5A25' },
          purple:  { DEFAULT: '#A78BFA', dim: '#A78BFA12', border: '#A78BFA25' },
          cyan:    { DEFAULT: '#38BDF8', dim: '#38BDF812', border: '#38BDF825' },
          magenta: { DEFAULT: '#E879F9', dim: '#E879F912', border: '#E879F925' },
          blue:    { DEFAULT: '#60A5FA', dim: '#60A5FA12', border: '#60A5FA25' },
          green:   { DEFAULT: '#34D399', dim: '#34D39912', border: '#34D39925' },
          orange:  { DEFAULT: '#FB923C', dim: '#FB923C12', border: '#FB923C25' },
          amber:   { DEFAULT: '#FBBF24', dim: '#FBBF2412', border: '#FBBF2425' },
        },
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        sm: '0.375rem',
        md: '0.625rem',
        lg: '0.875rem',
        xl: '1.125rem',
      },
      boxShadow: {
        card:     '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)',
        'card-hover': '0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)',
        glow:     '0 0 24px rgba(0, 232, 198, 0.15)',
        'glow-sm':'0 0 12px rgba(0, 232, 198, 0.1)',
      },
      keyframes: {
        'slide-in': {
          from: { opacity: 0, transform: 'translateX(16px)' },
          to:   { opacity: 1, transform: 'translateX(0)' },
        },
        'fade-up': {
          from: { opacity: 0, transform: 'translateY(12px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: 0 },
          to:   { opacity: 1 },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulse: {
          '0%, 100%': { opacity: 1 },
          '50%':      { opacity: 0.5 },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to:   { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'slide-in':   'slide-in 0.3s cubic-bezier(0.16,1,0.3,1)',
        'fade-up':    'fade-up 0.4s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':    'fade-in 0.3s ease-out',
        shimmer:      'shimmer 2s infinite linear',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'spin-slow':  'spin-slow 20s linear infinite',
      },
    },
  },
  plugins: [],
}
