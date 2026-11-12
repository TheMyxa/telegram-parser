// Uses an installed browser; playwright-core is a temporary documentation tool.
const { chromium } = require(process.env.TG_PLAYWRIGHT_MODULE || 'playwright-core');
const path = require('node:path');

(async () => {
  const baseUrl = process.env.TG_DOCS_URL || 'http://127.0.0.1:19596';
  const preview = await fetch(new URL('/api/docs-preview', baseUrl));
  if (!preview.ok || (await preview.json()).synthetic_preview !== true) {
    throw new Error('Refusing to capture a server without the synthetic documentation preview marker.');
  }
  const browser = await chromium.launch({
    executablePath: process.env.TG_BROWSER_PATH,
    headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1, locale: 'en-US', timezoneId: 'UTC' });
    await page.addInitScript(() => {
      localStorage.setItem('tg-dashboard-language', 'en');
      localStorage.setItem('tg-dashboard-theme', 'light');
    });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    await page.locator('#localExportSelect option[value="demo_dataset.json"]').waitFor({ state: 'attached' });
    await page.selectOption('#localExportSelect', 'demo_dataset.json');
    await page.click('#openLocalExport');
    await page.waitForFunction(() => document.querySelector('#metricPosts').textContent.trim() === '3');
    await page.evaluate(() => document.fonts.ready);
    const output = path.join(__dirname, 'screenshots');
    await page.screenshot({ path: path.join(output, 'dashboard.png'), fullPage: true, animations: 'disabled' });
    await page.click('[data-tab="posts"]');
    await page.locator('#postsBody .post-title').first().click();
    await page.locator('.post-full-text').waitFor();
    await page.screenshot({ path: path.join(output, 'posts.png'), fullPage: true, animations: 'disabled' });
    await page.click('[data-tab="globalSearch"]');
    await page.fill('#globalSearchQuery', 'export');
    await page.click('#runGlobalSearch');
    await page.locator('#globalSearchBody tr td:nth-child(5)').first().waitFor();
    await page.screenshot({ path: path.join(output, 'search.png'), fullPage: true, animations: 'disabled' });
    await page.click('[data-tab="export"]');
    await page.screenshot({ path: path.join(output, 'export.png'), fullPage: true, animations: 'disabled' });
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Captured dashboard, posts, search and export from synthetic demo data.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
