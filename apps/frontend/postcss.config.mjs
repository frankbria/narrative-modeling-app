// Tailwind v4 moved the PostCSS plugin into its own package; `tailwindcss` is no
// longer a PostCSS plugin itself. Autoprefixer is gone because v4 handles vendor
// prefixing internally via Lightning CSS.
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};

export default config;
