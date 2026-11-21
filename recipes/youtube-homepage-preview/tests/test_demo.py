"""Browser test for the YouTube homepage preview demo. Needs Python with Playwright and Google Chrome.

    python -m unittest recipes/youtube-homepage-preview/tests/test_demo.py

It opens demo.html straight from disk. Nothing is fetched from the internet.
"""
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

DEMO = (Path(__file__).resolve().parents[1] / 'demo.html').as_uri()


class HomepagePreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(channel='chrome')
        except Exception:  # noqa: BLE001 - fall back to Playwright's own Chromium if Chrome isn't installed
            cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self, width=1366, height=900):
        ctx = self.browser.new_context(viewport=dict(width=width, height=height))
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        self.errors, self.requests = [], []
        page.on('pageerror', lambda e: self.errors.append(str(e)))
        page.on('request', lambda r: self.requests.append(r.url) if r.url.startswith('http') else None)
        page.goto(DEMO)
        return page

    def test_three_cards_with_badge_title_and_views(self):
        page = self.open()
        cards = page.locator('#three .yc')
        self.assertEqual(cards.count(), 3)
        first = cards.first.inner_text()
        for part in ('One Conversation That Changed My Career', 'Demo Creator', '123K views • 3 days ago', '12:38'):
            self.assertIn(part, first)
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.yc-title')).fontWeight"), '600')

    def test_homepage_puts_the_creator_in_the_first_row(self):
        page = self.open()
        page.click('#go')
        page.wait_for_selector('dialog.yh .yh-card')
        cards = page.locator('dialog.yh .yh-card')
        self.assertEqual(cards.count(), 12)
        self.assertIn('mine', cards.nth(1).get_attribute('class'))
        self.assertEqual(page.locator('dialog.yh .yh-card.mine').count(), 1)
        src = lambda: page.evaluate("document.querySelector('dialog.yh .yh-card.mine img').src")  # noqa: E731
        a = src()
        page.click('[data-yh-rank="1"]')
        self.assertNotEqual(src(), a, 'B shows a different image')
        page.click('[data-yh-shuffle]')
        self.assertIn('mine', page.locator('dialog.yh .yh-card').nth(1).get_attribute('class'), 'shuffle keeps your card in place')
        page.click('[data-yh-close]')
        page.wait_for_function("!document.querySelector('dialog.yh')")
        self.assertEqual(self.errors, [])
        self.assertEqual(self.requests, [], 'nothing is fetched from the internet')

    def test_unknown_views_stay_hidden(self):
        page = self.open()
        page.click('#go')
        page.wait_for_selector('dialog.yh .yh-card')
        lines = page.evaluate("[...document.querySelectorAll('dialog.yh .yh-card:not(.mine) .yc-text')].map(t=>t.innerText)")
        self.assertTrue(any('views' not in l for l in lines), 'a video with no saved views shows no views')
        self.assertFalse(any('undefined' in l or 'NaN' in l or 'null' in l for l in lines))

    def test_phone_is_one_column_without_sideways_scroll(self):
        page = self.open(390, 844)
        page.click('#go')
        page.wait_for_selector('dialog.yh .yh-card')
        cols = page.evaluate("getComputedStyle(document.querySelector('.yh-grid')).gridTemplateColumns.split(' ').length")
        self.assertEqual(cols, 1)
        self.assertLessEqual(page.evaluate('document.querySelector("dialog.yh").scrollWidth'), 390)


if __name__ == '__main__':
    unittest.main()
