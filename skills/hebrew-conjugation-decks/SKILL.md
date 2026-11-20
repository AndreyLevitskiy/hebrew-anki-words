---
name: hebrew-conjugation-decks
description: Build or rebuild Hebrew verb conjugation decks (Спряжения by binyan) for SmartCards+ from the verbs in hebrew_words.json, with forms from Pealim. Use when the user asks for conjugation cards for a whole binyan, for old verbs, or to re-voice a conjugation deck.
---

# Hebrew Conjugation Decks

Conjugation cards train producing a specific verb form, not the meaning (that is what the regular word cards do). New verbs from a word batch get their conjugation cards automatically in `hebrew-anki-export` (Step 8); this skill is for bulk work: a whole binyan, old verbs, re-voicing.

## Card format

| Field | Content | Example |
|---|---|---|
| Russian (side 1, question) | `<infinitive> — <person>, <tense>` | `לסגור — она, прошедшее` |
| Hebrew (side 2, answer) | the form **without nikud**, as Pealim spells it (plene) — the user types it in Type Answer | `סגרה` |
| Comment | transliteration `\n` form with nikud `\n` Russian meaning (Pealim's, else the infinitive's translation from the base) | `сагра / סָגְרָה / закрывать` |
| Audio | the form with nikud (ElevenLabs, fallback Carmit) | |

3 random forms per verb: one past, one future, one present or imperative. Deck `Hebrew-Russian::Спряжения::<binyan>`. The card id is built from the question, so identical forms (בא = past 3ms = present ms) don't collide.

## Tool

All on the user's Mac (MacOS-MCP Shell), project `/Users/andreilevitskii/Claude/Projects/Hebrew Json`:

```bash
python3 conj_tools/conj_deck.py --binyan פיעל --verbs "לדבר,לבקר" --out conj_פיעל_extra \
        [--force "למדוד=/ru/dict/1025-lamod/"] [--seed 7]
```

- `--binyan`: פעל · פיעל · הפיעל · התפעל · נפעל (Pealim labels ПААЛЬ, ПИЭЛЬ, hИФЪИЛЬ, hИТПАЭЛЬ, НИФЪАЛЬ are mapped inside).
- Writes `<out>.apkg` to the project folder and copies it to the Desktop. Never touches `hebrew_words.json`.
- Internals: `build_conj.py` (finds the verb page on pealim.com/ru, checks infinitive + binyan, takes the forms) and `make_apkg2.py` (audio + apkg via `add_words.build_apkg`).

## Verb list from the base

```python
import json,re
d=json.load(open('hebrew_words.json',encoding='utf-8'))
nik=re.compile('[֑-ׇ]'); cyr=re.compile('[А-Яа-яЁё]')
verbs=[]
for w in d['פיעל מילים']:
    h=re.sub(r'\(.*?\)','',nik.sub('',w['hebrew'])).strip()
    base=h.split()[0].split('/')[0]          # 'לשמור על' -> 'לשמור'
    if base.startswith('ל') and base not in verbs: verbs.append(base)
```

- Skip idioms that are not a plain verb (`לכרוע ברך`, `לחזור לעצמו`, `ללכת לאיבוד`).
- Entries with Cyrillic letters inside (`להכיн`, `להחזיк`) are old typos: map the letters (н→נ/ן, к→ק, д→ד, ф→פ/ף, м→מ, б→ב, в→ב, г→ג) and include them; don't edit the base unless asked.
- Exclude verbs already built (check existing `conj_*.apkg` question lists) to avoid duplicate cards.

## Long runs

Each bridge call times out at ~80 s. For more than ~15 verbs run in the background and poll:

```bash
nohup python3 conj_tools/conj_deck.py ... > /tmp/conj.log 2>&1 &
tail -3 /tmp/conj.log      # in later calls, sleep ≤ 70 s between polls
```

Pealim scraping ≈ 2–3 s per verb; Carmit audio is fast, ElevenLabs ≈ 1.5 s per form. For a job over ~10 minutes, schedule a check-back (send_later) instead of polling.

## Checks before reporting

- `✗` lines: verb not found on Pealim or its binyan differs — usually the verb sits in the wrong section of the base (seen: למשש, להאט in פעל; למרוח, לפרוס in פיעל; לגשת). Report them; offer `--force` with the right page or the right binyan.
- Spelling variants: Pealim may file a verb under another spelling (לתפוס → forms with ש: תפשנו). Convert to the user's spelling before building.
- Literary main forms: some verbs get a bookish form (למדוד → ימוד); keep Pealim's form and mention it.
- Inside each `.apkg`: no duplicate ids, no duplicate questions, every card has `[sound:`.
- Audio fallback: if ElevenLabs quota is gone everything is voiced by Carmit — tell the user.

## Done so far (Nov 2026)

פעל: 150 verbs (conj_פעל, _2, _3) · פיעל 116 · הפיעל 79 · התפעל 54 · נפעל 16 — all voiced; the non-פעל decks and conj_פעל_3 with Carmit.
