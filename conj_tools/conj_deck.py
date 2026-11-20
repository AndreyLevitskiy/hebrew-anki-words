#!/usr/bin/env python3
"""Build a conjugation deck (Спряжения::<binyan>) for a list of verbs.

    python3 conj_tools/conj_deck.py --binyan פעל --verbs "לכתוב,לסגור" --out conj_פעל_new

Forms come from pealim.com (Russian version), N random forms per verb
(one past, one future, one present/imperative). Audio: ElevenLabs, falls back
to macOS Carmit. Output: <project>/<out>.apkg + a copy on the Desktop.
Does NOT touch hebrew_words.json.
"""
import argparse, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
BINYAN_RU = {"פעל": "ПААЛЬ", "פיעל": "ПИЭЛЬ", "הפיעל": "hИФЪИЛЬ",
             "התפעל": "hИТПАЭЛЬ", "נפעל": "НИФЪАЛЬ"}

ap = argparse.ArgumentParser()
ap.add_argument("--binyan", required=True, choices=BINYAN_RU)
ap.add_argument("--verbs", required=True, help="comma-separated infinitives without nikud")
ap.add_argument("--out", required=True, help="output name without .apkg, e.g. conj_פעל_new")
ap.add_argument("--force", default="", help='verb=/ru/dict/<id>-<slug>/,... when search misses the page')
ap.add_argument("--seed", type=int, default=int(time.time()))
a = ap.parse_args()

tmp = tempfile.mkdtemp(prefix="conj_")
entries = os.path.join(tmp, "entries.json")
env = dict(os.environ, SEED=str(a.seed), OUT=entries, FORCE=a.force)
r = subprocess.run([sys.executable, os.path.join(HERE, "build_conj.py"),
                    a.binyan, BINYAN_RU[a.binyan], a.verbs], env=env)
if r.returncode or not os.path.exists(entries):
    sys.exit("✗ сбор форм с pealim не удался")
subprocess.run([sys.executable, os.path.join(HERE, "make_apkg2.py"),
                entries, a.out, a.binyan], check=True)
