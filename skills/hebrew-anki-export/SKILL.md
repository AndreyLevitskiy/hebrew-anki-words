---
name: hebrew-anki-export
description: Add Hebrew words to hebrew_words.json and generate Anki .apkg files with audio, transliteration and usage examples (plus conjugation cards for new verbs). Triggered when user sends a list of Hebrew words to add to their vocabulary.
---

# Hebrew Anki Export Skill

Triggered when the user sends a list of Hebrew words (from their teacher or textbook) and wants to:
- Add words to `hebrew_words.json`
- Get `.apkg` files ready to import into SmartCards+ (one file per grammatical group)
- For new verbs: also get conjugation cards (see Step 8)

Before parsing, check project memory for words the user asked to hold "for the next batch" and add them to this batch.

---

## How the card looks in SmartCards+ (verified on a screen recording, Nov 2026)

The user reviews **Russian → Hebrew** and types the answer (Type Answer):
- **Side 1:** the Russian translation (sometimes a picture).
- **Side 2:** the Hebrew field, the comment block (transliteration, Hebrew example, its Russian translation) and **one** audio player.

SmartCards+ does NOT use the Anki HTML template: it strips HTML (`<br>` shows nothing, lines glue together), so line breaks in fields are plain `\n`. There is only one player per card — that is why the example sentence is voiced instead of the word (Step 6).

---

## Input format

The teacher sends words in free-form text. Each line is one entry:

```
בינוני / בינונית = СРЕДНИЙ
להתרכז (ב...) – התרכז – מתרכז – יתרכז = СОСРЕДОТОЧИВАТЬСЯ
נקודת מבט (רבים: נקודות מבט) [נקבה] = ТОЧКА ЗРЕНИЯ
להגיש – הגיש – מגיש – יגיש = ПОДАВАТЬ (אוכל, משקאות), СДАВАТЬ (מסמכים)
```

Multi-line verbs (`להתעצם = …` + next line `התעצם – מתעצם – יתעצם`) are supported too.

---

## Step 1 — Parse each line

- **Hebrew main form:** the first Hebrew word/phrase before `=`, `–`, `(`, `[`.
- **Strip:** `(רבים: ...)`, `[זכר]`, `[נקבה]`, `(ביטוי)`.
- **Masc/fem pairs: keep both forms**, never narrow to masculine: card field `רווק / רווקה`, nikud `רַוָּק / רַוָּקָה`, Russian both genders where it differs.
- **Verbs:** take the infinitive (starts with `ל`); conjugations = past – present – future without the infinitive, without nikud.
- **Verb prepositions** like `(ב...)`, `(על...)`, `(מ...)` go to `"governs"` — they are shown on the Hebrew side next to the infinitive, never in the Russian translation.

**Russian translation — ONLY Russian.** It is the question side: any Hebrew there gives away the answer.
- Convert ALL CAPS to normal case.
- Hebrew collocations the teacher puts in brackets (`(אוכל, משקאות)`, `(למשל: מחיר סביר)`, `(בסלנג)`) → translate the note to Russian (`(еду, напитки)`, `(сленг)`) or move the Hebrew collocation into the example. Never leave Hebrew letters in `russian`, never transliterate Hebrew into Cyrillic there.

---

## Step 2 — Section (binyan)

| Section key | Rule (by the past tense, 3rd m. sg.) |
|---|---|
| `מילים` | not a verb (nouns, adjectives, adverbs, prepositions, expressions like `להיות סגור על משהו`) |
| `פעל מילים` | no prefix, no doubling (כתב, למד) |
| `פיעל מילים` | doubled middle / 4 letters (דיבר, ביקר, שילשל) |
| `הפיעל מילים` | starts with `ה` (not `הת`) — הכין, הגיש |
| `התפעל מילים` | starts with `הת` — התרכז, התנתק |
| `נפעל מילים` | starts with `נ` — נכנס, נקלע |

**Check the root, not just the letters.** `להתמיד` (התמיד) is **הפעיל**: ת is a root letter (ת-מ-ד), not the הת prefix. Same trap: הִתְחִיל. When unsure, check the verb on [Pealim](https://www.pealim.com/ru/).

---

## Step 3 — Nikud and example

Words arrive without nikud. For every word give:
- `"hebrew"` — clean form exactly as on the card (never derive it by stripping nikud: letters like ו get lost).
- `"hebrew_nikud"` — with nikud, for transliteration (and audio when there is no example).
- `"example"` — a Hebrew sentence **without nikud**; prefer a real idiom / set phrase (על סדר היום, מכוח ההרגל, על מגש של כסף) over a neutral sentence.
- `"example_ru"` — its Russian translation.
- `"example_nikud"` — the same sentence **with nikud**: this is what gets voiced.

Prefer example sentences built from words the user already has in the base.

---

## Step 4 — Duplicates (search by substring, not exact key)

Older entries have composite keys (`אוזניה, אוזניות`, `רואה חשבון, רואת חשבון`) and some contain Cyrillic letters, so exact matching misses them. For each word search **all sections** for the nikud-stripped word and its root-related forms as substrings:

```python
import json,re
d=json.load(open('hebrew_words.json',encoding='utf-8'))
nik=re.compile('[֑-ׇ]')
hits=[(w['hebrew'],w['russian'],s) for s,ws in d.items() for w in ws if 'סביר' in nik.sub('',w['hebrew'])]
```

Then judge: real duplicate → **skip without asking** (standing instruction) and list it; letter-coincidence (`להסביר` for `סביר`) → not a duplicate. A present-tense form already stored as a word (ממהר) does not block adding the infinitive — mention it.

Homographs (two meanings, same letters): use the **nikud form as the key** (`מְגֻוָּן` / `מִגְוָן`), never `²` markers.

---

## Step 5 — Show the table and WAIT for approval

| # | Иврит (карточка) | Секция | Никуд | Транслит | Перевод | Пример |
|---|---|---|---|---|---|---|

- Verb card field: `להקפיד (על...)<br><br>הקפיד – מקפיד – יקפיד`.
- Example cell: Hebrew sentence (set phrase in bold) + `<br>` + *Russian translation*.
- Below the table: skipped duplicates, binyan traps, homographs, translations you supplied yourself (when the teacher gave none — say so).

Then **stop**. Approval = a clear go-ahead («да», «ок», «генерируй», «делай файлы»).
A correction → fix, show the table again, wait. A question or a side request (e.g. "make a spreadsheet of it") is **not** approval and **not** a cancellation: do the side request, then ask whether to generate the cards.

---

## Step 6 — Run add_words.py on the Mac

Runs on the user's Mac through the MacOS-MCP Shell tool (`mcp__remote-devices__MacOS-MCP__Shell`; the bridge call times out at ~80 s, use background + polling for long jobs). If the Mac is not reachable, say so; do not run from the sandbox (ElevenLabs is not reachable there).

```bash
cd "/Users/andreilevitskii/Claude/Projects/Hebrew Json"
cat > /tmp/batch.json << 'JSON'
[ ...entries... ]
JSON
python3 add_words.py --words-file /tmp/batch.json
cp hebrew_words.json ~/Desktop/
```

Entry format:
```json
{"hebrew": "להקפיד", "governs": "(על...)", "hebrew_nikud": "לְהַקְפִּיד",
 "russian": "Строго соблюдать, быть принципиальным",
 "section": "הפיעל מילים", "conjugations": "הקפיד – מקפיד – יקפיד",
 "example": "היא מקפידה על כל פרט", "example_ru": "Она строго следит за каждой мелочью",
 "example_nikud": "הִיא מַקְפִּידָה עַל כָּל פְּרָט"}
```

What the script does:
- Hebrew field: `infinitive [governs]\n\nconjugations` for verbs, the word for the rest.
- Comment field: `transliteration\nexample\nexample_ru` (plain `\n`, no HTML).
- **Audio = the example sentence** (`example_nikud`); no `example_nikud` → the word (`hebrew_nikud`).
- Saves `hebrew_words.json` (with `example`, `example_ru`, `example_nikud`, `governs`) and publishes it to GitHub (`publish_to_github()`).
- One `new_words_<section>.apkg` per section in the project folder. Files are **overwritten** on every run — the user must import before the next batch.
- Media inside `.apkg` use ASCII names (`0.mp3`…) — never revert to Hebrew file names (SmartCards+ then plays nothing).

---

## Step 7 — Audio: ElevenLabs with Carmit fallback

Primary: ElevenLabs — voice **Jessica** (`cgSgspJ2msm6clMCkdW9`), model `eleven_v3`, `language_code: "he"`, stability `1.0`, similarity `0.75` + speaker boost, text prefixed with `[spoken in Hebrew] ` (a direction, not read aloud), `mp3_44100_128`. Key: `~/.config/hebrew-json/elevenlabs_key` (never bundle it).

Fallback: if ElevenLabs fails (quota — the API key "Hebrew Card with Claude" is capped at 10 000 credits —, auth, network), the script switches to macOS **`say -v "Carmit (Enhanced)"`** + ffmpeg → mp3 for the rest of the run and prints `⚠ Озвучено запасным голосом Carmit (N): …`. Always tell the user which words got the fallback voice; they can be re-voiced with Jessica after the quota resets.

---

## Step 8 — Conjugation cards for new verbs

If the batch had verbs, after Step 6 build their conjugation cards (3 random forms each: past, future, present/imperative) into `Спряжения::<binyan>`:

```bash
cd "/Users/andreilevitskii/Claude/Projects/Hebrew Json"
python3 conj_tools/conj_deck.py --binyan הפיעל --verbs "להקפיד,להגיש" --out conj_הפיעל_$(date +%F)
```

One call per binyan. Output `conj_<binyan>_<date>.apkg` in the project folder + a copy on the Desktop. Forms come from Pealim; verbs Pealim can't find (or whose binyan differs) are listed with `✗` — report them. Details and pitfalls: skill `hebrew-conjugation-decks`.

---

## Step 9 — Report

- Words added per section, `.apkg` files (project folder), conjugation file if any.
- Skipped duplicates.
- Audio: any `✗` or fallback-voice words.
- Transliteration mistakes worth flagging (see below).
- JSON copied to the Desktop, base published to GitHub.

---

## Transliteration notes

`transliterate()` builds Cyrillic reading from nikud. Fixed: patah gnuva (`руах`), vav with dagesh as consonant (`мегуван`), final yod (`насуй`), word starts after space/slash (`лалехет леибуд`), yod + shuruk (`сиюм`), yod after tsere (`бейт`), `-ִיָּה` (`сифрия`).
Still imperfect: `йа` not merged into `я` (`пенуйа`, `hатайа`, `цалйан`), word-initial shva always `е` (`севира`), shva before final kaf (`ацмха`). Audio is the reliable reference.

---

## GitHub

`hebrew_words.json` is pushed automatically by the script to https://github.com/AndreyLevitskiy/hebrew-anki-words (the `hebrew-dialogue` skill reads it from there). Script changes (`add_words.py` in the root **and** `skills/hebrew-anki-export/scripts/add_words.py`, `conj_tools/`) are committed and pushed **only on the user's explicit instruction**. If `git` fails with an Xcode license message, the user must run `sudo xcodebuild -license accept`.
