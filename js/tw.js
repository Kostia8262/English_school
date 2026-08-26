/* Конфіг Tailwind для посадкових сторінок — один файл на всі.
   В index.html конфіг лежить інлайном і лишається там: сторінка вантажиться
   першою, і зайвий блокуючий запит на її критичному шляху дорожчий за дублювання.
   Решта сторінок беруть звідси, інакше десять копій одного словника токенів
   розійшлися б після першої ж правки дизайн-системи.

   Порядок підключення важливий: cdn.tailwindcss.com спершу, цей файл — одразу
   після нього, до першого використання класів. */
tailwind.config = {
  theme: {
    extend: {
      screens: {
        nav: '1100px', // повне десктопне меню вміщається лише звідси
      },
      colors: {
        fox: {
          50:  '#FFF5EF',
          100: '#FFE8D6',
          200: '#FFCAAA',
          300: '#FFA07A',
          400: '#FF7A45',
          500: '#FF6B35',
          600: '#E54E1A',
          700: '#BF3C0F',
        },
        violet: {
          50:  '#F4F0FF',
          100: '#EAE2FF',
          500: '#7C3AED',
          600: '#6D28D9',
        },
        gray: {
          950: '#030712',
        },
        british: '#C8102E',
        cream: '#FFFBF7',
        gold: {
          DEFAULT: '#D4AF37',
          light:   '#F5E88A',
          dark:    '#B8960C',
        },
      },
      fontFamily: {
        sans: ['Nunito', 'sans-serif'],
      },
      fontWeight: {
        medium:   '500',
        semibold: '600',
        bold:     '700',
        black:    '900',
      },
      fontSize: {
        '2xs':  ['0.6875rem', { lineHeight: '1rem' }],     // 11px
        xs:     ['0.75rem',   { lineHeight: '1rem' }],     // 12px
        sm:     ['0.875rem',  { lineHeight: '1.25rem' }],  // 14px
        base:   ['1rem',      { lineHeight: '1.5rem' }],   // 16px
        lg:     ['1.125rem',  { lineHeight: '1.75rem' }],  // 18px
        xl:     ['1.25rem',   { lineHeight: '1.75rem' }],  // 20px
        '2xl':  ['1.5rem',    { lineHeight: '2rem' }],     // 24px
        '3xl':  ['1.875rem',  { lineHeight: '2.25rem' }],  // 30px
        '4xl':  ['2.25rem',   { lineHeight: '2.5rem' }],   // 36px
        '5xl':  ['3rem',      { lineHeight: '1' }],        // 48px
      },
      borderRadius: {
        xl:   '0.75rem',
        '2xl':'1rem',
        '3xl':'1.5rem',
        '4xl':'2rem',
      },
      boxShadow: {
        'fox-sm': '0 4px 14px rgba(255,107,53,0.12)',
        'fox':    '0 8px 24px rgba(255,107,53,0.18)',
        'fox-lg': '0 20px 40px rgba(255,107,53,0.22)',
        'fox-xl': '0 28px 56px rgba(255,107,53,0.30)',
      },
    },
  },
};
