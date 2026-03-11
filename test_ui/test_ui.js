/**
 * tests/test_ui.js — Jest suite for pure JS functions in index.html
 *
 * Setup (from test_ui/):
 *   npm install
 *   npm test
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ── Extract <script> block from index.html ────────────────────────────────────
const htmlPath = path.join(__dirname, '..', 'templates', 'index.html');
const html     = fs.readFileSync(htmlPath, 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/);
if (!scriptMatch) throw new Error('Could not locate <script> block in index.html');
const rawScript = scriptMatch[1];

// ── Minimal DOM stubs ─────────────────────────────────────────────────────────
function stubEl(id = '') {
  return {
    id, style: {}, dataset: {},
    classList:   { add: jest.fn(), remove: jest.fn(), toggle: jest.fn(), contains: jest.fn(() => false) },
    addEventListener: jest.fn(),
    querySelectorAll: jest.fn(() => []),
    appendChild:  jest.fn(),
    innerHTML: '', textContent: '', value: '',
    type: 'text', disabled: false, placeholder: '', src: '',
    focus: jest.fn(),
  };
}
const elCache = {};
document.getElementById      = (id) => (elCache[id] ??= stubEl(id));
document.addEventListener    = jest.fn();
document.querySelectorAll    = jest.fn(() => []);
document.createElement       = jest.fn((tag) => stubEl(tag));
window.innerWidth            = 1280;
window.innerHeight           = 800;
global.fetch                 = jest.fn();

// ── Evaluate and expose functions ─────────────────────────────────────────────
// eslint-disable-next-line no-new-func
const ui = new Function(rawScript + `
  ;return { normaliseSets, formatPrice, formatSaleDate, calcSaleValue, esc };
`)();

const { normaliseSets, formatPrice, formatSaleDate, calcSaleValue, esc } = ui;


// ═══════════════════════════════════════════════════════════════════════════════
// Fixtures
// ═══════════════════════════════════════════════════════════════════════════════

const SINGLE_MAP = {
  '10188-1': {
    name: 'Death Star - UCS',
    category: 'Star Wars',
    current: { avg: 1104, max: 1498, min: 935,  quantity: 10, currency: 'USD' },
    past:    { avg: 929,  max: 1298, min: 520,  quantity: 14, currency: 'USD',
               last_sale_date: '2026-02-08T21:05:26.307Z' },
    year: 2008,
    image:     '//img.bricklink.com/SL/10188-1.jpg',
    thumbnail: '//img.bricklink.com/S/10188-1.gif',
  }
};

const TWO_MAP = {
  ...SINGLE_MAP,
  '75192-1': {
    name: 'Millennium Falcon',
    category: 'Star Wars',
    current: { avg: 450, max: 800, min: 350, quantity: 5,  currency: 'USD' },
    past:    { avg: 400, max: 750, min: 300, quantity: 12, currency: 'USD',
               last_sale_date: '2024-06-15T10:00:00.000Z' },
    year: 2017,
    image:     '//img.bricklink.com/SL/75192-1.jpg',
    thumbnail: '//img.bricklink.com/S/75192-1.jpg',
  }
};

const NO_PAST_MAP = {
  '41591-1': {
    name: 'Black Widow',
    category: 'BrickHeadz',
    current: { avg: 23, max: 85, min: 13, quantity: 31, currency: 'USD' },
    past: {},
    year: 2017,
    image:     '//img.bricklink.com/SL/41591-1.jpg',
    thumbnail: '//img.bricklink.com/S/41591-1.gif',
  }
};


// ═══════════════════════════════════════════════════════════════════════════════
// esc
// ═══════════════════════════════════════════════════════════════════════════════

describe('esc', () => {
  test('escapes &',             () => expect(esc('a & b')).toBe('a &amp; b'));
  test('escapes <',             () => expect(esc('<b>')).toContain('&lt;'));
  test('escapes >',             () => expect(esc('a > b')).toContain('&gt;'));
  test('null → —',              () => expect(esc(null)).toBe('—'));
  test('undefined → —',         () => expect(esc(undefined)).toBe('—'));
  test('safe string unchanged', () => expect(esc('Hello')).toBe('Hello'));
  test('number coerced',        () => expect(esc(42)).toBe('42'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// calcSaleValue
// ═══════════════════════════════════════════════════════════════════════════════

describe('calcSaleValue', () => {
  test('(avg + max) / 2',          () => expect(calcSaleValue('100 USD', '200 USD')).toBe('150 USD'));
  test('rounds 0.5 up',            () => expect(calcSaleValue('100 USD', '201 USD')).toBe('151 USD'));
  test('preserves currency',       () => expect(calcSaleValue('50 GBP', '150 GBP')).toContain('GBP'));
  test('works without currency',   () => expect(calcSaleValue('100', '200')).toMatch(/150/));
  test('— when avg missing',       () => expect(calcSaleValue('', '200 USD')).toBe('—'));
  test('— when max missing',       () => expect(calcSaleValue('100 USD', '')).toBe('—'));
  test('— when both missing',      () => expect(calcSaleValue('', '')).toBe('—'));
  test('— when undefined',         () => expect(calcSaleValue(undefined, undefined)).toBe('—'));
  test('— when non-numeric',       () => expect(calcSaleValue('abc USD', '200 USD')).toBe('—'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// formatPrice
// ═══════════════════════════════════════════════════════════════════════════════

describe('formatPrice', () => {
  test('formats with commas and currency', () => {
    const r = formatPrice('1410 USD');
    expect(r).toContain('1,410');
    expect(r).toContain('USD');
  });
  test('large number gets commas',  () => expect(formatPrice('10000 USD')).toContain('10,000'));
  test('— for empty string',        () => expect(formatPrice('')).toBe('—'));
  test('— for undefined',           () => expect(formatPrice(undefined)).toBe('—'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// formatSaleDate
// ═══════════════════════════════════════════════════════════════════════════════

describe('formatSaleDate', () => {
  test('— for empty string',         () => expect(formatSaleDate('')).toBe('—'));
  test('— for null',                 () => expect(formatSaleDate(null)).toBe('—'));
  test('— for undefined',            () => expect(formatSaleDate(undefined)).toBe('—'));
  test('— for non-date string',      () => expect(formatSaleDate('not-a-date')).toBe('—'));

  test('2026-02-08 → February 8 2026', () => {
    const r = formatSaleDate('2026-02-08T21:05:26.307Z');
    expect(r).toContain('February');
    expect(r).toContain('8');
    expect(r).toContain('2026');
  });

  test('2024-06-15 → June 15 2024', () => {
    const r = formatSaleDate('2024-06-15T10:00:00.000Z');
    expect(r).toContain('June');
    expect(r).toContain('15');
    expect(r).toContain('2024');
  });

  test('no timezone shift — late UTC stays same day', () => {
    const r = formatSaleDate('2023-05-27T23:59:59.000Z');
    expect(r).toContain('May');
    expect(r).toContain('27');
  });

  test('no timezone shift — early UTC stays same day', () => {
    const r = formatSaleDate('2025-09-05T00:00:01.000Z');
    expect(r).toContain('September');
    expect(r).toContain('5');
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// normaliseSets — single set
// ═══════════════════════════════════════════════════════════════════════════════

describe('normaliseSets — single set', () => {
  let s;
  beforeEach(() => { s = normaliseSets(SINGLE_MAP)[0]; });

  test('returns one item',                    () => expect(normaliseSets(SINGLE_MAP)).toHaveLength(1));
  test('number = map key',                    () => expect(s.number).toBe('10188-1'));
  test('name',                                () => expect(s.name).toBe('Death Star - UCS'));
  test('category',                            () => expect(s.category).toBe('Star Wars'));
  test('year coerced to string',              () => expect(s.year).toBe('2008'));

  // Images prefixed with http:
  test('thumbnail prefixed with http:',       () => expect(s.thumbnail).toBe('http://img.bricklink.com/S/10188-1.gif'));
  test('image prefixed with http:',           () => expect(s.image).toBe('http://img.bricklink.com/SL/10188-1.jpg'));

  // Current sales formatted as "value CURRENCY"
  test('cur_avg = 1104 USD',                  () => expect(s.cur_avg).toBe('1104 USD'));
  test('cur_max = 1498 USD',                  () => expect(s.cur_max).toBe('1498 USD'));
  test('cur_min = 935 USD',                   () => expect(s.cur_min).toBe('935 USD'));
  test('cur_qty = 10',                        () => expect(s.cur_qty).toBe('10'));

  // Past sales
  test('prev_avg = 929 USD',                  () => expect(s.prev_avg).toBe('929 USD'));
  test('prev_max = 1298 USD',                 () => expect(s.prev_max).toBe('1298 USD'));
  test('prev_min = 520 USD',                  () => expect(s.prev_min).toBe('520 USD'));
  test('prev_qty = 14',                       () => expect(s.prev_qty).toBe('14'));

  // Last sale date formatted
  test('prev_date contains February',         () => expect(s.prev_date).toContain('February'));
  test('prev_date contains 8',                () => expect(s.prev_date).toContain('8'));
  test('prev_date contains 2026',             () => expect(s.prev_date).toContain('2026'));

  // Sale value: (1104 + 1498) / 2 = 1301
  test('saleValue = 1301 USD',               () => expect(s.saleValue).toBe('1301 USD'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// normaliseSets — multiple sets
// ═══════════════════════════════════════════════════════════════════════════════

describe('normaliseSets — multiple sets', () => {
  let sets;
  beforeEach(() => { sets = normaliseSets(TWO_MAP); });

  test('returns two items',                        () => expect(sets).toHaveLength(2));
  test('sets have independent data',               () => expect(sets[0].name).not.toBe(sets[1].name));

  test('second set sale value = 625 USD', () => {
    const falcon = sets.find(s => s.number === '75192-1');
    // (450 + 800) / 2 = 625
    expect(falcon.saleValue).toBe('625 USD');
  });

  test('second set last sale date contains June', () => {
    const falcon = sets.find(s => s.number === '75192-1');
    expect(falcon.prev_date).toContain('June');
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// normaliseSets — edge cases
// ═══════════════════════════════════════════════════════════════════════════════

describe('normaliseSets — edge cases', () => {
  test('empty map → empty array',           () => expect(normaliseSets({})).toHaveLength(0));

  test('missing thumbnail → empty string', () => {
    const sets = normaliseSets({ '1-1': { name: 'Test', category: 'X', current: {}, past: {}, year: 2020 } });
    expect(sets[0].thumbnail).toBe('');
    expect(sets[0].image).toBe('');
  });

  test('missing current values → —', () => {
    const s = normaliseSets({ '1-1': { name: 'Test', category: 'X', current: {}, past: {}, year: 2020 } })[0];
    expect(s.cur_avg).toBe('—');
    expect(s.cur_max).toBe('—');
    expect(s.cur_min).toBe('—');
    expect(s.cur_qty).toBe('—');
  });

  test('missing past values → —', () => {
    const s = normaliseSets({ '1-1': { name: 'Test', category: 'X', current: {}, past: {}, year: 2020 } })[0];
    expect(s.prev_avg).toBe('—');
    expect(s.prev_date).toBe('—');
  });

  test('missing last_sale_date → —',  () => {
    const s = normaliseSets(NO_PAST_MAP)[0];
    expect(s.prev_date).toBe('—');
  });

  test('sale value — when current missing', () => {
    const s = normaliseSets({ '1-1': { name: 'T', category: 'X', current: {}, past: {}, year: 2020 } })[0];
    expect(s.saleValue).toBe('—');
  });

  test('currency from past used when current has none', () => {
    const s = normaliseSets({
      '1-1': {
        name: 'T', category: 'X', year: 2020,
        current: { avg: 100, max: 200, min: 50, quantity: 5 },
        past:    { avg: 80,  max: 150, min: 40, quantity: 3, currency: 'EUR' },
      }
    })[0];
    expect(s.cur_avg).toContain('EUR');
  });

  test('year null → —', () => {
    const s = normaliseSets({ '1-1': { name: 'T', category: 'X', current: {}, past: {}, year: null } })[0];
    expect(s.year).toBe('—');
  });
});