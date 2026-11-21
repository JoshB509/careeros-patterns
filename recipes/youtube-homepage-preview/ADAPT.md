# Adapting the YouTube homepage preview (instructions for an AI)

You are bringing this recipe into someone else's app. Read `src/youtube-preview.js` first; its header lists every option.

## What the recipe needs from the host app

1. **The creator's candidate thumbnails.** One to three image URLs, plus the video's title and the channel name. In CareerOS these are the thumbnails placed in Main, B and C.
2. **Other videos to fill the feed (optional but recommended).** A list of `{image, title, channel, views, published}`. Use real saved data only. Leave `views` or `published` out when they aren't known; the card then hides that part of the line rather than showing a made-up number.
3. **A place to put the cards and a button** that calls `YouTubePreview.openHomepage(...)`.

## Steps

1. Copy `src/youtube-preview.js` and `src/youtube-preview.css` into the app's static files and load them on the page that shows thumbnails. Both are framework-free. In React, Vue or Svelte, call `YouTubePreview.card()` to get HTML or port the markup into a component; the class names and CSS stay the same.
2. Render each candidate with `YouTubePreview.card({ image, title, channel, mine: true })`.
3. Add a "View on homepage" button that calls `YouTubePreview.openHomepage({ candidates, references })`.
4. If the app has its own design system, leave the `.yc` and `.yh` styles alone. They copy the home-feed look on purpose, which is the point of the preview.
5. Check it at desktop and phone widths. The grid goes from three columns to two at 1100px and to one at 760px.

## Rules to keep

- Never present invented performance as real. Example views or durations on the creator's own card are fine when the creator asked for them; for other videos, show only saved data.
- The preview must not call YouTube, upload, or save anything. It is a picture of a feed.
- Escape all text. The recipe does this through `YouTubePreview.esc`; keep it if you change the markup.
- Don't include other creators' real thumbnails in a public demo. Draw placeholders, as `demo.html` does.

## Checking your work

`tests/test_demo.py` shows what to verify: the creator's card sits second in the feed, switching A/B/C changes the image, Shuffle keeps the creator's card in place, missing views stay hidden, and closing removes the preview.
