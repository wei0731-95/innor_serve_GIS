require('./modem.js');
const M = globalThis.HFModem;

// 1) RS 測試
let rsOk = 0;
for (let t = 0; t < 2000; t++) {
  const n = 1 + Math.floor(Math.random() * 40), msg = Array.from({ length: n }, () => Math.random() * 256 | 0);
  const cw = M.rsEncode(msg, 6), ne = Math.floor(Math.random() * 4);
  const pos = new Set(); while (pos.size < ne) pos.add(Math.random() * cw.length | 0);
  for (const p of pos) cw[p] ^= 1 + (Math.random() * 255 | 0);
  try { const r = M.rsDecode(cw, 6); if (r.data.join() === msg.join()) rsOk++; } catch (e) {}
}
console.log('RS (0-3 byte errors) correct:', rsOk, '/ 2000');

// 2) 通道模擬
function gauss() { let u = 0, v = 0; while (!u) u = Math.random(); v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function resample(x, r) { const n = Math.floor(x.length * r), o = new Float32Array(n);
  for (let i = 0; i < n; i++) { const s = i / r, a = Math.floor(s), f = s - a; o[i] = (x[a] || 0) * (1 - f) + (x[a + 1] || 0) * f; } return o; }
function channel(sig, fsTx, fsRx, o) {
  let x = fsTx === fsRx ? sig : resample(sig, fsRx / fsTx);
  const lead = Math.round(fsRx * (0.3 + Math.random())), tail = Math.round(fsRx * 0.5);
  const y = new Float32Array(lead + x.length + tail + Math.round(fsRx * o.rt));
  // 直達 + 回音（稀疏反射，指數衰減）
  const taps = [[0, 1]]; for (let i = 0; i < 300; i++) { const d = Math.random() * o.rt;
    taps.push([Math.round((0.003 + d) * fsRx), o.rev * gauss() * Math.exp(-6.9 * d / o.rt) / Math.sqrt(30)]); }
  for (const [d, g] of taps) for (let i = 0; i < x.length; i++) y[lead + d + i] += x[i] * g * o.gain;
  // 噪音：寬頻白噪音 + 低頻強噪音（模擬人聲/列車）
  for (let i = 0; i < y.length; i++) y[i] += o.noise * gauss() + 0.3 * Math.sin(2 * Math.PI * 300 * i / fsRx) * Math.sin(2 * Math.PI * 1.3 * i / fsRx);
  return y;
}
function trial(o, fsTx, fsRx, cfg) {
  const msg = M.encodeTemplate(1 + (Math.random() * 7 | 0), Math.random() * 30 | 0, Math.random() * 9 | 0);
  const sig = M.synthesize(msg, cfg, fsTx), y = channel(sig, fsTx, fsRx, o);
  let got = null; const r = new M.Receiver(fsRx, cfg, m => { if (m.ok && !got) got = m; });
  for (let i = 0; i < y.length; i += 2048) r.push(y.subarray(i, i + 2048));
  return got && got.payload.join() === msg.join();
}
const cfg = Object.assign({}, M.DEFAULTS);
// 頻帶內 SNR：訊號功率 (gain*0.6)^2/2；噪音在一個 22Hz bin 內的功率比較才是重點，這裡只報寬頻 SNR
for (const [label, o] of [
  ['安靜、無回音', { gain: 0.05, noise: 0.002, rev: 0, rt: 0.05 }],
  ['中等噪音、回音 0.4s', { gain: 0.05, noise: 0.02, rev: 0.5, rt: 0.4 }],
  ['強噪音、回音 0.8s', { gain: 0.05, noise: 0.05, rev: 0.7, rt: 0.8 }],
  ['極強噪音、強回音 1.2s', { gain: 0.05, noise: 0.1, rev: 1.0, rt: 1.2 }],
]) {
  for (const [fsTx, fsRx] of [[48000, 48000], [48000, 44100]]) {
    let ok = 0; const T = 30; const t0 = Date.now();
    for (let i = 0; i < T; i++) if (trial(o, fsTx, fsRx, cfg)) ok++;
    const snr = 10 * Math.log10(((o.gain * 0.6) ** 2 / 2) / (o.noise ** 2));
    console.log(`${label.padEnd(18)} 寬頻SNR ${snr.toFixed(1).padStart(6)} dB  ${fsTx}->${fsRx}: ${ok}/${T}  (${((Date.now() - t0) / T).toFixed(0)} ms/次)`);
  }
}
// 封包長度
const s = M.frameSymbols(M.encodeTemplate(1, 5, 2), cfg);
console.log('模板封包符號數', s.length, '時長', (s.length * cfg.ts).toFixed(2), 's');
const s2 = M.frameSymbols(M.encodeText('列車延誤5分鐘'), cfg);
console.log('文字「列車延誤5分鐘」符號數', s2.length, '時長', (s2.length * cfg.ts).toFixed(2), 's');
