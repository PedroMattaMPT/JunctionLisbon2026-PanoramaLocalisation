import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../../design_system/', import.meta.url);
const tokens = JSON.parse(await readFile(new URL('tokens.json', root), 'utf8'));
const first = tokens.color.themes[0].id;
const value = (v) => String(v).replace(/\{([^}]+)\}/g, 'var(--$1)');
const pick = (v, theme = first) => typeof v === 'object' ? v[theme] ?? v[first] : v;
export function generateTokens() {
  const css = ['/* Generated from design_system/tokens.json. Do not edit. */'];
  for (const theme of tokens.color.themes) {
    css.push(`${theme.id === first ? ':root, ' : ''}[data-theme="${theme.id}"] {`);
    for (const token of tokens.color.tokens) css.push(`  --${token.name}: ${value(pick(token.value, theme.id))};`);
    css.push('}');
  }
  css.push(':root {');
  for (const family of ['spacing', 'radius', 'shadow', 'border', 'zIndex', 'duration', 'easing', 'opacity', 'size']) {
    for (const token of tokens[family].tokens) css.push(`  --${token.name}: ${value(pick(token.value))};`);
  }
  for (const [name, family] of Object.entries(tokens.type.families)) css.push(`  --font-${name}: ${family};`);
  // Type dimensions can also be used by app adapters without introducing sizes.
  for (const group of tokens.type.groups) for (const style of group.styles) {
    for (const property of ['fontSize', 'lineHeight']) css.push(`  --${style.name}-${property === 'fontSize' ? 'size' : 'line'}: ${style[property]};`);
  }
  css.push('}');
  for (const font of tokens.type.fonts) css.push(`@font-face { font-family: ${JSON.stringify(font.family)}; src: url('../../../design_system/${font.file}') format('woff2'); font-weight: ${font.weight}; font-style: ${font.style}; font-display: swap; }`);
  for (const group of tokens.type.groups) for (const style of group.styles) {
    css.push(`.${style.name} { font-family: var(--font-${group.family}); font-size: ${style.fontSize}; line-height: ${style.lineHeight}; font-weight: ${style.fontWeight};${style.fontStyle ? ` font-style: ${style.fontStyle};` : ''}${style.letterSpacing ? ` letter-spacing: ${style.letterSpacing};` : ''}${style.opticalSize ? ` font-variation-settings: 'opsz' ${style.opticalSize};` : ''} }`);
  }
  return css.join('\n') + '\n';
}
export async function checkTokens(css = generateTokens()) {
  const sources = await Promise.all(['components/bundle.css', 'code/aqui.tailwind.preset.js'].map(f => readFile(new URL(f, root), 'utf8')));
  const definitions = new Set([...`${css}\n${sources[0]}`.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]));
  definitions.add('--w');
  const references = new Set([...sources.join('\n').matchAll(/var\((--[\w-]+)/g)].map(m => m[1]));
  const missing = [...references].filter(name => !definitions.has(name));
  if (missing.length) throw new Error(`Unresolved tokens: ${missing.join(', ')}`);
  return references.size;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const css = generateTokens();
  const count = await checkTokens(css);
  await mkdir(new URL('../src/generated/', import.meta.url), { recursive: true });
  await writeFile(new URL('../src/generated/tokens.css', import.meta.url), css);
  console.log(`Generated tokens.css; ${count} design-system variable references resolve.`);
}
