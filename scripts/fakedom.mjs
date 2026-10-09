// DOM giả + nạp view THẬT cho test màn QC (D159, D160): views/*.js cùng qcui + dom, modal / toast / bàn số
// thay bằng bản giả ghi lại lời gọi. DOM giả tối thiểu theo cây con (kids): đủ cho el(), innerHTML,
// classList, sự kiện click / input / change, querySelectorAll theo tên thẻ (segment() dùng).
//
// Dùng:
//   import { napView, kiem, ketThuc, tim, nut, dangChon, cho, MO, PAD, TOAST } from './fakedom.mjs';
//   const V = await napView('views/qc_xuatxuong.js');

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

export class E {
  constructor(tag = 'div') {
    this.tagName = String(tag).toUpperCase();
    this.kids = []; this.nghe = {}; this._lop = new Set(); this.dataset = {}; this.style = {};
    this.value = ''; this.disabled = false; this.type = ''; this._html = ''; this.textContent = '';
    this.classList = {
      add: (...c) => c.forEach((x) => this._lop.add(x)),
      remove: (...c) => c.forEach((x) => this._lop.delete(x)),
      contains: (c) => this._lop.has(c),
      toggle: (c, b) => {
        const on = b === undefined ? !this._lop.has(c) : !!b;
        if (on) this._lop.add(c); else this._lop.delete(c);
        return on;
      },
    };
  }

  get className() { return [...this._lop].join(' '); }

  set className(v) { this._lop.clear(); String(v || '').split(/\s+/).filter(Boolean).forEach((c) => this._lop.add(c)); }

  get innerHTML() { return this._html; }

  set innerHTML(h) {
    this._html = String(h); this.kids = [];
    this.textContent = this._html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
  }

  appendChild(x) { this.kids.push(x); return x; }

  setAttribute() {}

  addEventListener(ev, f) { (this.nghe[ev] = this.nghe[ev] || []).push(f); }

  bam() { (this.nghe.click || []).forEach((f) => f({ currentTarget: this, target: this, preventDefault() {} })); }

  doi(v) {
    this.value = v;
    ['input', 'change'].forEach((ev) => (this.nghe[ev] || []).forEach((f) => f({ target: this })));
  }

  querySelectorAll(q) {
    const tag = q.toUpperCase();
    const ra = [];
    const di = (e) => e.kids.forEach((k) => { if (k.tagName === tag) ra.push(k); di(k); });
    di(this);
    return ra;
  }

  querySelector(q) { return this.querySelectorAll(q)[0] || null; }

  get chu() { return [this.textContent, ...this.kids.map((k) => k.chu)].join(' ').replace(/\s+/g, ' ').trim(); }
}

globalThis.document = { createElement: (t) => new E(t) };
globalThis.window = { open: () => null };

export const MO = [];
export const PAD = [];
export const TOAST = [];
globalThis.__gia = {
  openModal: (o) => { const m = { ...o, body: new E('div'), dong: false, close() { m.dong = true; } }; MO.push(m); return m; },
  numpad: (o) => { PAD.push(o); },
  toast: (s, k) => { TOAST.push([s, k]); },
};

const GOC = 'sx/public/sx/';

/** Nạp một view thật (đổi đường /assets/... sang tệp tạm) cùng dom, qcui, anh; trả module. */
export async function napView(rel) {
  const tam = mkdtempSync(join(tmpdir(), 'sx-view-'));
  const tep = (r) => join(tam, `${r.replace(/\//g, '__').replace(/\.js$/, '')}.mjs`);
  const doiDuong = (src) => src.replace(/from '\/assets\/sx\/sx\/([^']+)'/g,
    (_, r) => `from '${pathToFileURL(tep(r)).href}'`);
  for (const r of ['lib/dom.js', 'lib/anh.js', 'components/qcui.js', rel]) {
    writeFileSync(tep(r), doiDuong(readFileSync(GOC + r, 'utf8')));
  }
  writeFileSync(tep('components/modal.js'), 'export const openModal = (o) => globalThis.__gia.openModal(o);\n'
    + 'export const confirm2Step = () => {};\n');
  writeFileSync(tep('components/toast.js'), 'export const toast = (s, k) => globalThis.__gia.toast(s, k);\n'
    + "export const toastErr = (s) => globalThis.__gia.toast(s, 'err');\n");
  writeFileSync(tep('components/numpad.js'), 'export const openNumpad = (o) => globalThis.__gia.numpad(o);\n');
  try {
    return await import(pathToFileURL(tep(rel)).href);
  } finally { rmSync(tam, { recursive: true, force: true }); }
}

let hong = 0;
export function kiem(ten, dk, ct = '') {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${!dk && ct !== '' ? ` — ${typeof ct === 'string' ? ct : JSON.stringify(ct)}` : ''}`);
}

export function ketThuc(ten) {
  console.log(`\n${hong ? `${ten}-FAIL (${hong})` : `${ten}-OK`}`);
  process.exit(hong ? 1 : 0);
}

export const bang = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const cho = () => new Promise((r) => { setTimeout(r, 0); });
export function tim(goc, dk) {
  const ra = [];
  const di = (e) => e.kids.forEach((k) => { if (dk(k)) ra.push(k); di(k); });
  di(goc);
  return ra;
}
export const nut = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.trim() === chu)[0];
export const dangChon = (seg) => (tim(seg, (e) => e.tagName === 'BUTTON' && e.classList.contains('sx-qc-seg-on'))[0] || {})
  .textContent || '';
