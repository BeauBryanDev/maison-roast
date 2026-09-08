/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './products/templates/**/*.html',
    './orders/templates/**/*.html',
    './users/templates/**/*.html',
    // Any class name constructed in JS must be scanned too, or it gets purged.
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      // Maison Roast vintage palette. Five roles -- see the mockups.
      colors: {
        espresso: {
          DEFAULT: '#1a1108',   // page ground, nav, footer
          800: '#241708',
          700: '#2e1d0d',
        },
        roast: {
          DEFAULT: '#3b2515',   // dark cards and panels
          600: '#4a3020',
          400: '#6b4a32',
        },
        crema: {
          DEFAULT: '#f2e4cc',   // parchment panels, body text on dark
          200: '#f8f1e3',
          400: '#e3cfae',
        },
        terracotta: {
          DEFAULT: '#c0622c',   // CTAs, active nav, prices
          600: '#a8531f',
          400: '#d4834f',
        },
        gold: {
          DEFAULT: '#c8a26a',   // hairlines, icons, ornaments
          400: '#dcbd8f',
          600: '#a8834c',
        },
        // Evening-only. The bar page after 18:00 -- used nowhere else, so the
        // daytime site stays the five roles above.
        plum: {
          DEFAULT: '#33163d',   // the bar's welcome panel
          800: '#24102b',
          400: '#5a2c66',
        },
      },
      fontFamily: {
        display: ['"Playfair Display"', 'Georgia', 'Cambria', 'serif'],
        script: ['"Great Vibes"', '"Brush Script MT"', 'cursive'],
        body: ['Lato', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      letterSpacing: {
        widest2: '0.2em',
      },
    },
  },
  plugins: [],
};
