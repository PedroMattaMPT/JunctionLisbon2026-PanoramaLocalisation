import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { checkTokens, generateTokens } from '../scripts/build-tokens.mjs';
it('the generated stylesheet resolves every design-system and Tailwind variable', async () => { const css = readFileSync(new URL('../src/generated/tokens.css', import.meta.url), 'utf8'); expect(css).toBe(generateTokens()); expect(await checkTokens(css)).toBe(139); });
it('generates aliases, every theme, local fonts and inference typography', () => { const css = generateTokens(); expect(css).toContain('[data-theme="stage"]'); expect(css).toContain('--neutral: var(--ink-3)'); expect(css).toContain('font-style: italic'); expect(css).toContain("../../../design_system/fonts/"); expect(css.match(/@font-face/g)).toHaveLength(5); });
