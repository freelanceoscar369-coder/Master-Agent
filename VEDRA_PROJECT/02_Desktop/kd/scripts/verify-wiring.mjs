#!/usr/bin/env node
/**
 * Static wiring check.
 *
 * This is NOT a type checker. It exists because the environment this tree was
 * authored in had no npm registry, so `tsc` could never be run. It catches the
 * class of error that actually breaks a fresh `npm run dev`: an import that
 * points at a file that does not exist, or a named import that the target
 * module does not export.
 *
 * Run: node scripts/verify-wiring.mjs
 * Exit 0 = clean. Exit 1 = findings.
 *
 * Delete this file once `npm run typecheck` runs in CI — tsc subsumes it.
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'src');

const CODE = new Set(['.ts', '.tsx']);
const STYLE = new Set(['.css']);
const RESOLVE_ORDER = ['', '.ts', '.tsx', '/index.ts', '/index.tsx'];

/** @type {string[]} */
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else files.push(p);
  }
})(SRC);

const codeFiles = files.filter((f) => CODE.has(extname(f)));
const rel = (p) => p.slice(ROOT.length + 1);

/* ── collect exports per module ───────────────────────────────────────── */

/** @type {Map<string, Set<string>>} */
const exportsByFile = new Map();
/** @type {Map<string, string[]>} */
const starReexports = new Map();

const NAMED_DECL = /export\s+(?:async\s+)?(?:function|const|let|var|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/g;
const NAMED_LIST = /export\s+(?:type\s+)?\{([^}]*)\}(?:\s*from\s*['"]([^'"]+)['"])?/g;
const STAR_FROM = /export\s+\*\s+from\s*['"]([^'"]+)['"]/g;
const DEFAULT_EXPORT = /export\s+default\s/;

for (const f of codeFiles) {
  const src = readFileSync(f, 'utf8');
  const set = new Set();
  for (const m of src.matchAll(NAMED_DECL)) set.add(m[1]);
  for (const m of src.matchAll(NAMED_LIST)) {
    for (const part of m[1].split(',')) {
      const name = part.trim().split(/\s+as\s+/).pop()?.trim();
      if (name) set.add(name.replace(/^type\s+/, ''));
    }
  }
  if (DEFAULT_EXPORT.test(src)) set.add('default');
  exportsByFile.set(f, set);
  const stars = [...src.matchAll(STAR_FROM)].map((m) => m[1]);
  if (stars.length) starReexports.set(f, stars);
}

/* ── resolve a specifier to a file on disk ────────────────────────────── */

function resolveSpec(fromFile, spec) {
  let base;
  if (spec.startsWith('@/')) base = join(SRC, spec.slice(2));
  else if (spec.startsWith('.')) base = resolve(dirname(fromFile), spec);
  else return { external: true };

  if (STYLE.has(extname(base))) {
    return existsSync(base) ? { file: base, style: true } : { missing: base, style: true };
  }
  for (const suffix of RESOLVE_ORDER) {
    const candidate = base + suffix;
    if (existsSync(candidate) && statSync(candidate).isFile()) return { file: candidate };
  }
  return { missing: base };
}

/** Follow `export * from` one level deep so barrels resolve. */
function exportsOf(file, depth = 0) {
  const own = new Set(exportsByFile.get(file) ?? []);
  if (depth > 3) return own;
  for (const spec of starReexports.get(file) ?? []) {
    const r = resolveSpec(file, spec);
    if (r.file) for (const n of exportsOf(r.file, depth + 1)) own.add(n);
  }
  return own;
}

/* ── check every import ───────────────────────────────────────────────── */

const IMPORT_RE = /import\s+(?:(type)\s+)?(?:([\w$]+)\s*,\s*)?(?:\{([^}]*)\}|([\w$]+)|\*\s+as\s+[\w$]+)?\s*(?:from\s*)?['"]([^'"]+)['"]/g;

const missingFiles = [];
const missingNames = [];
const anyUsages = [];
let importCount = 0;

for (const f of codeFiles) {
  const src = readFileSync(f, 'utf8');

  for (const m of src.matchAll(/:\s*any\b|<any>|as\s+any\b/g)) {
    const line = src.slice(0, m.index).split('\n').length;
    anyUsages.push(`${rel(f)}:${line}`);
  }

  for (const m of src.matchAll(IMPORT_RE)) {
    const [, , defaultImport, namedBlock, bareDefault, spec] = m;
    if (!spec) continue;
    importCount++;
    const r = resolveSpec(f, spec);
    if (r.external) continue;
    if (r.missing) {
      missingFiles.push(`${rel(f)}  →  ${spec}`);
      continue;
    }
    if (r.style) continue;

    const available = exportsOf(r.file);
    const wanted = [];
    if (defaultImport || bareDefault) wanted.push('default');
    if (namedBlock) {
      for (const part of namedBlock.split(',')) {
        const name = part.trim().replace(/^type\s+/, '').split(/\s+as\s+/)[0]?.trim();
        if (name) wanted.push(name);
      }
    }
    for (const w of wanted) {
      if (w && !available.has(w)) {
        missingNames.push(`${rel(f)}  →  { ${w} } from '${spec}'`);
      }
    }
  }
}

/* ── report ───────────────────────────────────────────────────────────── */

const line = (s = '') => console.log(s);
line('KALPAVRIKSHA DESKTOP — static wiring check');
line('─'.repeat(60));
line(`modules      ${codeFiles.length}`);
line(`stylesheets  ${files.filter((f) => STYLE.has(extname(f))).length}`);
line(`imports      ${importCount}`);
line();

let failed = false;

if (missingFiles.length) {
  failed = true;
  line(`UNRESOLVED IMPORTS (${missingFiles.length})`);
  for (const x of missingFiles) line('  ' + x);
  line();
} else line('unresolved imports    none');

if (missingNames.length) {
  failed = true;
  line(`MISSING NAMED EXPORTS (${missingNames.length})`);
  for (const x of missingNames) line('  ' + x);
  line();
} else line('missing named exports none');

if (anyUsages.length) {
  line(`\`any\` usages (${anyUsages.length}) — review, not necessarily fatal`);
  for (const x of anyUsages.slice(0, 20)) line('  ' + x);
} else line('`any` usages          none');

line();
line(failed ? 'RESULT: FINDINGS — fix before first run' : 'RESULT: CLEAN');
line('Note: this is not a substitute for `npm run typecheck`.');
process.exit(failed ? 1 : 0);
