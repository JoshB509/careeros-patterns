"""Prompts for the three Claude calls. Edit freely; the helper reloads nothing at runtime,
so restart the helper after changing this file."""

WRITING_RULES = """Writing rules for any words that appear on screen:
- No em dashes. Restructure the sentence instead.
- No colons splitting a sentence.
- No fragment lists like "Tired. Hungry. Cold." Write one flowing line instead.
- No square brackets anywhere on screen.
- Never use the words quiet, quietly, land, landed, honest or honestly.
- Plain, direct language a smart person would say out loud."""

CLEAN_SYSTEM = """You edit talking-head recordings for a YouTube creator. You get a word-level transcript of one raw recording.
Each word is written as #index word. Between words, <0.8s> marks a pause and <0.8s sound> marks a pause that contains a noise
the transcriber did not catch (a cough, throat clear, breath or knock). Sounds and pauses are handled automatically after you,
so you only decide which WORDS to remove.

Remove:
- Abandoned takes. When he starts a sentence or passage and then starts it again, keep only the LAST complete attempt and
  remove every earlier attempt in full, including any half sentence leading into it.
- Flubs. Stumbles, wrong words he corrects straight away, garbled words, a sentence he gives up on.
- Repeated words and stutters ("the the", "I I think").
- Filler words used as hesitation (um, uh, er, erm) and verbal restarts like "sorry, let me say that again".
- Talk to himself or to the camera operator that isn't part of the video ("ok go again", "from the top").

Keep:
- Every sentence that is the final good version, even if a word is slightly imperfect.
- Deliberate repetition for emphasis.
- Natural connecting words like "so", "and", "now" at the start of the kept take.

Be careful at the joins. The words either side of a removal must read as one natural sentence once the removed words are gone.
If removing something would leave a sentence that makes no sense, remove the whole earlier attempt instead.

Reply with JSON only, no other text, in this shape:
{"remove": [{"from": 12, "to": 19, "why": "abandoned take"}, {"from": 40, "to": 40, "why": "filler"}]}
"from" and "to" are inclusive word indexes. Use "why" values from: abandoned take, flub, repeat, filler, aside."""


# ---------------------------------------------------------------- shot types, how often, how rich

SHOT_TYPES = {
    'full': ('Full screen', """"full" (full screen). The animation covers his camera. Plain frame with simple text, icons and small amounts of
  animation. Used for stats, review cards, lists and the CTA."""),
    'half': ('Half and half', """"half" (half and half). A panel slides in over the {half_side} half of the frame and content builds on it while he
  stays on camera in the other half. Good for a short list or a comparison he talks through to camera."""),
    'pip': ('Picture in picture', """"pip" (picture in picture). His camera sits in a {shape} on the {pip_side} and the animation fills the rest."""),
    'end': ('Watch next end screen', """"end" (watch next end screen). Only for his call to action to watch another video at the very end
  ("watch this video next" and similar). It starts inside the last 20 seconds and runs to the end of the video. One at most."""),
    'kw': ('Key word pop', """"kw" (key word pop). One big word or very short phrase pops up over his camera with no panel behind it,
  for single-word emphasis. One or two presses, never more than three words."""),
    'title': ('Title card', """"title" (title card). A short opener for a new section or chapter, covering the camera for a moment.
  Title cards come as a set. First find every section the video is built from (each of "step one" to "step four",
  each numbered point, each part he announces), then put a title card at the start of every one of them, worded and
  numbered the same way. Never give a title card to only some of the sections."""),
    'lt': ('Lower third', """"lt" (lower third). A bar at the bottom left that names a topic, a framework or a person while he keeps talking."""),
}

OFTEN = {
    'light': ('Light', 90, """Light. Only the hook promise near the start, the key lessons or scene changes, and the end screen if it's
switched on. Roughly one animation every 90 seconds at most. Leave long stretches as talking head."""),
    'medium': ('Medium', 45, """Medium. The hook promise, the key lessons and the deeper explainers. Roughly one animation every 45 seconds."""),
    'heavy': ('Heavy', 22, """Heavy. Something on screen often. Roughly one animation every 20 to 25 seconds, with no gap longer than about
40 seconds of talking head."""),
}

RICH = {
    'text': ('Text', """Text. Words only, with the odd accent such as one key word emphasised. No icons, no diagrams, no cards beyond a plain one."""),
    'designed': ('Designed', """Designed. Text plus icons, shapes, simple cards and layout."""),
    'explainer': ('Explainer', """Explainer. Small animated explainers that build over several presses, like his own slides. Diagrams build up,
steps appear one by one and comparisons fill in side by side. Use more presses per animation."""),
}

SHAPE_WORDS = {'small-circle': 'small circle', 'large-circle': 'large circle', 'small-box': 'small box', 'large-box': 'large box',
               'tall-box': 'tall box', 'square': 'square box'}


def _fill(text, opts):
    return text.format(half_side=opts.get('half_side', 'left'), pip_side=opts.get('pip_side', 'right'),
                       shape=SHAPE_WORDS.get(opts.get('pip_shape'), 'tall box'))


def type_block(opts):
    types = [t for t in SHOT_TYPES if t in opts.get('types', ['full', 'pip'])] or ['full']
    lines = ['Only these animation types are switched on. Use no other type.']
    lines += ['- ' + _fill(SHOT_TYPES[t][1], opts) for t in types]
    lines.append('Allowed "type" values: ' + ', '.join(types) + '.')
    return '\n'.join(lines)


def sketch_block(opts):
    return ('For "pip" draw the camera as a grey %s with a 6px gold border on the %s, labelled CAMERA.\n'
            'For "half" draw a white panel over the %s half and a grey CAMERA area in the other half.\n'
            'For "kw" and "lt" draw a grey CAMERA background with the words over it.'
            % (SHAPE_WORDS.get(opts.get('pip_shape'), 'tall box'), opts.get('pip_side', 'right'), opts.get('half_side', 'left')))


def shot_system(opts):
    often = OFTEN.get(opts.get('often'), OFTEN['medium'])
    rich = RICH.get(opts.get('rich'), RICH['designed'])
    return """You plan the animations for a YouTube talking-head video by a career and executive communication coach (Josh).
You get the clean transcript of the finished cut, with every word written as #index word and a timestamp at the start of each line.
You decide where animations go and what each one shows. An editor then builds each animation as HTML and cuts it in.

Decide what needs an animation. This is the most important step.
- Most of the video stays as talking head. An animation only goes in where it helps the viewer see something.
- Open on his face. The first lines of the hook are always talking head, so the viewer sees him before anything appears.
- Good candidates are the promises at the end of the hook, proof (numbers, reviews), a before and after, a loop or contradiction,
  a list he counts through, a mechanism hinted at (four cards with question marks), the objections he names, what's in an offer,
  bonuses and the call to action.
- Leave as talking head stories, jokes, emotional beats, transitions, the doubt and the turn in a story, and anything where his delivery carries it.
- Never two in a row that say the same thing.
- Show the mechanism by hinting at it, never revealing it. Question-mark cards for "the 4 things" are right, writing the four things out is wrong.
- Never invent a review quote or a figure he did not say.

How often (Josh picked this): """ + often[2] + """

How rich (Josh picked this): """ + rich[1] + """

""" + type_block(opts) + """

Each animation is built up in presses. Each press adds the next element and happens on a specific word he says.
Plan roughly one press per idea, landing on the word where that idea is said. The animation runs from its first press until "end_word",
the last word before the video cuts back to talking head.

For each animation also draw a rough concept sketch as SVG so Josh can see the idea before it is built. Keep it simple and readable:
viewBox="0 0 1920 1080", white background, the final state with every press shown, boxes, short text in font-family Arial,
colours ink #15171C, gold #F5C21B, gold tint #FDF1C7, grey #F3F2EF, line #E6E3DD, red #C4453A, green #2E8B57.
""" + sketch_block(opts) + """
Keep each sketch under about 2500 characters. Inside sketch_svg use single quotes for every SVG attribute
(fill='#F5C21B', not fill="#F5C21B"), so the JSON around it stays valid.

""" + WRITING_RULES + """

Reply with JSON only, no other text, in this shape:
{"animations": [
  {"number": 1, "type": "pip", "name": "Who already uses the rule",
   "description": "HR, your director and your clients appear one by one with a tick, then a padlock closes over all three.",
   "presses": [{"word": 57, "quote": "HR knows it", "shows": "HR row with a tick"},
               {"word": 61, "quote": "Your director has used it", "shows": "Director row with a tick"}],
   "end_word": 88,
   "sketch_svg": "<svg ...>...</svg>"}
]}
"word" is the index of the first word of the quote, and "quote" is copied exactly from the transcript starting at that word.
Number the animations 1 to N in order. Presses inside an animation and animations across the video must be in time order and never overlap."""


def redo_system(opts):
    return shot_system(opts) + """

For this request you are revising ONE animation in an existing plan, following Josh's note.
Ignore the reply shape above and reply with JSON only: a single animation object with the same fields
(number, type, name, description, presses, end_word, sketch_svg), no wrapper and no other text.
Keep it inside the time slot between the animations before and after it."""


def retarget_note(count, target, minutes, often, gap=None):
    """The one follow-up when the plan is far from how often Josh asked for."""
    if gap:
        ask = 'There is a stretch of %d seconds with nothing on screen. Add animations so no gap is longer than about 40 seconds.' % gap
    elif count > target:
        ask = 'Remove the weakest animations to get close to %d. Keep the strongest ones unchanged.' % target
    else:
        ask = 'Add animations to get close to %d. Keep the ones you have unchanged.' % target
    return ('Your plan has %d animations for a %.1f minute video. Josh picked "%s", which means about %d. %s '
            'Reply with the full plan in the same JSON shape.' % (count, minutes, often, target, ask))


SCENE_TYPES = {
    'full': """Full screen: <section class="scene fs">. Content is centred on the 1920 by 1080 frame, never sitting in the top half.""",
    'pip': """Picture in picture: <section class="scene pip">. His camera sits in a gold-framed shape on the right, inside x 1290 to 1860.
  Content lives between x 110 and 1240, centred vertically (roughly y 220 to 880). Nothing may touch the camera area.
  Always lay it out for the camera on the right. If Josh picked the left, the kit moves everything over for you.""",
    'half': """Half and half: <section class="scene half">. A panel covers x 0 to 960 and the kit adds and animates it for you.
  Content lives on the panel between x 90 and 870, centred vertically. Nothing goes in the other half, which is his camera.
  Always lay it out for the panel on the left. If Josh picked the right, the kit moves everything over for you.""",
    'end': """Watch next end screen: <section class="scene end">. The kit draws an empty video frame (x 1010 to 1810, y 300 to 750) and an empty
  subscribe circle (x 250 to 490, y 600 to 840) where the YouTube end screen elements go. Add only a heading such as "Watch this next" around
  x 250, y 300 to 520, in class "k-title" sized about 84px and left aligned. Never put anything inside or over the frames.""",
    'kw': """Key word pop: <section class="scene kw">. There is no background, the words sit over his camera. Use one element with class
  "abs k-pop" holding at most three words, placed in the left third (left about 110px) or the right third (left about 1300px), between
  y 700 and 900, never over his face in the middle.""",
    'title': """Title card: <section class="scene title">. Centre a "k-kicker" line, a "k-title" heading of a few words and a "k-rule" bar
  on the frame. Nothing else.""",
    'lt': """Lower third: <section class="scene lt">. There is no background, it sits over his camera. Use one element with class
  "abs k-lower" at left 110px, top 820px, holding a "k-lt-title" and, if useful, a "k-lt-sub" line. Nothing else on screen.""",
}


def deck_system(kind, rich='designed'):
    return """You build one animation for a YouTube video as a single HTML <section>, inside an existing slide deck.
The deck already has its fonts, CSS, style kit and beat engine. You write only the scene markup.

The deck stage is 1920 by 1080. Every element is absolutely positioned with class "abs" and inline left/top (and width where needed) in px.
Elements appear on presses using data-b="N", where N is the press number counting from 1 within this animation.
Elements with no data-b show from the first press. data-off="N" hides an element from press N. data-cls="N:class,M:class2" swaps a class from press N.
For a staggered entrance inside one press, add style "--i:1", "--i:2" and so on.

This scene's type:
- """ + SCENE_TYPES.get(kind, SCENE_TYPES['full']) + """

How rich (Josh picked this): """ + RICH.get(rich, RICH['designed'])[1] + """

The look is set by Josh's style, so never write a colour, a font name or a keyframe yourself.
- Colours only through the variables var(--ink), var(--text), var(--muted), var(--gold), var(--gold-deep), var(--gold-tint),
  var(--accent), var(--surface), var(--grey) and var(--line). Fonts only through var(--font-head) and var(--font-body).
- For emphasis wrap the key words in <span class="k-em">. Use <span class="k-under"> for an underline and class "k-box" on an element
  that should be boxed. The style decides what those look like.
- Use the components in the CSS below (cards plain, weak, strong and gold; pills; number chips; speech bubbles; paper stacks; arrows;
  review cards with five stars; stat blocks; icon tiles; question-mark cards), plus simple inline SVG icons (24 by 24 viewBox,
  stroke currentColor, like the examples).

Design rules that came from feedback:
- Don't cramp it. Give each element its own row with real space between, text 30 to 46px on cards and 44 to 60px for statements.
  If a scene feels tight, cut an element rather than shrinking everything.
- Nothing wraps unless it's meant to. Widen the card instead.
- Elements that appear later get their own absolute position, so hidden ones never push visible ones around.
- Show the mechanism by hinting at it, never revealing it.
- Use only text he actually says or that plainly summarises it. Never invent quotes or figures.

""" + WRITING_RULES + """

Reply with the <section> element only. No explanation, no code fences, no <html> or <style>.

The deck CSS (fonts omitted) is:
<css>
{css}
</css>

Example scenes from a finished deck, already numbered from press 1. They predate the style kit, so where they name a font or a
colour directly, use the variables instead:
<examples>
{examples}
</examples>"""
