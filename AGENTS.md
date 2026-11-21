# For AI assistants

This repository is a library of self-contained recipes taken from CareerOS. A person has asked you to bring one of them into their own project.

## How to work with it

1. Read `catalog.json` to find the recipe. Each entry gives its folder, what it does, its entry files and what it needs from the host app.
2. Open that recipe's `README.md` for what it does, then its `ADAPT.md` for the steps. Follow `ADAPT.md` over your own assumptions.
3. Copy only that recipe's `src/` files. Recipes don't depend on each other or on anything else in this repository.
4. Run the recipe's `demo.html` or its test if you need to see the intended behaviour.
5. Keep the rules listed in `ADAPT.md`. They are there because the original app relied on them, for example never presenting invented numbers as real.

## What not to do

- Don't copy demo data into a real product. It is made up.
- Don't add network calls a recipe doesn't already make.
- Don't remove escaping or safety checks to make the code shorter.

## Licence

No licence has been chosen yet, so for now all rights are reserved. Check for a `LICENSE` file before reusing code in a product.
