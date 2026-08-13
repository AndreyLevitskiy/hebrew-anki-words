#!/usr/bin/env python3
"""
Full workflow: add new Hebrew words to JSON + generate audio + create .apkg per section.

Usage:
  python3 add_words.py --words '[{"hebrew":"שָׁלוֹם","russian":"мир","section":"מילים"}]'
  python3 add_words.py --words-file /path/to/words.json

Output: one new_words_<section>.apkg per section that has new words.
"""

import argparse, collections, hashlib, json, os, re, sqlite3, subprocess, sys, tempfile, time, urllib.error, urllib.request, zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH  = os.path.join(SCRIPT_DIR, "hebrew_words.json")
AUDIO_DIR  = "/tmp/heb_audio"

MODEL_ID = 1424504004   # matches the working reference apkg

# ── ElevenLabs TTS config ────────────────────────────────────────────────────
EL_KEY_PATH   = os.path.expanduser("~/.config/hebrew-json/elevenlabs_key")  # вне репо
_LEGACY_KEY   = os.path.join(SCRIPT_DIR, ".elevenlabs_key")                 # старое место, fallback
if not os.path.exists(EL_KEY_PATH) and os.path.exists(_LEGACY_KEY):
    EL_KEY_PATH = _LEGACY_KEY
EL_VOICE_ID   = "cgSgspJ2msm6clMCkdW9"   # Jessica
EL_VOICE_NAME = "Jessica"
EL_MODEL      = "eleven_v3"
EL_LANGUAGE   = "he"                      # language override
EL_STABILITY  = 1.0                       # "Robust" preset
EL_PREFIX     = "[spoken in Hebrew] "     # audio tag; not read aloud
EL_FORMAT     = "mp3_44100_128"
EL_URL        = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format={fmt}"

SECTION_DECK = {
    "מילים":       "Hebrew-Russian::מילים",
    "פעל מילים":   "Hebrew-Russian::פעל",
    "פיעל מילים":  "Hebrew-Russian::פיעל",
    "הפיעל מילים": "Hebrew-Russian::הפיעל",
    "התפעל מילים": "Hebrew-Russian::התפעל",
    "נפעל מילים":  "Hebrew-Russian::נפעל",
}

SECTION_SLUG = {
    "מילים":       "מילים",
    "פעל מילים":   "פעל",
    "פיעל מילים":  "פיעל",
    "הפיעל מילים": "הפיעל",
    "התפעל מילים": "התפעל",
    "נפעל מילים":  "נפעל",
}

SEP      = "\x1f"
NIKUD_RE = re.compile(r'[ְ-ׇ]')

def strip_nikud(s):
    return NIKUD_RE.sub('', s)

def checksum(s):
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16)

# ── Transliteration ──────────────────────────────────────────────────────────────
DAGESH   = 'ּ'
SHIN_DOT = 'ׁ'
SIN_DOT  = 'ׂ'
RAFE     = 'ֿ'

VOWEL = {
    'ְ': '',  'ֱ': 'е', 'ֲ': 'а', 'ֳ': 'о',
    'ִ': 'и', 'ֵ': 'е', 'ֶ': 'е', 'ַ': 'а',
    'ָ': 'а', 'ֹ': 'о', 'ֺ': 'о', 'ֻ': 'у', 'ׇ': 'а',
}
CONS = {
    'א': '', 'ב': 'в', 'ג': 'г', 'ד': 'д', 'ה': 'h',
    'ו': 'в', 'ז': 'з', 'ח': 'х', 'ט': 'т', 'י': 'й',
    'ך': 'х', 'כ': 'х', 'ל': 'л', 'ם': 'м', 'מ': 'м',
    'ן': 'н', 'נ': 'н', 'ס': 'с', 'ע': '', 'ף': 'ф',
    'פ': 'ф', 'ץ': 'ц', 'צ': 'ц', 'ק': 'к', 'ר': 'р',
    'ש': 'ш', 'ת': 'т',
}
DAGESH_HARD = {'ב': 'б', 'כ': 'к', 'פ': 'п'}
SILENT_CONS = {'א', 'ע'}
IS_MARK     = lambda c: 'ְ' <= c <= 'ׇ' or c == RAFE

def transliterate(word):
    chars = list(word)
    n = len(chars)
    result, i, at_start = [], 0, True
    while i < n:
        ch = chars[i]
        if IS_MARK(ch): i += 1; continue
        j = i + 1
        marks = []
        while j < n and IS_MARK(chars[j]):
            marks.append(chars[j]); j += 1
        has_dagesh = DAGESH in marks
        has_sin    = SIN_DOT in marks
        has_shva   = 'ְ' in marks
        base_v     = [VOWEL[m] for m in marks if m in VOWEL and m != 'ְ' and VOWEL[m]]
        shva_v     = 'е' if (has_shva and at_start) else ''

        if ch == 'י' and at_start and has_shva:
            result.append('е'); at_start = False; i = j; continue
        if ch == 'ו' and has_dagesh:
            result.append('у'); at_start = False; i = j; continue
        if ch == 'ו' and 'ֹ' in marks:
            result.append('о'); at_start = False; i = j; continue
        if ch == 'י' and not base_v and not has_shva:
            prev = ''.join(result)
            if prev and prev[-1] in 'аеиоуэ': i = j; continue
        if ch == 'ש':
            cons = 'с' if has_sin else 'ш'
        elif has_dagesh and ch in DAGESH_HARD:
            cons = DAGESH_HARD[ch]
        else:
            cons = CONS.get(ch, ch)
        if ch == 'ה' and not base_v and not shva_v and j >= n: i = j; continue
        if ch in SILENT_CONS:
            vs = base_v or ([shva_v] if shva_v else [])
            result.extend(['э' if (at_start and v == 'е') else v for v in vs])
            if vs: at_start = False
            i = j; continue
        result.append(cons)
        if shva_v: result.append(shva_v)
        result.extend(base_v)
        at_start = False; i = j
    return ''.join(result)

# ── Публикация базы в GitHub ─────────────────────────────────────
def publish_to_github():
    """Коммитит hebrew_words.json и пушит в origin/main."""
    git = ["git", "-C", SCRIPT_DIR]
    try:
        subprocess.run(git + ["add", "hebrew_words.json"], check=True)
        if subprocess.run(git + ["diff", "--cached", "--quiet"]).returncode == 0:
            print("→ GitHub: база не изменилась, коммит не нужен")
            return
        msg = time.strftime("база: обновление %Y-%m-%d %H:%M")
        subprocess.run(git + ["commit", "-q", "-m", msg], check=True)
        subprocess.run(git + ["push", "-q", "origin", "main"], check=True)
        print("→ база опубликована в GitHub")
    except FileNotFoundError:
        print("⚠ git не найден — база НЕ опубликована", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"⚠ git вернул ошибку ({e}) — база НЕ опубликована", file=sys.stderr)

# ── Audio (ElevenLabs) ────────────────────────────────────────────────────────
def _el_key():
    """Read the ElevenLabs API key from .elevenlabs_key (kept out of the .skill zip)."""
    try:
        with open(EL_KEY_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"  ✗ Нет файла с ключом: {EL_KEY_PATH}", file=sys.stderr)
        return ""

def gen_audio(hnikud, fname):
    """Generate audio via ElevenLabs. Text is sent WITH nikud, prefixed by the
    [spoken in Hebrew] tag (interpreted as a direction, not read aloud)."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    mp3 = os.path.join(AUDIO_DIR, fname + ".mp3")
    key = _el_key()
    if not key:
        return ""

    payload = json.dumps({
        "text": EL_PREFIX + hnikud,
        "model_id": EL_MODEL,
        "language_code": EL_LANGUAGE,
        "voice_settings": {
            "stability": EL_STABILITY,
            "similarity_boost": 0.75,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        EL_URL.format(voice=EL_VOICE_ID, fmt=EL_FORMAT),
        data=payload, method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio = resp.read()
        if not audio.startswith(b"ID3") and not audio[:2] == b"\xff\xfb":
            print(f"  ⚠ Не похоже на MP3: {hnikud}", file=sys.stderr)
            return ""
        with open(mp3, "wb") as f:
            f.write(audio)
        return mp3
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        print(f"  ⚠ ElevenLabs {e.code} для {hnikud}: {body}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  ⚠ Audio failed {hnikud}: {e}", file=sys.stderr)
        return ""

# ── Build .apkg for one section ───────────────────────────────────────────────
def build_apkg(entries, deck_name, output_path):
    """
    entries: [{"hebrew_nikud":..., "hebrew":..., "russian":..., "transliteration":..., "audio_path":...}]
    """
    now_s  = int(time.time())
    now_ms = int(time.time() * 1000)

    model = {str(MODEL_ID): {
        "vers": [], "name": "Hebrew-Russian", "tags": [], "did": 1, "usn": -1,
        "req": [[0, "all", [0]]],
        "flds": [
            {"name": "Hebrew",         "media": [], "sticky": False, "rtl": True,  "ord": 0, "font": "Arial", "size": 20},
            {"name": "Russian",        "media": [], "sticky": False, "rtl": False, "ord": 1, "font": "Arial", "size": 20},
            {"name": "Sound",          "media": [], "sticky": False, "rtl": False, "ord": 2, "font": "Arial", "size": 20},
            {"name": "Transliteration","media": [], "sticky": False, "rtl": False, "ord": 3, "font": "Arial", "size": 18},
        ],
        "sortf": 0,
        "tmpls": [{
            "name": "Card 1", "ord": 0,
            "qfmt": "{{Hebrew}}{{Sound}}",
            "afmt": "{{FrontSide}}<hr>{{Russian}}<br>{{Transliteration}}",
            "did": None, "bqfmt": "", "bafmt": ""
        }],
        "mod": now_s, "type": 0, "id": MODEL_ID,
        "latexPost": "\\end{document}",
        "latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n"
                    "\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n"
                    "\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}\n",
    }}

    deck = {"1": {
        "desc": "", "name": deck_name, "extendRev": 50, "usn": 0,
        "collapsed": False, "newToday": [0, 0], "timeToday": [0, 0],
        "dyn": 0, "extendNew": 10, "conf": 1,
        "revToday": [0, 0], "lrnToday": [0, 0], "id": 1, "mod": now_s,
    }}

    dconf = {"1": {
        "name": "Default", "replayq": True,
        "lapse": {"leechFails": 8, "delays": [10], "minInt": 1, "leechAction": 0, "mult": 0},
        "rev": {"perDay": 200, "ease4": 1.3, "fuzz": 0.05, "minSpace": 1,
                "ivlFct": 1, "maxIvl": 36500, "bury": True, "ease2": 1.2},
        "timer": 0, "maxTaken": 60, "usn": 0,
        "new": {"perDay": 20, "delays": [1, 10], "separate": True, "ints": [1, 4, 7],
                "initialEase": 2500, "bury": True, "order": 1},
        "mod": now_s, "id": 1, "autoplay": True,
    }}

    conf = json.dumps({
        "nextPos": 1, "estTimes": True, "activeDecks": [1], "sortField": "noteFlds",
        "timeLim": 0, "addToCur": True, "newBury": True, "newSpread": 0,
        "dueCounts": True, "sortBackwards": False, "curDeck": 1,
        "curModel": str(MODEL_ID), "collapseTime": 1200,
    })

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "collection.anki2")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.executescript("""
CREATE TABLE col (id integer, crt integer, mod integer, scm integer, ver integer,
  dty integer, usn integer, ls integer, conf text, models text, decks text, dconf text, tags text);
CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null,
  mod integer not null, usn integer not null, tags text not null, flds text not null,
  sfld integer not null, csum integer not null, flags integer not null, data text not null);
CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null,
  ord integer not null, mod integer not null, usn integer not null, type integer not null,
  queue integer not null, due integer not null, ivl integer not null, factor integer not null,
  reps integer not null, lapses integer not null, left integer not null, odue integer not null,
  odid integer not null, flags integer not null, data text not null);
CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null,
  ease integer not null, ivl integer not null, lastIvl integer not null, factor integer not null,
  time integer not null, type integer not null);
CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
CREATE INDEX ix_notes_usn on notes (usn);
CREATE INDEX ix_cards_usn on cards (usn);
CREATE INDEX ix_cards_nid on cards (nid);
""")
        c.execute("INSERT INTO col VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, now_s, now_ms, now_ms, 11, 0, 0, 0,
             conf, json.dumps(model), json.dumps(deck), json.dumps(dconf), "{}"))

        nid = now_ms
        cid = now_ms + 1
        due = 1
        media_json  = {}
        media_files = []

        for idx, e in enumerate(entries):
            hnikud  = e["hebrew_nikud"]
            heb     = e.get("hebrew_card", e["hebrew"])  # no nikud; verbs include conjugations
            rus     = e["russian"]
            translit = e["transliteration"]
            apath   = e.get("audio_path", "")

            sound = ""
            if apath and os.path.exists(apath):
                # ASCII-safe media filename (index-based) — avoids Hebrew/space/Unicode
                # normalization mismatches that stop players from finding the audio.
                key   = str(len(media_files))
                fname = key + os.path.splitext(apath)[1]   # .mp3 (ElevenLabs)
                media_json[key] = fname
                media_files.append((key, apath))
                sound = f"[sound:{fname}]"

            flds = SEP.join([heb, rus, sound, translit])
            guid = hashlib.md5(f"{deck_name}::{hnikud}".encode()).hexdigest()[:10]
            csum = checksum(heb)

            c.execute("INSERT OR IGNORE INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (nid, guid, MODEL_ID, now_s, -1, "", flds, heb, csum, 0, ""))
            c.execute("INSERT OR IGNORE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, nid, 1, 0, now_s, -1, 0, 0, due, 0, 0, 0, 0, 0, 0, 0, 0, ""))
            nid += 2; cid += 2; due += 1

        conn.commit()
        conn.close()

        media_path = os.path.join(tmp, "media")
        with open(media_path, "w") as f:
            json.dump(media_json, f)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, "collection.anki2")
            zf.write(media_path, "media")
            for key, src in media_files:
                zf.write(src, key)

# ── main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--words")
    g.add_argument("--words-file")
    args = parser.parse_args()

    words = json.loads(open(args.words_file).read()) if args.words_file else json.loads(args.words)

    with open(JSON_PATH, encoding="utf-8") as f:
        db = json.load(f)

    existing = {sec: {strip_nikud(w["hebrew"]) for w in items} for sec, items in db.items()}

    new_by_section = collections.defaultdict(list)
    skipped = []

    for w in words:
        sec          = w["section"]
        russian      = w["russian"].strip()
        conjugations = w.get("conjugations", "").strip()  # "זייף – מזייף – יזייף" for verbs

        # "hebrew" = clean form (no nikud) — used for card and JSON storage
        # "hebrew_nikud" = form with vowel marks — used ONLY for audio and transliteration
        # Never derive the clean form by stripping nikud: letters like ו can be lost
        hclean = w["hebrew"].strip()
        hnikud = w.get("hebrew_nikud", hclean).strip()
        translit = transliterate(hnikud)

        # Hebrew field in Anki card: infinitive only, or infinitive + blank line + conjugations
        heb_card = hclean + ("\n\n" + conjugations if conjugations else "")

        if sec not in db:
            print(f"  ✗ Неизвестная секция: {sec}", file=sys.stderr); continue
        if hclean in existing.get(sec, set()):
            skipped.append(hclean); continue

        db[sec].append({"hebrew": hclean, "russian": russian})
        existing.setdefault(sec, set()).add(hclean)
        new_by_section[sec].append({
            "hebrew": hclean, "hebrew_card": heb_card,
            "hebrew_nikud": hnikud, "russian": russian, "transliteration": translit
        })
        print(f"  + {hclean} ({hnikud}) [{translit}] → {sec}")

    if skipped:
        print(f"\nПропущено (дубли): {', '.join(skipped)}")
    if not new_by_section:
        print("Нет новых слов."); return

    # Save JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for v in new_by_section.values())
    print(f"\nJSON обновлён: +{total} слов")

    # Публикация базы в GitHub (чтобы она читалась из чата с любого устройства)
    publish_to_github()

    # Generate audio for all new words
    print(f"\nГенерирую аудио (ElevenLabs · {EL_VOICE_NAME} · {EL_MODEL})...")
    failed = []
    for sec, entries in new_by_section.items():
        for e in entries:
            hnikud = e["hebrew_nikud"]
            fname  = strip_nikud(hnikud).replace("/", "_")
            e["audio_path"] = gen_audio(hnikud, fname)
            mark = "🔊" if e["audio_path"] else "✗ "
            print(f"  {mark} {hnikud} [{e['transliteration']}]")
            if not e["audio_path"]:
                failed.append(strip_nikud(hnikud))
    if failed:
        print(f"\n⚠ Без озвучки ({len(failed)}): {', '.join(failed)}")

    # Build one .apkg per section
    print("\nСоздаю файлы...")
    out_files = []
    for sec, entries in new_by_section.items():
        slug      = SECTION_SLUG.get(sec, sec)
        deck_name = SECTION_DECK.get(sec, sec)
        out_path  = os.path.join(SCRIPT_DIR, f"new_words_{slug}.apkg")
        build_apkg(entries, deck_name, out_path)
        print(f"  ✓ {os.path.basename(out_path)} ({len(entries)} карточек)")
        out_files.append(out_path)

    print(f"\nГотово: {len(out_files)} файл(ов)")
    for f in out_files:
        print(f"  → {f}")

if __name__ == "__main__":
    main()
