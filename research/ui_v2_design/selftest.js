'use strict';
// 自检（无需浏览器）。加载 prototype.html 的脚本，检查（以 ±9 为准）：
//   1) 宽度：逐项 8 字符，紧凑 7–8 字符，Amount 8 字符，穷举全部取值；
//   2) 对齐：数字在固定列；0 的符号位留空；上下限 "!" 只在端点，位置固定；
//   3) 数值范围：各项 ±档位，Amount 为 0%–150%（16 档）；
//   4) 随机按键遍历（固定种子，含档位切换）下的不变量；
//   5) 场景断言（有界循环）；
//   6) 打印 ASCII 示意与各类文字的最大宽度（供 DESIGN.md 引用）。
// 用法（仓库根）：node research/ui_v2_design/selftest.js > research/ui_v2_design/selftest.out.txt
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, 'prototype.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error('prototype.html 中没有 <script>');

const stubEl = () => ({ style: {}, innerHTML: '', textContent: '', checked: false, hidden: false, className: '', addEventListener() {} });
const ctx = { console, document: { getElementById: () => stubEl(), addEventListener() {} } };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(m[1], ctx, { filename: 'prototype.html' });
const G = ctx.GXR;

let fails = 0, passes = 0;
function check(name, cond, extra) {
  if (cond) passes++;
  else { fails++; console.log('FAIL: ' + name + (extra !== undefined ? '  -> ' + JSON.stringify(extra) : '')); }
}
const ASCII = /^[\x20-\x7e]+$/;
const ok8 = (t) => t.length <= 8 && ASCII.test(t);
const isDig = (c) => c !== undefined && /^[0-9]$/.test(c);
const texts = (S) => G.screenRows(S).map((r) => r.t);
const press = (S, ...ks) => { ks.forEach((k) => G.press(S, k)); return S; };
const fresh = () => { const S = G.newState(); G.setRange(S, 9); return S; };
function goRow(S, row) {
  for (let i = 0; i < 80; i++) {
    if (S.cur === row) return S;
    G.press(S, S.cur < row ? 'DOWN' : 'UP');
    if (S.screen === 'closed') break;
  }
  if (S.cur !== row) throw new Error('goRow 未到达第 ' + row + ' 行，当前 ' + S.screen + ' ' + S.cur);
  return S;
}
const STEP = ['Cont', 'High', 'Shad', 'Fade', 'Satu', 'Warm', 'Tint', 'Splt', 'Filt', 'Tone'];
const isLimStep = (n, R) => n === R || n === -R;
const widths = {};
function note(cat, t) { widths[cat] = Math.max(widths[cat] || 0, t.length); }

// ---------- 1–3. 宽度与对齐（穷举；三种档位）----------
for (const R of [9, 7, 15]) {
  ctx.RANGE = R;
  for (const key of STEP) {
    for (let n = -R; n <= R; n++) {
      const t = G.valText(key, n);
      const tag = '[±' + R + '] ' + key + ' ' + n + ' → "' + t + '"';
      const digits = String(Math.abs(n));
      check(tag + ' 恰为 8 字符', t.length === 8 && ASCII.test(t), t.length);
      check(tag + ' 数字结尾于第 8 列', t.endsWith(n === 0 ? '0' : digits), t);
      check(tag + ' 符号紧挨数字；0 的符号位留空', n === 0 ? t.endsWith('  0') : t.endsWith((n < 0 ? '-' : '+') + digits), t);
      check(tag + ' "!" 在标签后，只在端点', (t[4] === '!') === isLimStep(n, R) && (t[4] === '!' || t[4] === ' '), t);
      note(R === 9 ? '逐项行（±9）' : '逐项行（±' + R + '）', t);
    }
  }
  for (let n = -10; n <= 5; n++) {
    const t = G.valText('Amt', n);
    const tag = '[±' + R + '] Amt ' + n + ' → "' + t + '"';
    check(tag + ' 恰为 8 字符', t.length === 8 && ASCII.test(t), t.length);
    check(tag + ' % 在第 8 列，数字右对齐', t[7] === '%' && isDig(t[6]), t);
    check(tag + ' "!" 只在 0% 与 150%', (t[3] === '!') === (n === -10 || n === 5), t);
    const f = G.amtCompact(n);
    check(tag + ' 紧凑 Amount 6 字符', f.length === 6 && f[5] === '%' && (f[1] === '!') === (n === -10 || n === 5), f);
    note('Amount 逐项行', t);
    note('Amount 紧凑行', f);
  }
  // 紧凑：两格一行，任意组合都 ≤8 字符；字母在固定列
  for (const type of ['C', 'B']) {
    const keys = G.ITEMS[type];
    for (const js of G.PAIRS[type]) {
      for (let a = -R; a <= R; a++) for (let b = -R; b <= R; b++) {
        const vec = keys.map(() => 0); vec[js[0]] = a; vec[js[1]] = b;
        const t = G.pairText(keys, vec, js);
        const tag = '[±' + R + '] 紧凑 ' + keys[js[0]] + '/' + keys[js[1]] + ' (' + a + ',' + b + ') → "' + t + '"';
        check(tag + ' ≤8 字符、ASCII', ok8(t), t);
        if (R > 9) check(tag + ' ±15：两格恒为 8 字符，无 "!"（0 的符号位为空格）', t.length === 8 && !t.includes('!'), t);
        else check(tag + ' 字母在第 1、5 列；数字在第 3、7 列', /[A-Z]/.test(t[0]) && /[A-Z]/.test(t[4]) && isDig(t[2]) && isDig(t[6]), t);
        note(type === 'C' ? '紧凑两项一行（彩色，±' + R + '）' : '紧凑两项一行（黑白，±' + R + '）', t);
      }
    }
  }
}
ctx.RANGE = 9;
check('默认档位为 ±9', G.getRange() === 9);
check('0 显示为 "Cont   0"（符号位留空）', G.valText('Cont', 0) === 'Cont   0');
check('紧凑 0 为 "C 0"', G.cellText('Cont', 0) === 'C 0');
check('例：Cont +9 / Cont -9 / C+9 H-9', G.valText('Cont', 9) === 'Cont! +9' && G.valText('Cont', -9) === 'Cont! -9' && G.valText('Cont', 8) === 'Cont  +8' && G.pairText(G.ITEMS.C, [0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1]) === 'C 0 H 0');
check('例：Amt 150%（限位）为 "Amt!150%"，未限位写法 "Amt 140%"', G.valText('Amt', 5) === 'Amt!150%' && G.valText('Amt', 4) === 'Amt 140%', [G.valText('Amt', 5), G.valText('Amt', 4)]);
check('Amount 16 档：0%…150%，每档 10%', (() => { const v = []; for (let a = -10; a <= 5; a++) v.push(G.pct(a)); return JSON.stringify(v) === JSON.stringify([0,10,20,30,40,50,60,70,80,90,100,110,120,130,140,150]); })());

// ---------- 4. 随机遍历（含档位切换）----------
function rng(seed) { let s = seed >>> 0; return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; }
// 标签清单：遍历中实际出现过的文字，按屏幕与行的类别归档（供 DESIGN.md 第 8 节核对）
const CAT = {};
function addCat(cat, t) { (CAT[cat] = CAT[cat] || new Set()).add(t); }
function collectLabels(S) {
  if (S.screen === 'closed') return;
  const rows = G.screenRows(S);
  if (S.screen === 'list') rows.forEach((r, i) => addCat(i < 8 ? 'L1 配方行' : (i === 8 ? 'L1 MyRec 行' : 'L1 第 10 行'), r.t));
  else if (S.screen === 'grp') rows.forEach((r, i) => addCat(i === 0 ? 'G 第一行' : 'G 分组行', r.t));
  else if (S.screen === 'ent') rows.forEach((r, i) => addCat(i === 0 ? 'E 第一行' : 'E 条目行 / None', r.t));
  else if (S.screen === 'ov') {
    const lay = G.ovLayout(S);
    rows.forEach((r, i) => {
      const k = lay[i].kind;
      addCat(k === 'title' ? '配方卡/逐项 第一行' : (k === 'pair' ? '配方卡 两项一行' : (k === 'item' ? (S.ovView === 'card' ? '配方卡 Amount 行' : '逐项列表 各项') : '动作行（含状态词）')), r.t);
    });
  } else if (S.screen === 'vs') rows.forEach((r) => addCat('数值页 各行', r.t));
  else rows.forEach((r) => addCat('状态屏', r.t));
}
function savedAll(S) { return JSON.stringify(S.entries.map((e) => [e.id, e.saved])); }
function inRange(key, v, R) { const l = G.keyLim(key, R); return Number.isInteger(v) && v >= l.lo && v <= l.hi; }
{
  const S = ctx.S;
  const rnd = rng(20261028);
  const events = ['UP', 'UP', 'DOWN', 'DOWN', 'DISP', 'DISP', 'EXIT', 'OPEN', 'BUSY', 'READY', 'ERR', 'POWER', 'RESTORE', 'BACK', 'RANGE'];
  const ranges = [7, 9, 15];
  let steps = 0;
  for (let round = 0; round < 40; round++) {
    G.powerCycle(S); S.restoreOn = rnd() < 0.5; G.setBusy(S, false);
    for (let k = 0; k < 600; k++) {
      steps++;
      const ev = events[Math.floor(rnd() * events.length)];
      const screenBefore = S.screen, appliedBefore = JSON.stringify(S.applied), tag = 'walk' + round + '/' + k + ' ' + ev;
      const savedBefore = savedAll(S), liveBefore = JSON.stringify(S.live), ovViewBefore = S.ovView, vsRowBefore = S.vsRow;
      if (ev === 'OPEN') G.open(S);
      else if (ev === 'BUSY') G.setBusy(S, true);
      else if (ev === 'READY') G.setBusy(S, false);
      else if (ev === 'ERR') { if (S.screen !== 'err') G.setErr(S); }
      else if (ev === 'POWER') {
        G.powerCycle(S);
        check(tag + ' 断电后活动值全为 0', S.live.every((v) => v.every((x) => x === 0)));
        check(tag + ' 断电后条目恢复为已保存内容', S.entries.every((e) => JSON.stringify(e.vec) === JSON.stringify(e.saved)));
      } else if (ev === 'RESTORE') S.restoreOn = !S.restoreOn;
      else if (ev === 'BACK') G.setBackMode(S, rnd() < 0.5 ? 'title' : 'row');
      else if (ev === 'RANGE') G.setRange(S, ranges[Math.floor(rnd() * 3)]);
      else {
        G.press(S, ev);
        if (ev === 'EXIT') {
          check(tag + ' 退出：列表关闭', S.screen === 'closed', S.screen);
          check(tag + ' 退出：保留现在看到的效果（应用的配方与数值不变）', JSON.stringify(S.live) === liveBefore && JSON.stringify(S.applied) === appliedBefore);
          check(tag + ' 退出不改已保存数据', savedAll(S) === savedBefore);
        }
        if (screenBefore === 'err') check(tag + ' 锁定态只允许退出', S.screen === 'err' || S.screen === 'closed');
        if (screenBefore === 'list' && (ev === 'UP' || ev === 'DOWN') && (S.cur === G.IDX_MY || S.cur === G.IDX_HINT)) {
          check(tag + ' 非配方行不改应用的配方', JSON.stringify(S.applied) === appliedBefore, [S.applied, appliedBefore]);
        }
        if (screenBefore === 'vs' && ev === 'DISP') {
          check(tag + ' 数值页 DISP 回到上一屏原行，视图不变', S.screen === 'ov' && S.cur === vsRowBefore && S.ovView === ovViewBefore, [S.screen, S.cur, vsRowBefore, S.ovView]);
        }
      }
      // 不变量
      if (S.screen !== 'closed') {
        G.screenRows(S).forEach((r) => check(tag + ' 行文字 ≤8 ASCII', ok8(r.t), r.t));
        if (S.screen === 'vs') {
          const key = G.ITEMS[S.ov.k === 'b' ? G.BASE[S.ov.i].type : G.BASE[ctx.entById(S, S.ov.id).base].type][S.vsItem];
          const l = G.keyLim(key);
          check(tag + ' 数值页光标范围 = 档数', S.cur >= 0 && S.cur <= l.hi - l.lo, [S.cur, l]);
        } else if (S.screen !== 'err') check(tag + ' 光标范围', S.cur >= 0 && S.cur < G.screenRows(S).length, [S.screen, S.cur]);
      }
      if (S.screen === 'ov') {
        const lay = G.ovLayout(S), hasPair = lay.some((d) => d.kind === 'pair');
        check(tag + ' 无隐藏模式：逐项列表没有两项一行的行，配方卡有', S.ovView === 'edit' ? !hasPair : hasPair, [S.ovView, hasPair]);
        if (S.armed >= 0) check(tag + ' 确认只出现在动作行', lay[S.armed] && lay[S.armed].kind === 'act', S.armed);
      }
      if (S.applied.k === 'm') check(tag + ' 应用的条目存在', !!ctx.entById(S, S.applied.id));
      if (S.applied.k === 'b') check(tag + ' 应用的底子序号有效', S.applied.i >= 0 && S.applied.i <= 7);
      const R = ctx.RANGE;
      S.live.forEach((v, bi) => v.forEach((x, j) => check(tag + ' 活动值在该项范围内', inRange(G.ITEMS[G.BASE[bi].type][j], x, R), [G.ITEMS[G.BASE[bi].type][j], x])));
      S.entries.forEach((e) => e.vec.forEach((x, j) => check(tag + ' 条目值在该项范围内', inRange(G.ITEMS[G.BASE[e.base].type][j], x, R), x)));
      collectLabels(S);
    }
  }
  check('随机遍历步数', steps === 24000, steps);
  G.setRange(S, 9);
}

// 静态清单：设计中使用、但模型里不一定触发的文字（逐条核对长度与 ASCII）
['< Back', ' < Back', ' MyRec', '>MyRec', ' DISP:Tw', ' NoRest', 'Full', 'CardFul', 'SaveErr', 'NoCard', ' None', 'None',
  'Save*', 'Sure?', 'Saved', 'Default', 'Copy', 'Delete', 'Busy', 'Retry', 'ERR 701', ' GRP 999', '>FCC   1', ' FCC*001', '<FCC*001', '<4 Std',
  '<3 HC BW', '<5*F-CC', '<7 L-Chr', '<8*L-Viv', 'Cont! +9', 'Cont  +8', 'Cont   0', 'Cont! -9', 'Amt!150%', 'Amt!  0%', 'Amt 100%', 'Amt 140%',
  'C+9!H-9!', 'C+9 H-9', 'C 0 H 0', 'A!150%', 'A 100%', 'A!  0%', 'Filt!-9', 'Tone! +9', 'S 00F 00', 'C+05H-15']
  .forEach((t) => check('静态标签 ≤8 字符 ASCII: "' + t + '"', ok8(t), t.length));

// ---------- 5. 场景断言（默认 ±9）----------
{ // A. L1：应用中的配方用 > 标记，调过的用 *；光标与应用分开
  const S = fresh(); G.open(S);
  check('开机：04 带 > 标记，光标在它上面', S.cur === 3 && texts(S)[3] === '>4 Std', texts(S));
  check('第一行为 " 1 GRPos"', texts(S)[0] === ' 1 GRPos', texts(S)[0]);
  press(S, 'DOWN');
  check('下移一行：05 带 >，04 去掉标记', texts(S)[4] === '>5 F-CC' && texts(S)[3] === ' 4 Std', texts(S));
  goRow(S, 8);
  check('沿途经过 05–08：应用停在最后经过的 08；MyRec 无标记', S.applied.i === 7 && texts(S)[7] === '>8 L-Viv' && texts(S)[8] === ' MyRec', texts(S));
  press(S, 'DOWN');
  check('移到提示行：应用不变', texts(S)[9] === ' DISP:Tw' && S.applied.i === 7);
  press(S, 'EXIT');
  check('退出：关闭列表', S.screen === 'closed');
}
{ // B. 配方卡：第一行 <名字，两项一行，Amt，动作行；0 的符号位留空
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  check('配方卡 8 行（标题、四行两项、Amt、Default、Save）',
    JSON.stringify(texts(S)) === JSON.stringify(['<5 F-CC', 'C 0 H 0', 'S 0 F 0', 'V 0 W 0', 'T 0 P 0', 'A 100%', 'Default', 'Save']), texts(S));
  S.live[4][0] = 2; S.live[4][4] = -3;
  check('调过的配方：标题带 *，两项一行', texts(S)[0] === '<5*F-CC' && texts(S)[1] === 'C+2 H 0' && texts(S)[3] === 'V-3 W 0', texts(S));
  check('配方卡在一屏内（8 行 ≤ 9 行窗口）', texts(S).length <= G.VISIBLE);
  S.live[4][0] = 0; S.live[4][4] = 0;
}
{ // C. 两项一行 → 逐项列表（光标在左边一项）→ 数值页（光标在当前值）→ 返回
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP');
  check('配方卡按两项一行的行 DISP：进入逐项列表，光标在左边一项', S.ovView === 'edit' && S.cur === 1, [S.ovView, S.cur]);
  check('逐项列表 10 行（标题 + 9 项），0 的符号位留空', JSON.stringify(texts(S)) === JSON.stringify(['<5 F-CC', 'Cont   0', 'High   0', 'Shad   0', 'Fade   0', 'Satu   0', 'Warm   0', 'Tint   0', 'Splt   0', 'Amt 100%']), texts(S));
  press(S, 'DISP');
  check('数值页：19 行；光标在 0 的行（当前值）', S.screen === 'vs' && S.vsItem === 0 && S.cur === 9 && texts(S).length === 19, [S.cur, texts(S).length]);
  press(S, 'UP', 'UP');
  check('数值页上两格为 +2，光标跟到 +2 的行，实时应用', S.live[4][0] === 2 && S.cur === 7 && texts(S)[S.cur] === 'Cont  +2' && S.applied.i === 4, [S.cur, texts(S)[S.cur]]);
  press(S, 'DISP');
  check('数值页 DISP：回到逐项列表，同一行', S.screen === 'ov' && S.ovView === 'edit' && S.cur === 1 && texts(S)[1] === 'Cont  +2', [S.screen, S.cur]);
  press(S, 'UP', 'DISP');
  check('逐项列表标题 DISP：回到配方卡，光标回到第一行两项', S.ovView === 'card' && S.cur === 1 && texts(S)[1] === 'C+2 H 0', [S.ovView, S.cur, texts(S)[1]]);
  press(S, 'EXIT');
  check('退出保留 Cont +2', S.live[4][0] === 2 && S.screen === 'closed');
  S.live[4][0] = 0;
}
{ // D. Default 二次确认：移动即取消
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][0] = 3;
  goRow(S, 6); press(S, 'DISP');
  check('Default 第一次显示 Sure?', texts(S)[6] === 'Sure?' && S.armed === 6, texts(S)[6]);
  press(S, 'UP', 'DOWN');
  check('移开再回来：确认已取消', texts(S)[6] === 'Default' && S.armed === -1, texts(S)[6]);
  press(S, 'DISP', 'DISP');
  check('同一行两次 DISP：恢复为配方原样', S.live[4].every((v) => v === 0));
}
{ // E. 保存为新条目：组内序号 001，闪显 Saved，下一键清除
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][1] = -2;
  goRow(S, 7); press(S, 'DISP');
  check('保存为新条目：闪显 Saved，组内序号 1', texts(S)[7] === 'Saved' && S.entries.length === 1 && S.entries[0].gser === 1, texts(S));
  press(S, 'UP');
  check('下一次按键清除 Saved', texts(S)[7] === 'Save', texts(S)[7]);
  S.live[4][1] = 0;
}
{ // F. 上限：逐项与紧凑都显示 "!"，位置固定（±9）
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP', 'DISP');
  for (let i = 0; i < 12; i++) press(S, 'UP');
  check('Cont 到 +9：数值页显示 "Cont! +9"（8 字符）', S.live[4][0] === 9 && texts(S)[S.cur] === 'Cont! +9' && texts(S)[S.cur].length === 8, texts(S)[S.cur]);
  press(S, 'DISP');
  check('返回逐项列表后该行仍为 Cont! +9', S.ovView === 'edit' && texts(S)[1] === 'Cont! +9', texts(S)[1]);
  press(S, 'UP', 'DISP');
  check('配方卡：上限的 ! 占分隔位，数字列不变', S.ovView === 'card' && texts(S)[1] === 'C+9!H 0', texts(S)[1]);
  S.live[4][0] = 0;
}
{ // G. Amount：16 档；100% 为起点；150% 与 0% 为上下限
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  goRow(S, 5); press(S, 'DISP');
  check('Amt 行进入数值页：16 行，光标在 100%（第 6 行）', S.screen === 'vs' && S.vsItem === 8 && texts(S).length === 16 && S.cur === 5 && texts(S)[5] === 'Amt 100%', [S.cur, texts(S)]);
  for (let i = 0; i < 16; i++) press(S, 'UP');
  check('Amt 上限 150%：Amt!150%', S.live[4][8] === 5 && texts(S)[S.cur] === 'Amt!150%', [S.live[4][8], texts(S)[S.cur]]);
  press(S, 'DISP');
  check('返回配方卡：Amt 行为 A!150%', texts(S)[5] === 'A!150%', texts(S)[5]);
  goRow(S, 5); press(S, 'DISP');
  for (let i = 0; i < 20; i++) press(S, 'DOWN');
  check('Amt 下限 0%：Amt!  0%', S.live[4][8] === -10 && texts(S)[S.cur] === 'Amt!  0%', [S.live[4][8], texts(S)[S.cur]]);
  press(S, 'DISP');
  goRow(S, 5);
  S.live[4][8] = 0;
}
{ // H. 我的配方：分组 → 条目（应用中的条目带 >）→ 配方卡（10 行）→ 复制、删除
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][1] = -2; goRow(S, 7); press(S, 'DISP'); press(S, 'EXIT');
  G.open(S); goRow(S, G.IDX_MY); press(S, 'DISP');
  check('MyRec 进入分组：组行带数量，FCC 为 1', S.screen === 'grp' && texts(S)[5] === ' FCC   1', texts(S)[5]);
  goRow(S, 5); press(S, 'DISP');
  check('分组内条目：FCC*001', S.screen === 'ent' && texts(S)[1] === ' FCC*001', texts(S));
  press(S, 'DISP');
  check('条目配方卡：标题 <FCC*001，共 10 行', S.screen === 'ov' && texts(S)[0] === '<FCC*001' && texts(S).length === 10, texts(S));
  goRow(S, 8); press(S, 'DISP');
  check('Copy：新增一条（同底子同值），闪显 Saved', S.entries.length === 2 && texts(S)[8] === 'Saved' && S.entries[1].gser === 2, texts(S));
  press(S, 'UP'); goRow(S, 9); press(S, 'DISP');
  check('Delete 先确认', texts(S)[9] === 'Sure?');
  press(S, 'DISP');
  check('删除应用中的条目：回到分组，应用切回其底子 05', S.screen === 'ent' && S.entries.length === 1 && S.applied.k === 'b' && S.applied.i === 4, [S.screen, S.entries.length, S.applied]);
  press(S, 'EXIT');
}
{ // I. 提示行：DISP 打开应用的配方；返回方式可切换（< Back 行）
  const S = fresh(); G.open(S); goRow(S, G.IDX_HINT);          // 沿途经过 05–08，应用停在 08
  check('提示行上应用的配方不变（沿途最后经过的 08）', S.applied.i === 7 && S.cur === 9);
  press(S, 'DISP');
  check('提示行 DISP 打开 08 的配方卡，第一行 <8 L-Viv', S.screen === 'ov' && S.ov.i === 7 && texts(S)[0] === '<8 L-Viv', texts(S)[0]);
  G.setBackMode(S, 'row');
  check('设置为 < Back 行：第一行为 " < Back"', texts(S)[0] === ' < Back', texts(S)[0]);
  press(S, 'UP', 'DISP');
  check('< Back 行 DISP：回到列表，光标在提示行', S.screen === 'list' && S.cur === 9, [S.screen, S.cur]);
  press(S, 'EXIT');
  check('提示行上 OK：关闭并保留 08', S.screen === 'closed' && S.applied.i === 7);
}
{ // J. 黑白配方：项目与位置
  const S = fresh(); G.open(S); press(S, 'UP');
  press(S, 'DISP');
  check('黑白配方卡：标题 + 三行两项 + Default + Save = 6 行', JSON.stringify(texts(S)) === JSON.stringify(['<3 HC BW', 'C 0 H 0', 'S 0 F 0', 'G 0 T 0', 'Default', 'Save']), texts(S));
  goRow(S, 3); press(S, 'DISP');
  check('黑白逐项列表：Cont、High、Shad、Fade 与彩色位置相同，之后是 Filt、Tone',
    JSON.stringify(texts(S)) === JSON.stringify(['<3 HC BW', 'Cont   0', 'High   0', 'Shad   0', 'Fade   0', 'Filt   0', 'Tone   0']), texts(S));
  check('两项一行的左边一项 Filt 位于第 5 行', S.cur === 5 && texts(S)[5] === 'Filt   0', [S.cur, texts(S)[S.cur]]);
  press(S, 'EXIT');
}
{ // K. 忙、ERR、断电
  const S = fresh(); G.open(S); press(S, 'DOWN');
  G.setBusy(S, true);
  check('拍照忙：Busy / Retry', S.screen === 'busy' && texts(S).join('|') === 'Busy|Retry', texts(S));
  press(S, 'UP');
  check('忙时上下键不进入列表', S.screen === 'busy');
  G.setBusy(S, false); press(S, 'DOWN');
  check('就绪后回到列表，应用中的行有 >', S.screen === 'list' && texts(S)[S.applied.i].startsWith('>'), [S.screen, texts(S)]);
  G.setErr(S);
  check('ERR 只显示一行 ERR 701', S.screen === 'err' && texts(S).join('|') === 'ERR 701', texts(S));
  press(S, 'DISP'); G.open(S);
  check('锁定期间 DISP 与 ADJ 无效', S.screen === 'err');
  press(S, 'EXIT');
  check('退出后仍锁定，关机再开才清除', S.screen === 'closed' && S.lock === 'ERR 701');
  G.powerCycle(S);
  check('关机再开清除锁定', S.lock === null);
}
{ // L. 开机恢复（可选，默认关）
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DOWN', 'EXIT');
  const last = JSON.parse(JSON.stringify(S.applied));
  G.powerCycle(S); S.restoreOn = true; G.open(S);
  check('开启恢复：第一次打开套用上次配方', S.applied.k === last.k && S.applied.i === last.i);
  press(S, 'EXIT');
  G.powerCycle(S); S.restoreOn = false; G.open(S);
  check('关闭恢复：开机为纯 04', S.applied.i === 3);
}
{ // M. 档位切换（演示）：超出新上限的值夹到新上限；Amount 不变
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][0] = 9; S.live[4][8] = 5;
  G.setRange(S, 7);
  check('切到 ±7：Cont 夹到 +7，Amount 150% 不变', S.live[4][0] === 7 && S.live[4][8] === 5, S.live[4]);
  G.setRange(S, 15);
  check('切到 ±15：紧凑格式两项恒为 8 字符，0 为 "S 00F 00"', texts(S)[2] === 'S 00F 00' && texts(S)[2].length === 8, texts(S));
  G.setRange(S, 9);
  check('切回 ±9', G.getRange() === 9);
  S.live[4][0] = 0; S.live[4][8] = 0;
}

// ---------- 6. 屏幕示意（±9）----------
function dump(title, S) {
  collectLabels(S);
  const rows = G.screenRows(S);
  let top = 0;
  if (rows.length > G.VISIBLE) top = Math.max(0, Math.min(S.cur - G.VISIBLE + 1, rows.length - G.VISIBLE));
  const out = ['[' + title + ']'];
  for (let i = top; i < Math.min(rows.length, top + G.VISIBLE); i++) {
    out.push(' ' + (i === S.cur ? '>' : ' ') + ' |' + (rows[i].t + '        ').slice(0, 8) + '|');
  }
  return out.join('\n');
}
const dumps = [];
{
  const S = fresh(); G.open(S);
  dumps.push(dump('D1 L1 开机：应用中的 04 带 >，光标在它上面', S));
  press(S, 'DOWN');
  dumps.push(dump('D2 L1 光标下移到 05：应用随配方行走（05 带 >）', S));
  goRow(S, G.IDX_HINT);
  dumps.push(dump('D3 L1 光标在提示行：应用不变（沿途最后经过的 08 带 >）', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][0] = 2; S.live[4][1] = -1; S.live[4][4] = -3;
  dumps.push(dump('D4 配方卡 05：调过的配方（标题 *，两项一行）', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][0] = 9; S.live[4][1] = -9; S.live[4][8] = 5;
  dumps.push(dump('D5 配方卡 05：上下限（! 在标签后，紧凑在分隔位）', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP');
  S.live[4][0] = 2; S.live[4][1] = -1; S.live[4][4] = -3;
  press(S, 'DOWN', 'DOWN', 'DOWN', 'DOWN');
  dumps.push(dump('D6 逐项列表 05：光标在 Satu，0 的符号位留空', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP', 'DISP');
  dumps.push(dump('D7 数值页 Cont（19 行）：光标在当前值 0，0 行在窗口底部', S));
  for (let i = 0; i < 12; i++) press(S, 'UP');
  dumps.push(dump('D8 数值页 Cont 到上限 +9：Cont! +9 在窗口顶部', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP', 'DISP');
  for (let i = 0; i < 3; i++) press(S, 'UP');
  dumps.push(dump('D9 数值页 Cont 到 +3：当前值在窗口中，0 行已滚出窗口', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  goRow(S, 6); press(S, 'DISP');
  dumps.push(dump('D10 配方卡：Default 第一次按下，显示 Sure?', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][1] = -2; goRow(S, 7); press(S, 'DISP');
  dumps.push(dump('D11 配方卡：Save 保存为新条目，闪显 Saved', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][1] = -2; goRow(S, 7); press(S, 'DISP'); press(S, 'EXIT');
  G.open(S); goRow(S, G.IDX_MY); press(S, 'DISP'); goRow(S, 5); press(S, 'DISP'); press(S, 'DISP');
  goRow(S, 9);
  dumps.push(dump('D12 我的条目 FCC*001 配方卡：10 行，光标在 Delete', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP');
  S.live[4][1] = -2; goRow(S, 7); press(S, 'DISP'); press(S, 'EXIT');
  G.open(S); goRow(S, G.IDX_MY); press(S, 'DISP');
  goRow(S, 5); press(S, 'DISP');                  // 进入组内条目列表
  press(S, 'DOWN');                               // 光标落到条目上，它成为应用中的配方
  dumps.push(dump('D14 组内条目：应用中的条目带 >', S));
  press(S, 'UP', 'DISP');                         // 第一行 < Back 回到分组
  dumps.push(dump('D13 我的配方分组：应用中的条目所在组带 >', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'UP', 'DISP');
  dumps.push(dump('D15 黑白 03 配方卡：两项一行，G 与 T 为滤镜与色调', S));
  goRow(S, 3); press(S, 'DISP');
  dumps.push(dump('D16 黑白 03 逐项列表', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP', 'DISP', 'DISP');
  press(S, 'DOWN');
  dumps.push(dump('D17 数值页 Cont 在 -1 附近', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); press(S, 'DOWN', 'DISP'); goRow(S, 5); press(S, 'DISP');
  dumps.push(dump('D18 数值页 Amount（16 档，100% 为起点，150% 为上限）', S));
  press(S, 'EXIT');
}
{
  const S = fresh(); G.open(S); G.setBusy(S, true);
  dumps.push(dump('D19 拍照忙：Busy / Retry（光标在 Retry）', S));
  G.setBusy(S, false); G.setErr(S);
  dumps.push(dump('D20 ERR 锁定：一行错误码', S));
}

// ---------- 7. 输出 ----------
console.log('== 检查结果 ==');
console.log('通过 ' + passes + ' 项，失败 ' + fails + ' 项');
console.log('\n== 各类文字的最大宽度（字符数，穷举所得）==');
Object.keys(widths).forEach((k) => console.log('  ' + k.padEnd(28, ' ') + ' ' + widths[k]));
console.log('\n== 标签清单（遍历中实际出现的文字；数值页与逐项列表只列最大宽度）==');
Object.keys(CAT).sort().forEach((cat) => {
  const arr = Array.from(CAT[cat]);
  const mx = Math.max(...arr.map((t) => t.length));
  const isNum = /数值页|逐项列表 各项|Amount 行|配方卡 两项/.test(cat);
  console.log(cat.padEnd(18) + ' 种数 ' + String(arr.length).padStart(4) + '  最长 ' + mx + ' 字符' + (isNum ? '' : '  ：' + arr.map((t) => JSON.stringify(t)).join(' ')));
});
console.log('\n== 逐项数值文字（±9，19 档；Amount 为 16 档）==');
for (const key of STEP.slice(0, 8).concat(['Amt'])) {
  const cells = [];
  const lim = G.keyLim(key, 9);
  for (let n = lim.hi; n >= lim.lo; n--) cells.push(G.valText(key, n));
  console.log(key.padEnd(6) + cells.join(' | '));
}
console.log('\n== 紧凑格式示例（±9）==');
console.log(['C+9 H-9', 'C+9!H-9!', 'C 0 H 0', 'A!150%', 'A 100%'].join('   ') + '   ← 由模型生成如下：');
console.log(G.pairText(G.ITEMS.C, [9, -9, 0, 0, 0, 0, 0, 0, 0], [0, 1]) + '   ' + G.pairText(G.ITEMS.C, [0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1]) + '   ' + G.amtCompact(5) + '   ' + G.amtCompact(0));
console.log('\n== 屏幕示意（> 光标；括号内为相机文字，8 字符）==');
console.log(dumps.join('\n\n'));
process.exitCode = fails ? 1 : 0;
