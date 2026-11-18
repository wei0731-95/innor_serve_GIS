// 自動偵測測試：發送端隨機選一組設定，接收端不知道設定，看能否解出並鎖定正確設定
require('./modem.js'); const M = globalThis.HFModem;
const code = require('fs').readFileSync(__dirname + '/test.js', 'utf8');
eval(code.slice(code.indexOf('function gauss'), code.indexOf('function trial')));
const S = [['安靜', { gain: 0.05, noise: 0.002, rev: 0, rt: 0.05 }], ['中等+0.4s回音', { gain: 0.05, noise: 0.02, rev: 0.5, rt: 0.4 }],
  ['強噪音+0.8s回音', { gain: 0.05, noise: 0.05, rev: 0.7, rt: 0.8 }]];
for (const [name, o] of S) {
  let ok = 0, rightLock = 0, T = 24;
  for (let t = 0; t < T; t++) {
    const c = M.CANDIDATES[t % 8], msg = M.encodeTemplate(1 + (t % 5), t, 2);
    const y = channel(M.synthesize(msg, c, 48000, 0.6), 48000, 44100, o);
    let got = null, lock = null;
    const a = new M.AutoReceiver(44100, m => { if (m.ok && !got) got = m; }, null, cfg => { if (cfg) lock = cfg; });
    for (let i = 0; i < y.length; i += 4096) a.push(y.subarray(i, i + 4096));
    if (got && got.payload.join() === msg.join()) ok++;
    if (lock && lock.f0 === c.f0 && lock.ts === c.ts) rightLock++;
  }
  console.log(`${name.padEnd(14)} 解碼成功 ${ok}/${T}，鎖定正確設定 ${rightLock}/${T}`);
}
// 換設定：先用 17k 標準，鎖定後超過時限沒訊息 → 回到掃描 → 改用 18.5k 穩定也能收到
{
  const c1 = M.CANDIDATES[2], c2 = M.CANDIDATES[7], fs = 44100, got = [], locks = [];
  const a = new M.AutoReceiver(fs, m => m.ok && got.push(M.parsePayload(m.payload).id), null, c => locks.push(c ? c.f0 + '/' + c.ts : '掃描'), undefined, 3);
  const feed = x => { for (let i = 0; i < x.length; i += 4096) a.push(x.subarray(i, i + 4096)); };
  const rs = x => resample(x, fs / 48000);
  feed(rs(M.synthesize(M.encodeTemplate(1, 1, 0), c1, 48000))); feed(new Float32Array(fs * 5));
  feed(rs(M.synthesize(M.encodeTemplate(3, 0, 1), c2, 48000))); feed(new Float32Array(fs));
  console.log('換設定測試：收到模板', got.join(','), '｜鎖定變化', locks.join(' → '));
}
