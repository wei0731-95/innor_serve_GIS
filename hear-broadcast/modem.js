/* 聽見廣播 PoC — 高頻聲波數據機核心
 * 調變：18 個頻率的連續相位 FSK（0=同步A, 1=同步B, 2..17=資料 4 bits）
 * 封包：前導碼 A B A B ｜ 長度 ｜ ~長度 ｜ Reed-Solomon(資料 + nsym 個檢查位元組)
 */
(function (G) {
'use strict';

// ---------- GF(256) 與 Reed-Solomon ----------
const EXP = new Uint8Array(512), LOG = new Uint8Array(256);
{ let x = 1; for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11d; }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255]; }
const m255 = a => ((a % 255) + 255) % 255;
const gmul = (x, y) => (x === 0 || y === 0) ? 0 : EXP[LOG[x] + LOG[y]];
const gdiv = (x, y) => { if (y === 0) throw Error('div0'); return x === 0 ? 0 : EXP[m255(LOG[x] + 255 - LOG[y])]; };
const gpow = (x, p) => EXP[m255(LOG[x] * p)];
const ginv = x => EXP[255 - LOG[x]];
const pscale = (p, x) => p.map(c => gmul(c, x));
const padd = (p, q) => { const n = Math.max(p.length, q.length), r = new Array(n).fill(0);
  for (let i = 0; i < p.length; i++) r[i + n - p.length] = p[i];
  for (let i = 0; i < q.length; i++) r[i + n - q.length] ^= q[i]; return r; };
const pmul = (p, q) => { const r = new Array(p.length + q.length - 1).fill(0);
  for (let j = 0; j < q.length; j++) for (let i = 0; i < p.length; i++) r[i + j] ^= gmul(p[i], q[j]); return r; };
const peval = (p, x) => { let y = p[0]; for (let i = 1; i < p.length; i++) y = gmul(y, x) ^ p[i]; return y; };
const pdiv = (a, b) => { const o = a.slice();
  for (let i = 0; i < a.length - (b.length - 1); i++) { const c = o[i];
    if (c !== 0) for (let j = 1; j < b.length; j++) if (b[j] !== 0) o[i + j] ^= gmul(b[j], c); }
  const s = o.length - (b.length - 1); return [o.slice(0, s), o.slice(s)]; };
const genCache = {};
function genPoly(n) { if (genCache[n]) return genCache[n]; let g = [1];
  for (let i = 0; i < n; i++) g = pmul(g, [1, gpow(2, i)]); return (genCache[n] = g); }
function rsEncode(msg, n) { const g = genPoly(n), o = msg.concat(new Array(n).fill(0));
  for (let i = 0; i < msg.length; i++) { const c = o[i]; if (c !== 0) for (let j = 1; j < g.length; j++) o[i + j] ^= gmul(g[j], c); }
  for (let i = 0; i < msg.length; i++) o[i] = msg[i]; return o; }
function syndromes(msg, n) { const s = [0]; for (let i = 0; i < n; i++) s.push(peval(msg, gpow(2, i))); return s; }
function errLocator(s, n) { let el = [1], ol = [1]; const sh = s.length - n;
  for (let i = 0; i < n; i++) { const K = i + sh; let d = s[K];
    for (let j = 1; j < el.length; j++) d ^= gmul(el[el.length - 1 - j], s[K - j]);
    ol = ol.concat([0]);
    if (d !== 0) { if (ol.length > el.length) { const nl = pscale(ol, d); ol = pscale(el, ginv(d)); el = nl; }
      el = padd(el, pscale(ol, d)); } }
  while (el.length && el[0] === 0) el.shift();
  if ((el.length - 1) * 2 > n) throw Error('too many errors'); return el; }
function findErrors(elRev, nm) { const errs = elRev.length - 1, pos = [];
  for (let i = 0; i < nm; i++) if (peval(elRev, gpow(2, i)) === 0) pos.push(nm - 1 - i);
  if (pos.length !== errs) throw Error('locate failed'); return pos; }
function errataLocator(cp) { let e = [1]; for (const i of cp) e = pmul(e, padd([1], [gpow(2, i), 0])); return e; }
function errEvaluator(s, el, n) { return pdiv(pmul(s, el), [1].concat(new Array(n + 1).fill(0)))[1]; }
function correctErrata(msg, s, pos) {
  const cp = pos.map(p => msg.length - 1 - p), el = errataLocator(cp);
  const ev = errEvaluator(s.slice().reverse(), el, el.length - 1).reverse();
  const X = cp.map(c => gpow(2, -(255 - c))), E = new Array(msg.length).fill(0);
  for (let i = 0; i < X.length; i++) { const Xi = X[i], Xinv = ginv(Xi); let elp = 1;
    for (let j = 0; j < X.length; j++) if (j !== i) elp = gmul(elp, 1 ^ gmul(Xinv, X[j]));
    const y = gmul(Xi, peval(ev.slice().reverse(), Xinv));
    if (elp === 0) throw Error('forney'); E[pos[i]] = gdiv(y, elp); }
  return padd(msg, E); }
function rsDecode(msg, n) { let s = syndromes(msg, n);
  if (Math.max(...s) === 0) return { data: msg.slice(0, -n), fixed: 0 };
  const el = errLocator(s, n), pos = findErrors(el.slice().reverse(), msg.length);
  const out = correctErrata(msg, s, pos); s = syndromes(out, n);
  if (Math.max(...s) !== 0) throw Error('uncorrectable');
  return { data: out.slice(0, -n), fixed: pos.length }; }

// ---------- 調變參數 ----------
const DEFAULTS = { f0: 17000, df: 100, ts: 0.06, nsym: 6, maxLen: 48 };
const NT = 18;
const freqs = c => Array.from({ length: NT }, (_, i) => c.f0 + i * c.df);
const PRE = [0, 1, 0, 1];

function frameSymbols(payload, c) {
  if (!payload.length || payload.length > c.maxLen) throw Error('payload length 1..' + c.maxLen);
  const bytes = [payload.length, (~payload.length) & 255].concat(rsEncode(Array.from(payload), c.nsym));
  const sym = PRE.slice(); for (const b of bytes) sym.push(2 + (b >> 4), 2 + (b & 15)); return sym;
}
// 產生音訊：連續相位（不會有喀喀聲），頭尾 20ms 淡入淡出
function synthesize(payload, c, fs, amp = 0.6) {
  const sym = frameSymbols(payload, c), F = freqs(c), N = Math.round(c.ts * fs);
  const ramp = Math.round(0.02 * fs), pad = Math.round(0.05 * fs);
  const out = new Float32Array(pad * 2 + N * sym.length); let ph = 0, k = pad;
  for (const s of sym) { const w = 2 * Math.PI * F[s] / fs;
    for (let i = 0; i < N; i++) { out[k++] = Math.sin(ph); ph += w; } ph %= 2 * Math.PI; }
  const a = pad, b = pad + N * sym.length;
  for (let i = a; i < b; i++) { let g = 1;
    if (i - a < ramp) g = 0.5 - 0.5 * Math.cos(Math.PI * (i - a) / ramp);
    else if (b - i < ramp) g = 0.5 - 0.5 * Math.cos(Math.PI * (b - i) / ramp);
    out[i] *= g * amp; }
  return out;
}

// ---------- 接收端（串流處理） ----------
class Receiver {
  constructor(fs, cfg, onMessage, onLevel) {
    this.fs = fs; this.c = Object.assign({}, DEFAULTS, cfg || {});
    this.onMessage = onMessage || (() => {}); this.onLevel = onLevel || (() => {});
    this.F = freqs(this.c); this.N = Math.round(this.c.ts * fs);
    this.hop = Math.max(1, Math.round(this.N / 12)); this.k = Math.round(this.N / this.hop);
    this.Wd = Math.round(this.N * 0.75);
    this.cap = Math.round(fs * 24); this.buf = new Float32Array(this.cap);
    this.total = 0; this.nextHop = this.Wd; this.hist = [];
    this.state = 'search'; this.quietUntil = 0; this.thr = 0.3;
    this.coef = this.F.map(f => 2 * Math.cos(2 * Math.PI * f / fs)); this.win = {};
    this.stats = { ok: 0, fail: 0 };
  }
  hann(L) { return this.win[L] || (this.win[L] = Float32Array.from({ length: L }, (_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (L - 1)))); }
  seg(start, L) { const w = this.hann(L), o = new Float32Array(L);
    for (let i = 0; i < L; i++) o[i] = this.buf[(start + i) % this.cap] * w[i]; return o; }
  powers(x, idx) { return idx.map(t => { const c = this.coef[t]; let s1 = 0, s2 = 0;
    for (let i = 0; i < x.length; i++) { const s0 = x[i] + c * s1 - s2; s2 = s1; s1 = s0; }
    return s1 * s1 + s2 * s2 - c * s1 * s2; }); }
  push(chunk) {
    for (let i = 0; i < chunk.length; i++) this.buf[(this.total + i) % this.cap] = chunk[i];
    this.total += chunk.length;
    while (this.total >= this.nextHop) { this.onHop(this.nextHop); this.nextHop += this.hop; }
    this.advance();
  }
  onHop(t) {
    const P = this.powers(this.seg(t - this.Wd, this.Wd), ALL);
    const sum = P.reduce((a, b) => a + b, 0) + 1e-12;
    this.hist.push({ t, a: P[0] / sum, b: P[1] / sum }); if (this.hist.length > 6 * this.k) this.hist.shift();
    const h = this.hist, n = h.length, k = this.k; let score = 0;
    if (n > 3 * k) score = Math.min(h[n - 1].b, h[n - 1 - k].a, h[n - 1 - 2 * k].b, h[n - 1 - 3 * k].a);
    this.onLevel(P, score, sum / this.Wd);
    if (t < this.quietUntil) return;
    if (this.state === 'search' && score > this.thr) { this.state = 'peak'; this.best = { s: score, t }; this.peakUntil = t + this.N; }
    else if (this.state === 'peak') {
      if (score > this.best.s) this.best = { s: score, t };
      if (t >= this.peakUntil) { this.state = 'header';
        this.p = Math.round(this.best.t + (this.N - this.Wd) / 2 - 4 * this.N); }
    }
  }
  symPowers(p, j, idx) { const st = p + j * this.N + Math.round(0.2 * this.N);
    return this.powers(this.seg(st, Math.round(0.75 * this.N)), idx); }
  dataSym(p, j) { const P = this.symPowers(p, j, DATA); let b = 0;
    for (let i = 1; i < 16; i++) if (P[i] > P[b]) b = i; return b; }
  align(p0) { // 以前導碼微調起點，±N/4，1ms 間距
    const step = Math.max(1, Math.round(this.fs * 0.001)), R = Math.round(this.N / 4); let best = p0, bs = -1;
    for (let d = -R; d <= R; d += step) { let s = 0;
      for (let j = 0; j < 4; j++) { const P = this.symPowers(p0 + d, j, ALL), sum = P.reduce((a, b) => a + b, 0) + 1e-12;
        s += P[PRE[j]] / sum; }
      if (s > bs) { bs = s; best = p0 + d; } }
    return best;
  }
  advance() {
    const N = this.N, margin = Math.round(N * 0.3);
    if (this.state === 'header' && this.total >= this.p + 8 * N + margin) {
      this.p = this.align(this.p);
      const by = j => (this.dataSym(this.p, j) << 4) | this.dataSym(this.p, j + 1);
      const len = by(4), nl = by(6);
      if ((len ^ nl) !== 255 || len === 0 || len > this.c.maxLen) { this.reset(this.p + 4 * N); return; }
      this.len = len; this.S = 8 + 2 * (len + this.c.nsym); this.state = 'body';
    }
    if (this.state === 'body' && this.total >= this.p + this.S * N + margin) {
      const bytes = [];
      for (let j = 8; j < this.S; j += 2) bytes.push((this.dataSym(this.p, j) << 4) | this.dataSym(this.p, j + 1));
      try { const r = rsDecode(bytes, this.c.nsym); this.stats.ok++;
        this.onMessage({ payload: r.data, fixed: r.fixed, ok: true, stats: this.stats }); }
      catch (e) { this.stats.fail++; this.onMessage({ ok: false, error: e.message, stats: this.stats }); }
      this.reset(this.p + this.S * N);
    }
  }
  reset(until) { this.state = 'search'; this.quietUntil = until; this.hist = []; }
}
const ALL = Array.from({ length: NT }, (_, i) => i), DATA = ALL.slice(2);

// ---------- 封包內容格式 ----------
// 0x01 模板：[0x01, 模板編號, 參數1, 參數2]；0x02 文字：[0x02, ...UTF-8]
const encodeTemplate = (id, p1 = 0, p2 = 0) => [1, id & 255, p1 & 255, p2 & 255];
const encodeText = s => { const b = Array.from(new TextEncoder().encode(s)); return [2].concat(b); };
function parsePayload(p) {
  if (p[0] === 1) return { type: 'template', id: p[1], p1: p[2], p2: p[3] };
  if (p[0] === 2) return { type: 'text', text: new TextDecoder().decode(new Uint8Array(p.slice(1))) };
  return { type: 'unknown', bytes: p };
}

G.HFModem = { DEFAULTS, freqs, frameSymbols, synthesize, Receiver, rsEncode, rsDecode,
  encodeTemplate, encodeText, parsePayload };
})(typeof window !== 'undefined' ? window : globalThis);
