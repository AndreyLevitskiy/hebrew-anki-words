---
name: hebrew-anki-export
description: Add Hebrew words to hebrew_words.json and generate Anki .apkg files with audio and transliteration. Triggered when user sends a list of Hebrew words to add to their vocabulary.
---

# Hebrew Anki Export Skill

Triggered when the user sends a list of Hebrew words (from their teacher or textbook) and wants to:
- Add words to `hebrew_words.json`
- Get `.apkg` files ready to import into SmartCards+ (one file per grammatical group)

---

## Input format

The user's teacher sends words in free-form text. Each line is one word entry. Common patterns:

```
בינוני / בינונית = СРЕДНИЙ
להתרכז (ב...) – התרכז – מתרכז – יתרכז = СОСРЕДОТОЧИВАТЬСЯ
נקודת מבט (רבים: נקודות מבט) [נקבה] = ТОЧКА ЗРЕНИЯ
טיעון [זכר] = АРГУМЕНТ
נגד = ПРОТИВ
```

Multi-line format is also supported:
```
להתעצם = УСИЛИВАТЬСЯ
התעצם – מתעצם – יתעצם
```

Verbs may also arrive with all 4 forms on one line:
```
לזייף – זייף – מזייף – יזייף = ПОДДЕЛЫВАТЬ
```

---

## Step 1 — Parse each line

Extract from each line:
- **Hebrew main form**: the first Hebrew word/phrase before any `=`, `–`, `(`, `/`, `[`
- **Russian translation**: everything after `=`, convert from ALL CAPS to normal case; strip parenthetical notes
- **Conjugation info** (for verbs): the `–` separated forms (infinitive – past – present – future)

**Extracting the Hebrew word:**
- Strip parentheses: `(ב...)`, `(רבים: ...)`, etc.
- Strip gender markers: `[זכר]`, `[נקבה]`
- **Masc/fem pairs: KEEP BOTH FORMS. Never narrow to the masculine only.**
  - Card field (`"hebrew"`): `רווק / רווקה` — both forms, slash separator, no nikud
  - `"hebrew_nikud"`: `רַוָּק, רַוָּקָה` — both forms, **comma** separator (Carmit reads both with a natural pause; transliteration covers both)
  - Russian: both genders too — `Холостяк / незамужняя`
  - This applies to nouns and adjectives alike: `מכר / מכרה`, `מבריק / מבריקה`, `בינוני / בינונית`
- If there are `–` separated conjugations, take the infinitive (first form, starts with `ל`)

**Extracting conjugations for verbs:**
- From `לזייף – זייף – מזייף – יזייף`: conjugations = `זייף – מזייף – יזייף` (drop the infinitive)
- From multi-line format (second line is `זייף – מזייף – יזייף`): conjugations = that line as-is
- Conjugations are passed **without nikud** — they are displayed as-is in the card

**Examples:**
- `בינוני / בינונית = СРЕДНИЙ` → Hebrew: `בינוני / בינונית`, nikud: `בִּינוֹנִי, בִּינוֹנִית`, Russian: `Средний / средняя`
- `להתרכז (ב...) – התרכז – מתרכז – יתרכז = СОСРЕДОТОЧИВАТЬСЯ` → Hebrew: `להתרכז`, Russian: `Сосредоточиваться, концентрироваться`
- `נקודת מבט (רבים: נקודות מבט) [נקבה] = ТОЧКА ЗРЕНИЯ` → Hebrew: `נקודת מבט`, Russian: `Точка зрения`

---

## Step 2 — Determine section (grammatical group)

Match each word to the correct `hebrew_words.json` key:

| Section key | Deck | Rule |
|---|---|---|
| `מילים` | Hebrew-Russian::מילים | Nouns, adjectives, adverbs, prepositions — anything that is NOT a verb |
| `פעל מילים` | Hebrew-Russian::פעל | Verbs where past tense has no prefix and no middle-letter doubling (e.g., כתב, למד) |
| `פיעל מילים` | Hebrew-Russian::פיעל | Past tense has doubled middle letter (e.g., זיקק, ביקר, דיבר) |
| `הפיעל מילים` | Hebrew-Russian::הפיעל | Past tense starts with `ה` (but NOT `הת`), present starts with `מ` (e.g., הזיע→מזיע) |
| `התפעל מילים` | Hebrew-Russian::התפעל | Past tense starts with `הת` (e.g., התרכז, התווכח, התנשף) |
| `נפעל מילים` | Hebrew-Russian::נפעל | Past tense starts with `נ` (e.g., נכנס, נגמר) |

**Detection logic** (use the past tense form — 2nd `–` separated form):
1. No conjugation given → `מילים`
2. Past starts with `הת` → `התפעל מילים`
3. Past starts with `ה` (not `הת`) → `הפיעל מילים`
4. Past starts with `נ` → `נפעל מילים`
5. Past has 4+ letters with no prefix → `פיעל מילים`
6. Otherwise → `פעל מילים`

---

## Step 3 — Add nikud (vowel marks)

Words always arrive **without nikud**. Before running the script, Claude must add nikud to each Hebrew word using its knowledge of Hebrew. Nikud is required for:
- Correct audio pronunciation by Carmit Enhanced TTS
- Correct transliteration into Russian letters

Use knowledge of standard Israeli Hebrew pronunciation. For less common words, look up on [Pealim](https://www.pealim.com) or [Morfix](https://www.morfix.co.il).

**Examples:**
- `מוכרז` → `מוּכְרָז`
- `תופעה` → `תּוֹפָעָה`
- `להכריז` → `לְהַכְרִיז`
- `אזרח` → `אֶזְרָח`

Pass **two separate fields** to `add_words.py`:
- `"hebrew"` — the clean form (no nikud), exactly as it should appear in the card and JSON
- `"hebrew_nikud"` — the same word with nikud, used ONLY for audio and transliteration

**Do NOT let the script strip nikud to derive the clean form.** Stripping can silently drop letters (e.g. `מרווח` → `מרוח`, losing a ו). Always provide the clean form yourself.

---

## Step 4 — Check for duplicates

Compare each word (nikud stripped) against existing entries in `hebrew_words.json`. Skip duplicates and report them.

---

## Step 5 — MANDATORY: show the table and WAIT for approval

**Never run `add_words.py` before the user explicitly approves the word list.** Always show a table first:

| # | Hebrew поле карточки | Секция | С никуд | Транслитерация | Перевод |
|---|---|---|---|---|---|

For verbs, show the card field with the blank line: `לדקור<br><br>דקר – דוקר – ידקור`.

Then **stop and wait**. Approval means a clear go-ahead: «ок», «давай», «делай файлы», «апрув».

**These are NOT approval — do not proceed:**
- A correction or new requirement («добавляй пустую строчку», «поменяй перевод») → apply the change, then **show the table again** and wait
- A question about the list
- Silence or an unrelated message

If the user gives a correction, the cycle restarts: fix → new table → wait for approval.

---

## Step 6 — Run add_words.py

**IMPORTANT: MacOS-MCP must be connected.** The ElevenLabs API is not reachable from the sandbox, so audio generation must run on the user's Mac via `mcp__MacOS-MCP__Shell`. If MacOS-MCP is unavailable, write the command to a shell script and ask the user to run it in Terminal.

```bash
cd "/Users/andreilevitskii/Claude/Projects/Hebrew Json"
python3 add_words.py --words '<JSON array>'
```

JSON format — `"hebrew"` clean (no nikud), `"hebrew_nikud"` with nikud; for verbs add optional `"conjugations"` (no nikud):
```json
[
  {"hebrew": "בינוני", "hebrew_nikud": "בִּינוֹנִי", "russian": "Средний, посредственный", "section": "מילים"},
  {"hebrew": "מרווח", "hebrew_nikud": "מְרֻוָּח", "russian": "Просторный", "section": "מילים"},
  {"hebrew": "לזייף", "hebrew_nikud": "לְזַיֵּף", "russian": "Подделывать, фальсифицировать", "section": "פיעל מילים", "conjugations": "זייף – מזייף – יזייף"}
]
```

---

## Step 7 — Output

The script produces:
- Updated `hebrew_words.json` (nikud stripped, infinitive only in storage)
- One `.apkg` per section that received new words (e.g. `new_words_מילים.apkg`, `new_words_התפעל.apkg`)
- Each card: Hebrew · Russian · Audio (Carmit Enhanced) · Transliteration

**Verb Hebrew field format** (in the Anki card):
```
לזייף

זייף – מזייף – יזייף
```
Line 1: infinitive (no nikud). Then a **blank line**. Then past – present – future (no nikud).
In the field string this is `infinitive\n\nconjugations` (двойной перевод строки).
Audio and transliteration are generated from the infinitive with nikud only.
Non-verb cards have just the word on one line.

Present all `.apkg` files to the user. Report skipped duplicates.

**Audio filenames must be ASCII.** Media files inside the `.apkg` are referenced by index-based names (`0.mp3`, `1.mp3`, ...), NOT by the Hebrew word. Hebrew filenames with spaces or Unicode nikud/normalization differences prevent players (SmartCards+) from matching the `[sound:]` tag to the audio file, so no sound plays. `add_words.py` handles this automatically — never revert to Hebrew audio filenames.

---

## Публикация базы — GitHub

После сохранения `hebrew_words.json` скрипт сам коммитит его и пушит в публичный репозиторий:

```
https://github.com/AndreyLevitskiy/hebrew-anki-words
```

Отвечает за это функция `publish_to_github()` в `add_words.py`: `git add hebrew_words.json` → `commit` → `push origin main`. Если база не изменилась, коммит не создаётся. Аутентификация — по SSH-ключу `~/.ssh/id_ed25519`.

**Google Drive больше не используется.** Раньше скрипт клал копию базы в синк-папку Диска — этот блок вырезан в августе 2026. Если в выводе скрипта всплывает Drive, значит запущена старая версия.

Оттуда же базу читает скилл `hebrew-dialogue` — по raw-ссылке, без авторизации. Поэтому **push важен**: не уехал коммит — диалоги собираются по устаревшему словарю. Если `publish_to_github()` напечатал предупреждение, сказать об этом пользователю, а не проглатывать.

---

## Озвучка — ElevenLabs

Audio is generated by the ElevenLabs API (replaced macOS `say`/Carmit in July 2026). Config lives at the top of `add_words.py`:

| Параметр | Значение |
|---|---|
| Голос | **Jessica** — `cgSgspJ2msm6clMCkdW9` |
| Модель | `eleven_v3` |
| Language override | `language_code: "he"` |
| Stability | `1.0` (пресет **Robust**) |
| similarity_boost | `0.75`, `use_speaker_boost: true` |
| Префикс текста | `[spoken in Hebrew] ` |
| Формат | `mp3_44100_128` |

**Key details:**
- The text sent to the API is the form **with nikud**, prefixed by `[spoken in Hebrew] `. The tag is a v3 direction and is **not read aloud** (verified: 1.41s with tag vs 1.49s without — only the word is spoken).
- The API key is read from `~/.config/hebrew-json/elevenlabs_key` (moved out of the project folder in August 2026; the script still falls back to `.elevenlabs_key` in the project folder if the new path is missing). It lives outside the repo and **must never be bundled into the `.skill` zip** — only `SKILL.md` and `scripts/add_words.py` go in.
- Library voices (Juniper, Aria, Charlotte, ...) require a **paid** ElevenLabs plan; on free tier the API returns `402 paid_plan_required`. Only premade voices work on free. If the user upgrades and wants a library voice, just change `EL_VOICE_ID`.
- If a request fails, the script prints the word with `✗`, lists all failures at the end, and still builds the `.apkg` (that card simply has no audio). Never silently ship a batch with missing audio — report it.

---

## Поле Transliteration (Comment)

Каждая карточка содержит поле **Transliteration** — фонетическое чтение слова русскими буквами. Генерируется автоматически функцией `transliterate()` из `add_words.py` на основе никуда.

Без никуда транслитерация будет нечитаемой (только согласные). Поэтому Claude всегда добавляет никуд перед запуском скрипта.

---

## After running

Report to the user:
- Words added per section
- Skipped duplicates
- Transliteration for each word (for verification)
- Present `.apkg` files for import into SmartCards+
