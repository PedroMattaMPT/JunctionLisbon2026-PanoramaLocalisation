module.exports = {
  presets: [require('../design_system/code/aqui.tailwind.preset.js')],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  corePlugins: { preflight: false },
};
