import { launchPinnedChromium, verifyPinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const pin = verifyPinnedRuntime();
const browser = await launchPinnedChromium({
  args: [
    '--enable-unsafe-webgpu',
    '--enable-unsafe-swiftshader',
    '--use-webgpu-adapter=swiftshader',
    '--single-process',
    '--in-process-gpu',
    '--no-zygote',
  ],
});
try {
  const page = await browser.newPage();
  const done = page.waitForResponse(response => {
    return new URL(response.url()).pathname === '/done' && response.request().method() === 'POST';
  }, { timeout: Number(process.argv[3]) });
  await page.goto(process.argv[2]);
  await done;
  console.log(JSON.stringify({ playwright: pin.playwrightVersion, chromiumRevision: pin.chromiumRevision, browserVersion: browser.version() }));
} finally {
  await browser.close();
}
