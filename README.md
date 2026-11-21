# CareerOS patterns

Pieces of CareerOS, a creator's studio app built with Claude, pulled out so anyone can see how they work and copy them. Each recipe is its own folder with a working demo, the code, and instructions an AI can follow to bring it into another app.

**Using an AI?** Point it at [`AGENTS.md`](AGENTS.md) and tell it which recipe you want.

## Recipes

| Recipe | What it does | Try it |
|---|---|---|
| [YouTube homepage preview](recipes/youtube-homepage-preview/) | Shows a thumbnail as a home-feed card, then inside a full home feed among other videos, so you can judge how it stands out. | [`demo.html`](recipes/youtube-homepage-preview/demo.html) |

## Pathways

A pathway is a whole workflow copied as it runs, with a guide that walks through it. Paths, brand and settings are left as they are on the original PC.

| Pathway | What it covers |
|---|---|
| [Video editing](pathways/video-editing/) | Script to animation deck, transcription, silence and flub cuts, cutting a Premiere sequence in place, rendering animations and placing them on the timeline. |

## Skills

| Skill | What it does |
|---|---|
| [Video editing prep](skills/video-editing-prep/SKILL.md) | Turns a finished script into an HTML animation deck and a script and shot list. |

More are on the way: the thumbnail workspace, a load guard that recovers failed stylesheets, approval-bound sending (one click sends exactly the version you read), "publish what you see", the team-agent setup, and the Claude skills used to write scripts, lessons and guides.

## How a recipe is laid out

```
recipes/<name>/
  README.md     what it does, a screenshot, how it was built
  demo.html     opens in a browser with made-up data
  src/          the code, with no dependency on CareerOS
  ADAPT.md      step-by-step instructions for an AI fitting it into another app
  tests/        a browser test of the demo
```

## Ground rules

- Demos use made-up data only. No real customer data, no other creators' images, no keys.
- Nothing in a recipe contacts a real service unless its README says so plainly.
- Every recipe runs on its own. If it needs CareerOS to work, it isn't finished.
- Pathways are the exception. They show a real workflow as it is, so expect hard-coded paths.

Not affiliated with or endorsed by YouTube or Google.
