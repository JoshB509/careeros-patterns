# Fonts for the style kit

These are the font files for the four extra pairings in the Styles editor. The House pairing (Outfit and Manrope) is already inside `deck-template.html`.

They came from Fontsource (`@fontsource/<family>@5` on cdn.jsdelivr.net) on 23 October 2026. Each file is the Latin subset of one weight, which covers English. All of them are under the SIL Open Font License, so they can be bundled and used in videos.

`helper/style.py` lists which file each pairing needs. If one goes missing, that pairing shows "not downloaded" in the editor and a build with it stops with a clear message.

| Pairing | Heading | Body |
| --- | --- | --- |
| Editorial | Fraunces 600, 800 | Inter 500, 700 |
| Modern | Space Grotesk 600, 700 | Inter 500, 700 |
| Bold | Anton 400 | Work Sans 500, 700 |
| Friendly | Poppins 600, 800 | Nunito 600, 800 |
