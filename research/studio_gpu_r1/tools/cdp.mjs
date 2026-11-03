// 极简 Chrome DevTools Protocol 客户端（Node 26 自带 WebSocket，无第三方依赖）。
// 启动真实的 Google Chrome（有窗口、走显卡），用独立的用户目录；结束时用 Browser.close 正常退出。
import { spawn } from 'node:child_process';

export const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

export async function launch({ userDataDir, width = 1280, height = 860, x = 60, y = 60, extra = [], timeoutMs = 30000 }) {
  const args = [
    `--user-data-dir=${userDataDir}`,
    '--remote-debugging-port=0',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-sync',
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-background-timer-throttling',
    '--disable-renderer-backgrounding',
    '--disable-backgrounding-occluded-windows',
    `--window-size=${width},${height}`,
    `--window-position=${x},${y}`,
    ...extra,
    'about:blank',
  ];
  const proc = spawn(CHROME, args, { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let buf = '';
    const timer = setTimeout(() => reject(new Error('Chrome 没有在限时内给出调试地址')), timeoutMs);
    proc.stderr.on('data', (d) => {
      buf += d.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) {
        clearTimeout(timer);
        resolve(m[1]);
      }
    });
    proc.on('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome 退出 ${code}`));
    });
  });
  const cdp = await CDP.connect(wsUrl);
  cdp.proc = proc;
  return cdp;
}

export class CDP {
  static connect(url) {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      const c = new CDP(ws);
      ws.onopen = () => resolve(c);
      ws.onerror = (e) => reject(e);
    });
  }
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.listeners = [];
    ws.onmessage = (ev) => {
      const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : ev.data.toString());
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(`${msg.error.message} ${msg.error.data || ''}`));
        else resolve(msg.result);
      } else if (msg.method) {
        for (const l of this.listeners) l(msg);
      }
    };
  }
  send(method, params = {}, sessionId = undefined) {
    const id = ++this.id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  on(fn) {
    this.listeners.push(fn);
  }
  waitFor(pred, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('等待事件超时')), timeoutMs);
      const l = (msg) => {
        if (pred(msg)) {
          clearTimeout(timer);
          this.listeners = this.listeners.filter((x) => x !== l);
          resolve(msg);
        }
      };
      this.listeners.push(l);
    });
  }
  async page() {
    const { targetInfos } = await this.send('Target.getTargets');
    const t = targetInfos.find((x) => x.type === 'page');
    const { sessionId } = await this.send('Target.attachToTarget', { targetId: t.targetId, flatten: true });
    const p = new Page(this, sessionId, t.targetId);
    await p.send('Page.enable');
    await p.send('Runtime.enable');
    return p;
  }
  async close() {
    try {
      await Promise.race([this.send('Browser.close'), new Promise((r) => setTimeout(r, 5000))]);
    } catch {}
    if (this.proc) {
      await Promise.race([
        new Promise((r) => (this.proc.exitCode !== null ? r() : this.proc.on('exit', r))),
        new Promise((r) => setTimeout(r, 15000)),
      ]);
    }
    try {
      this.ws.close();
    } catch {}
  }
}

export class Page {
  constructor(cdp, sessionId, targetId) {
    this.cdp = cdp;
    this.sessionId = sessionId;
    this.targetId = targetId;
  }
  send(method, params = {}) {
    return this.cdp.send(method, params, this.sessionId);
  }
  async eval(expr, { timeoutMs = 120000 } = {}) {
    const r = await Promise.race([
      this.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }),
      new Promise((_, rej) => setTimeout(() => rej(new Error(`eval 超时: ${expr.slice(0, 80)}`)), timeoutMs)),
    ]);
    if (r.exceptionDetails) throw new Error(`页面异常: ${JSON.stringify(r.exceptionDetails).slice(0, 800)}`);
    return r.result.value;
  }
  async goto(url, timeoutMs = 60000) {
    const loaded = this.cdp.waitFor((m) => m.method === 'Page.loadEventFired' && m.sessionId === this.sessionId, timeoutMs);
    await this.send('Page.navigate', { url });
    await loaded;
  }
  // 真实的鼠标输入（经过浏览器输入管线）
  mouse(type, x, y, buttons = 0, button = 'none') {
    return this.send('Input.dispatchMouseEvent', { type, x, y, button, buttons, clickCount: type === 'mouseMoved' ? 0 : 1 });
  }
  async screenshot(path) {
    const fs = await import('node:fs');
    const { data } = await this.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path, Buffer.from(data, 'base64'));
  }
}

export const pause = (ms) => new Promise((r) => setTimeout(r, ms));

export function stats(xs) {
  const a = [...xs].filter((v) => Number.isFinite(v)).sort((p, q) => p - q);
  if (!a.length) return { n: 0 };
  const q = (p) => a[Math.min(a.length - 1, Math.max(0, Math.round(p * (a.length - 1))))];
  const mean = a.reduce((s, v) => s + v, 0) / a.length;
  return { n: a.length, mean: +mean.toFixed(2), p50: +q(0.5).toFixed(2), p95: +q(0.95).toFixed(2), p99: +q(0.99).toFixed(2), max: +a[a.length - 1].toFixed(2), min: +a[0].toFixed(2) };
}
