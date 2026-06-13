const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto('http://localhost:3000');
    const data = await page.evaluate(() => {
      return localStorage.getItem('raptor-workflow-storage');
    });
    console.log("STORAGE_DATA:", data);
  } catch (err) {
    console.error("Error reading localStorage:", err);
  } finally {
    await browser.close();
  }
})();
