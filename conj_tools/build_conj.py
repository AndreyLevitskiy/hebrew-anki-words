# -*- coding: utf-8 -*-
import re, sys, html, json, random, subprocess, urllib.parse, os, time
sys.path.insert(0, "/Users/andreilevitskii/Claude/Projects/Hebrew Json")
import add_words as A

BINYAN = sys.argv[1]            # e.g. פעל
BINYAN_RU = sys.argv[2]         # e.g. ПААЛЬ (as on pealim.com/ru)
VERBS = sys.argv[3].split(",")  # infinitives from the base
PER_VERB = 3
NIKUD = re.compile('[֑-ׇ]')
HOLAM = 'ֹ'

LABEL = {
 'PERF-1s':'я, прошедшее','PERF-1p':'мы, прошедшее','PERF-2ms':'ты (м.), прошедшее','PERF-2fs':'ты (ж.), прошедшее',
 'PERF-2mp':'вы (м.), прошедшее','PERF-2fp':'вы (ж.), прошедшее','PERF-3ms':'он, прошедшее','PERF-3fs':'она, прошедшее','PERF-3p':'они, прошедшее',
 'IMPF-1s':'я, будущее','IMPF-1p':'мы, будущее','IMPF-2ms':'ты (м.), будущее','IMPF-2fs':'ты (ж.), будущее',
 'IMPF-2mp':'вы, будущее','IMPF-3ms':'он, будущее','IMPF-3fs':'она, будущее','IMPF-3mp':'они, будущее',
 'AP-ms':'настоящее, м. ед. ч.','AP-fs':'настоящее, ж. ед. ч.','AP-mp':'настоящее, м. мн. ч.','AP-fp':'настоящее, ж. мн. ч.',
 'IMP-2ms':'повелительное, ты (м.)','IMP-2fs':'повелительное, ты (ж.)','IMP-2mp':'повелительное, вы',
}

def get(url):
    return subprocess.run(["curl","-s","-L","-A","Mozilla/5.0",url],capture_output=True,text=True).stdout

def clean(x):
    return html.unescape(re.sub('<.*?>','',x)).replace('‏','').replace('!','').strip()

def plene(menukad):
    # vowelless spelling: holam haser on a consonant -> add ו
    out=[]
    chars=list(menukad)
    for i,c in enumerate(chars):
        out.append(c)
        if c==HOLAM:
            # find the consonant this mark sits on
            j=i-1
            while j>=0 and NIKUD.match(chars[j]): j-=1
            nxt=i+1
            while nxt<len(chars) and NIKUD.match(chars[nxt]): nxt+=1
            if j>=0 and chars[j]!='ו' and not (nxt<len(chars) and chars[nxt]=='ו'):
                out.append('ו')
    return NIKUD.sub('',''.join(out))

FORCE=dict(x.split('=') for x in os.environ.get('FORCE','').split(',') if x)
def find_page(verb):
    if verb in FORCE:
        p=get("https://www.pealim.com"+FORCE[verb])
        return (FORCE[verb],p) if ('Глагол – '+BINYAN_RU) in p else (None,None)
    s=get("https://www.pealim.com/ru/search/?q="+urllib.parse.quote(verb))
    for link in dict.fromkeys(re.findall(r'href="(/ru/dict/\d+-[^"/]+/)"',s)):
        p=get("https://www.pealim.com"+link); time.sleep(0.5)
        i=p.find('id="INF-L"')
        if i<0: continue
        blk=p[i:p.find('</td>',i)]
        mm=re.search(r'<span class="menukad">(.*?)</span>',blk,re.S)
        ch=re.search(r'<span class="chaser">\s*~\s*(.*?)</span>',blk,re.S)
        inf=clean(ch.group(1)) if ch else plene(clean(mm.group(1)))
        loose=lambda x: re.sub('[וי]','',x)
        if loose(inf)==loose(verb) and ('Глагол – '+BINYAN_RU) in p:
            return link,p
    return None,None

def forms(p):
    res={}
    for k in LABEL:
        i=p.find('id="'+k+'"')
        if i<0: continue
        blk=p[i:p.find('</td>',i)]
        mm=re.search(r'<span class="menukad">(.*?)</span>',blk,re.S)
        ch=re.search(r'<span class="chaser">\s*~\s*(.*?)</span>',blk,re.S)
        me=re.search(r'<div class="meaning">(.*?)</div>',blk,re.S)
        if mm: res[k]=(clean(mm.group(1)), clean(me.group(1)) if me else '', clean(ch.group(1)) if ch else None)
    return res

rnd=random.Random(int(os.environ.get("SEED","42")))
PER_VERB=int(os.environ.get("PER_VERB",PER_VERB))
entries=[]; report=[]
for v in VERBS:
    link,p=find_page(v)
    if not p:
        report.append(f"✗ {v}: не нашёл на pealim"); continue
    F=forms(p)
    print(v, link, len(F), file=sys.stderr)
    perf=[k for k in F if k.startswith('PERF')]; impf=[k for k in F if k.startswith('IMPF')]
    rest=[k for k in F if k not in perf and k not in impf]
    pools=[x for x in (perf,impf,rest) if x]
    if len(F)<3:
        report.append(f"✗ {v}: на странице мало форм ({len(F)})"); continue
    pick=[]
    for pool in pools:
        c=[k for k in pool if k not in pick]
        if c: pick.append(rnd.choice(c))
    while len(pick)<PER_VERB:
        c=[k for k in F if k not in pick]; pick.append(rnd.choice(c))
    for k in pick[:PER_VERB]:
        menukad,meaning,chaser=F[k]
        answer=chaser or NIKUD.sub('',menukad)
        entries.append({
            "hebrew": answer, "hebrew_card": answer, "hebrew_nikud": menukad,
            "russian": f"{v} — {LABEL[k]}",
            "transliteration": A.transliterate(menukad)+"\n"+menukad+"\n"+meaning,
            "audio_text": menukad,
            "guid_key": f"{v} — {LABEL[k]}",
        })
    report.append(f"✓ {v} ({link}): "+", ".join(f"{LABEL[k]} → {F[k][2] or NIKUD.sub('',F[k][0])}" for k in pick))

print("\n".join(report))
json.dump(entries,open(os.environ.get("OUT",f"/tmp/pealim/entries_{BINYAN}.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("entries:",len(entries))
