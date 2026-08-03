import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base: 'var(--bg-base)',
        surface: 'var(--bg-surface)',
        elevated: 'var(--bg-elevated)',
        'glass': 'var(--bg-glass)',
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        tertiary: 'var(--text-tertiary)',
        brand: { purple: 'var(--brand-purple)', teal: 'var(--brand-teal)', blue: 'var(--brand-blue)' },
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        info: 'var(--info)',
      },
      borderColor: {
        subtle: 'var(--border-subtle)',
        strong: 'var(--border-strong)',
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
        pill: '999px',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
        serif: ['"Source Han Serif SC"', '"Noto Serif SC"', 'serif'],
      },
      transitionTimingFunction: {
        ease: 'var(--ease-out)',
        spring: 'var(--ease-spring)',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        flipIn: {
          '0%': { transform: 'perspective(600px) rotateY(90deg)', opacity: '0' },
          '100%': { transform: 'perspective(600px) rotateY(0)', opacity: '1' },
        },
        springPop: {
          '0%': { transform: 'scale(0.92)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        mirrorSlide: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.2s cubic-bezier(0.16,1,0.3,1) 1',
        flipIn: 'flipIn 300ms cubic-bezier(0.16,1,0.3,1)',
        springPop: 'springPop 300ms var(--ease-spring)',
        mirrorSlide: 'mirrorSlide 400ms var(--ease-out)',
      },
    },
  },
  plugins: [],
};

export default config;
