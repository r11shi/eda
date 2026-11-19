// usage: node html_to_pdf.js in.html out.pdf "footer text"   (Chromium via Playwright, with page numbers)
const { chromium } = require('playwright');
(async () => {
  const [, , input, output, footer] = process.argv;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + require('path').resolve(input), { waitUntil: 'load' });
  await page.pdf({
    path: output, format: 'A4', printBackground: true, margin: { top: '14mm', bottom: '16mm', left: '13mm', right: '13mm' },
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: `<div style="width:100%;font-size:8.5px;color:#6b7785;padding:0 13mm;display:flex;justify-content:space-between;font-family:Arial"><span>${footer}</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`,
  });
  await browser.close();
})();
