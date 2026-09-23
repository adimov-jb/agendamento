/** @type {import('tailwindcss').Config} */
module.exports = {
  // *.py inclui classes aplicadas em formulários (core/forms.py)
  content: ["./templates/**/*.html", "./*/templates/**/*.html", "./*/*.py"],
  theme: {
    extend: {},
  },
  plugins: [require("@tailwindcss/forms")],
};
