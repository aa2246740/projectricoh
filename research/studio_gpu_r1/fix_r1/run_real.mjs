// 用本机 Chrome（CDP）打开隔离工作室，跑 14 组真实输入，读回像素交给 session.py 的接收器。
// 用法：node run_real.mjs <metal|swiftshader> <Chrome 用户目录>
import { readFileSync, writeFileSync } from 'node:fs';
import { launch } from '../tools/cdp.mjs';
const [mode, userDataDir] = process.argv.slice(2);
const temp = '/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r1/real/';
const cases = JSON.parse(readFileSync(temp + 'real-cases.json', 'utf8'));
const extra = ['--enable-unsafe-webgpu'];
if (mode === 'swiftshader') extra.push('--headless=new', '--enable-unsafe-swiftshader', '--use-webgpu-adapter=swiftshader');
const cdp = await launch({ userDataDir, width: 1000, height: 700, extra });
try {
  const page = await cdp.page();
  await page.goto('http://127.0.0.1:49751/?token=fix-r1-local-only');
  await page.eval(`window.__fixCases = ${JSON.stringify(cases)}; window.__fixMode = ${JSON.stringify(mode)}; true`);
  const result = await page.eval(readFileSync(new URL('route_cases.js', import.meta.url), 'utf8'), { timeoutMs: 900000 });
  const receipt = { mode, adapters: [...new Set(result.map((r) => r.adapter && `${r.adapter.vendor}/${r.adapter.architecture}`))], result };
  writeFileSync(new URL(`real-route-${mode}.json`, import.meta.url), JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify(receipt.adapters), result.map((r) => `${r.id}:${r.way}`).join(' '));
} finally {
  await cdp.close?.();
  try { cdp.proc.kill('SIGTERM'); } catch {}
}
process.exit(0); // CDP 的 WebSocket 不会自己让 node 退出
