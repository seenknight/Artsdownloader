# GAC Downloader

دانلود تصاویر Google Arts & Culture با بالاترین کیفیت، از طریق یک رابط وب ساده.

**🔗 نسخه‌ی آنلاین:** https://artsdownloader.spooladgar.workers.dev

## طرز استفاده

1. لینک صفحه‌ی یک اثر یا مجموعه را از Google Arts & Culture کپی کنید.
2. آن را در کادر وارد کنید و «دریافت تصاویر» را بزنید.
3. برای هر تصویر «دانلود با اندازه‌ی اصلی» را بزنید. برای صفحه‌ی مجموعه، تیک «همه‌ی تصاویر صفحه» را بزنید و از «دانلود همه» استفاده کنید.

## ساختار

- `public/index.html`: رابط کاربری (فارسی، راست‌چین، سازگار با حالت تاریک)
- `src/worker.js`: سرور (Cloudflare Worker) که صفحه را می‌خواند، آدرس تصاویر را پیدا می‌کند و نسخه‌ی اصلی را دانلود می‌کند
- `wrangler.jsonc`: تنظیمات انتشار

## انتشار

مخزن را در Cloudflare به بخش Workers & Pages → Import a repository وصل کنید. با هر commit، سایت خودکار به‌روز می‌شود. نام پروژه در Cloudflare باید با `name` در `wrangler.jsonc` یکی باشد.

## نکته

فقط لینک‌های `artsandculture.google.com` پذیرفته می‌شوند. لطفاً کپی‌رایت و شرایط استفاده‌ی هر اثر را رعایت کنید.

# GAC Downloader

Download images from Google Arts & Culture in the highest available quality, through a simple web interface.

**🔗 Live version:** https://artsdownloader.spooladgar.workers.dev

## Usage

1. Copy the link to an artwork or collection page on Google Arts & Culture.
2. Paste it into the input box and click "Get images".
3. Click "Download original size" on any image. For collection or story pages, tick "All images on the page" and use "Download all".

## Structure

- `public/index.html`: the user interface (Persian, right-to-left, dark mode supported)
- `src/worker.js`: the server (a Cloudflare Worker) that reads the page, finds the image URLs, and downloads the original versions
- `wrangler.jsonc`: deployment settings

## Deployment

Connect the repository to Cloudflare under Workers & Pages → Import a repository. The site updates automatically on every commit. The project name in Cloudflare must match `name` in `wrangler.jsonc`.

## Notes

Only `artsandculture.google.com` links are accepted. Please respect the copyright and terms of use of each artwork.
