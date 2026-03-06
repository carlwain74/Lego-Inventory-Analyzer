/**
 * tests/test_ui.js — Jest suite for pure JS functions in index.html
 *
 * Setup (from project root):
 *   npm install --save-dev jest jest-environment-jsdom
 *   npm test
 *
 * The functions under test live inside a <script> block in index.html.
 * We extract and evaluate that block here so Jest can test them without
 * a real browser, using jsdom to satisfy any DOM references.
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ── Extract the <script> block from index.html ────────────────────────────────
const htmlPath = path.join(__dirname, '..', 'templates', 'index.html');
const html     = fs.readFileSync(htmlPath, 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/);
if (!scriptMatch) throw new Error('Could not locate <script> block in index.html');
const rawScript = scriptMatch[1];

// ── Minimal DOM stubs so module-level getElementById calls don't throw ────────
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

// ── Evaluate the script and expose the pure functions we want to test ─────────
// eslint-disable-next-line no-new-func
const ui = new Function(rawScript + `
  ;return { parseAllSets, formatPrice, formatSaleDate, calcSaleValue, esc, makeChip };
`)();

const { parseAllSets, formatPrice, formatSaleDate, calcSaleValue, esc, makeChip } = ui;


// ═══════════════════════════════════════════════════════════════════════════════
// Test fixtures — mirror the real log format from the app
// ═══════════════════════════════════════════════════════════════════════════════

const ONE_SET = `Item: 41591-1
  Name: Black Widow
  Category: BrickHeadz
  Current Sales:
    Average: 23 USD
    Max: 85 USD
    Min: 13 USD
    Quantity avail: 31
  Previous Sales:
    Average: 13 USD
    Max: 15 USD
    Min: 9 USD
    Quantity avail: 8
    Last Sale Date: 2023-12-11T18:44:02.100Z
  Year Released: 2017
  Image: //img.bricklink.com/SL/41591-1.jpg
  Thumbnail: //img.bricklink.com/S/41591-1.jpg
`;

const TWO_SETS = ONE_SET + `
Item: 75192-1
  Name: Millennium Falcon
  Category: Star Wars
  Current Sales:
    Average: 450 USD
    Max: 800 USD
    Min: 350 USD
    Quantity avail: 5
  Previous Sales:
    Average: 400 USD
    Max: 750 USD
    Min: 300 USD
    Quantity avail: 12
    Last Sale Date: 2024-06-15T10:00:00.000Z
  Year Released: 2017
  Image: //img.bricklink.com/SL/75192-1.jpg
  Thumbnail: //img.bricklink.com/S/75192-1.jpg
`;

const NO_SALES = `Item: 99999-1
  Name: Test Set
  Category: Test
  Year Released: 2020
`;


// ═══════════════════════════════════════════════════════════════════════════════
// esc
// ═══════════════════════════════════════════════════════════════════════════════

describe('esc', () => {
  test('escapes &', ()  => expect(esc('a & b')).toBe('a &amp; b'));
  test('escapes <',  ()  => expect(esc('<b>')).toContain('&lt;'));
  test('escapes >',  ()  => expect(esc('a > b')).toContain('&gt;'));
  test('null  → —', ()  => expect(esc(null)).toBe('—'));
  test('undefined → —', () => expect(esc(undefined)).toBe('—'));
  test('safe string unchanged', () => expect(esc('Hello')).toBe('Hello'));
  test('number coerced to string', () => expect(esc(42)).toBe('42'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// calcSaleValue
// ═══════════════════════════════════════════════════════════════════════════════

describe('calcSaleValue', () => {
  test('(avg + max) / 2 rounded', () =>
    expect(calcSaleValue('100 USD', '200 USD')).toBe('150 USD'));

  test('rounds 0.5 up', () =>
    expect(calcSaleValue('100 USD', '201 USD')).toBe('151 USD'));

  test('preserves currency code', () =>
    expect(calcSaleValue('50 GBP', '150 GBP')).toContain('GBP'));

  test('works without currency', () =>
    expect(calcSaleValue('100', '200')).toMatch(/150/));

  test('— when avg missing',       () => expect(calcSaleValue('',    '200 USD')).toBe('—'));
  test('— when max missing',       () => expect(calcSaleValue('100 USD', '')).toBe('—'));
  test('— when both missing',      () => expect(calcSaleValue('', '')).toBe('—'));
  test('— when undefined',         () => expect(calcSaleValue(undefined, undefined)).toBe('—'));
  test('— when non-numeric',       () => expect(calcSaleValue('abc USD', '200 USD')).toBe('—'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// formatPrice
// ═══════════════════════════════════════════════════════════════════════════════

describe('formatPrice', () => {
  test('formats value with currency', () => {
    const r = formatPrice('1410 USD');
    expect(r).toContain('1,410');
    expect(r).toContain('USD');
  });

  test('large numbers get commas',    () => expect(formatPrice('10000 USD')).toContain('10,000'));
  test('— for empty string',          () => expect(formatPrice('')).toBe('—'));
  test('— for undefined',             () => expect(formatPrice(undefined)).toBe('—'));
  test('raw fallback for one token',  () => expect(typeof formatPrice('unknown')).toBe('string'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// formatSaleDate
// ═══════════════════════════════════════════════════════════════════════════════

describe('formatSaleDate', () => {
  test('— for empty string',     () => expect(formatSaleDate('')).toBe('—'));
  test('— for null',             () => expect(formatSaleDate(null)).toBe('—'));
  test('— for undefined',        () => expect(formatSaleDate(undefined)).toBe('—'));
  test('— for non-date string',  () => expect(formatSaleDate('not-a-date')).toBe('—'));

  test('2023-12-11 → December 11 2023', () => {
    const r = formatSaleDate('2023-12-11T18:44:02.100Z');
    expect(r).toContain('December');
    expect(r).toContain('11');
    expect(r).toContain('2023');
  });

  test('2026-02-22 → February 22 2026', () => {
    const r = formatSaleDate('2026-02-22T02:13:03.260Z');
    expect(r).toContain('February');
    expect(r).toContain('22');
    expect(r).toContain('2026');
  });

  test('no timezone shift — late UTC time stays same day', () => {
    // 2023-05-27T23:59:59Z must not become May 28
    const r = formatSaleDate('2023-05-27T23:59:59.000Z');
    expect(r).toContain('May');
    expect(r).toContain('27');
  });

  test('no timezone shift — early UTC time stays same day', () => {
    // 2025-09-05T00:00:01Z must not become September 4
    const r = formatSaleDate('2025-09-05T00:00:01.000Z');
    expect(r).toContain('September');
    expect(r).toContain('5');
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// parseAllSets — single set
// ═══════════════════════════════════════════════════════════════════════════════

describe('parseAllSets — single set', () => {
  let s;
  beforeEach(() => { s = parseAllSets(ONE_SET)[0]; });

  test('returns exactly one set',          () => expect(parseAllSets(ONE_SET)).toHaveLength(1));
  test('number',                           () => expect(s.number).toBe('41591-1'));
  test('name',                             () => expect(s.name).toBe('Black Widow'));
  test('category',                         () => expect(s.category).toBe('BrickHeadz'));
  test('year',                             () => expect(s.year).toBe('2017'));

  // Images must be prefixed with http:
  test('thumbnail prefixed with http:',    () => expect(s.thumbnail).toBe('http://img.bricklink.com/S/41591-1.jpg'));
  test('image prefixed with http:',        () => expect(s.image).toBe('http://img.bricklink.com/SL/41591-1.jpg'));

  // Current Sales
  test('cur_avg',                          () => expect(s.cur_avg).toBe('23 USD'));
  test('cur_max',                          () => expect(s.cur_max).toBe('85 USD'));
  test('cur_min',                          () => expect(s.cur_min).toBe('13 USD'));
  test('cur_qty',                          () => expect(s.cur_qty).toBe('31'));

  // Previous Sales
  test('prev_avg',                         () => expect(s.prev_avg).toBe('13 USD'));
  test('prev_max',                         () => expect(s.prev_max).toBe('15 USD'));
  test('prev_min',                         () => expect(s.prev_min).toBe('9 USD'));
  test('prev_qty',                         () => expect(s.prev_qty).toBe('8'));

  // Last sale date formatted
  test('prev_date contains December',      () => expect(s.prev_date).toContain('December'));
  test('prev_date contains 11',            () => expect(s.prev_date).toContain('11'));
  test('prev_date contains 2023',          () => expect(s.prev_date).toContain('2023'));

  // Sale value: (23 + 85) / 2 = 54
  test('saleValue = 54 USD',              () => expect(s.saleValue).toBe('54 USD'));

  // Top-level fields after Previous Sales block must not be swallowed
  test('year not captured into prev section', () => expect(s.year).toBe('2017'));
  test('image not captured into prev section', () => expect(s.image).toContain('http:'));
  test('thumbnail not captured into prev section', () => expect(s.thumbnail).toContain('http:'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// parseAllSets — multiple sets
// ═══════════════════════════════════════════════════════════════════════════════

describe('parseAllSets — multiple sets', () => {
  let sets;
  beforeEach(() => { sets = parseAllSets(TWO_SETS); });

  test('returns two sets',                  () => expect(sets).toHaveLength(2));
  test('first set name',                    () => expect(sets[0].name).toBe('Black Widow'));
  test('second set name',                   () => expect(sets[1].name).toBe('Millennium Falcon'));
  test('sets have independent data',        () => expect(sets[0].cur_avg).not.toBe(sets[1].cur_avg));

  // (450 + 800) / 2 = 625
  test('second set sale value = 625 USD',  () => expect(sets[1].saleValue).toBe('625 USD'));

  test('second set last sale date contains June', () =>
    expect(sets[1].prev_date).toContain('June'));
});


// ═══════════════════════════════════════════════════════════════════════════════
// parseAllSets — edge cases
// ═══════════════════════════════════════════════════════════════════════════════

describe('parseAllSets — edge cases', () => {
  test('empty string → empty array', () =>
    expect(parseAllSets('')).toHaveLength(0));

  test('no Item: lines → empty array', () =>
    expect(parseAllSets('Setting up session\nProcessing...\n')).toHaveLength(0));

  test('missing thumbnail → empty string', () => {
    const s = parseAllSets(NO_SALES)[0];
    expect(s.thumbnail).toBe('');
  });

  test('missing image → empty string', () => {
    const s = parseAllSets(NO_SALES)[0];
    expect(s.image).toBe('');
  });

  test('missing current sales → — values', () => {
    const s = parseAllSets(NO_SALES)[0];
    expect(s.cur_avg).toBe('—');
    expect(s.cur_max).toBe('—');
    expect(s.cur_qty).toBe('—');
  });

  test('missing previous sales → — values', () => {
    const s = parseAllSets(NO_SALES)[0];
    expect(s.prev_avg).toBe('—');
    expect(s.prev_date).toBe('—');
  });

  test('missing last sale date → —', () => {
    const log = `Item: 99999-1
  Name: Test Set
  Category: Test
  Previous Sales:
    Average: 10 USD
    Max: 20 USD
    Min: 5 USD
    Quantity avail: 3
`;
    expect(parseAllSets(log)[0].prev_date).toBe('—');
  });

  test('sale value — when current sales missing', () => {
    const s = parseAllSets(NO_SALES)[0];
    expect(s.saleValue).toBe('—');
  });
});