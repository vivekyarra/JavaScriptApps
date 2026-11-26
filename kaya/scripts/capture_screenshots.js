// Captures the deck screenshots into docs/media (API on :8001 with a fresh KNOCKON_DB; needs Playwright).
const { chromium } = require('playwright');
(async () => {
  const out = '/home/user/kaya/docs/media';
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
  await p.goto('http://127.0.0.1:8001/');
  await p.getByText('dev-01-oakridge').click();
  await p.waitForSelector('.answer-badge');
  await p.screenshot({ path: out + '/overview.png' });
  await p.getByRole('tab', { name: /Findings/ }).click();
  await p.waitForSelector('.finding');
  await p.screenshot({ path: out + '/findings.png' });
  await p.getByText('open page 1').first().click();
  await p.waitForSelector('.page-text .hit');
  await p.screenshot({ path: out + '/evidence.png' });
  await p.getByRole('button', { name: 'Close' }).click();
  await p.getByRole('tab', { name: 'History' }).click();
  await p.getByRole('button', { name: /Apply the sample/ }).click();
  await p.waitForSelector('.diff');
  await p.screenshot({ path: out + '/revision.png' });
  await p.getByText('m-02-meridian').click();
  await p.waitForSelector('.answer-badge');
  await p.getByRole('tab', { name: /Findings/ }).click();
  await p.waitForSelector('.finding');
  await p.screenshot({ path: out + '/unreadable.png' });
  await b.close();
})();
