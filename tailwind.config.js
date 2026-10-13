/** @type {import('tailwindcss').Config} */

// Cor da marca: vem de variáveis CSS, que cada tema (barbearia, clínica...) define em static/src/input.css
const marca = Object.fromEntries(
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((tom) => [tom, `rgb(var(--marca-${tom}) / <alpha-value>)`])
);
// Cinzas (classes slate-*) também vêm de variáveis: o site escuro da barbearia os inverte
const cinza = Object.fromEntries(
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map((tom) => [tom, `rgb(var(--cinza-${tom}) / <alpha-value>)`])
);

module.exports = {
  // *.py inclui classes aplicadas em formulários (core/forms.py)
  content: ["./templates/**/*.html", "./*/templates/**/*.html", "./*/*.py"],
  // O base.html monta a classe do tema ("tema-{{ tema }}"), que o Tailwind não acha sozinho
  safelist: ["tema-barbearia", "tema-clinica"],
  theme: {
    extend: {
      colors: {
        marca,
        slate: cinza,
        fundo: "rgb(var(--fundo) / <alpha-value>)",
        destaque: "rgb(var(--destaque) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--fonte-texto)", "ui-sans-serif", "system-ui", "sans-serif"],
        titulo: ["var(--fonte-titulo)", "ui-sans-serif", "system-ui", "sans-serif"],
        script: ["var(--fonte-script)", "cursive"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
