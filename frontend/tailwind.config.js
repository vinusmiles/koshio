/** Colours come from CSS variables in src/index.css so light and dark themes share one set of names. */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        paper: v("paper"), surface: v("surface"), ink: v("ink"), muted: v("muted"),
        line: v("line"), brass: v("brass"), spend: v("spend"), earn: v("earn"),
      },
      fontFamily: { sans: ['"Manrope"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      borderRadius: { card: "14px" },
    },
  },
  plugins: [],
};
