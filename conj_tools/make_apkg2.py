import sys, json, os, shutil
sys.path.insert(0, "/Users/andreilevitskii/Claude/Projects/Hebrew Json")
import add_words as A
src, outname, B = sys.argv[1], sys.argv[2], sys.argv[3]
db=json.load(open("/Users/andreilevitskii/Claude/Projects/Hebrew Json/hebrew_words.json",encoding="utf-8"))
ru={w['hebrew'].split()[0]:w['russian'] for w in db[B+' מילים']}
E=json.load(open(src,encoding="utf-8"))
fail=[]
for i,e in enumerate(E):
    tr,men,mean=e["transliteration"].split("\n")
    verb=e["russian"].split(" — ")[0]
    e["transliteration"]="\n".join([tr,men,mean or ru.get(verb,"")])
    e["audio_path"]=A.gen_audio(e["audio_text"], f"{outname}_{i}")
    if not e["audio_path"]: fail.append(e["hebrew"])
    if i%25==0: print(i, flush=True)
out=os.path.join("/Users/andreilevitskii/Claude/Projects/Hebrew Json", outname+".apkg")
A.build_apkg(E, f"Hebrew-Russian::Спряжения::{B}", out)
shutil.copy(out, os.path.expanduser(f"~/Desktop/{outname}.apkg"))
print("DONE cards:",len(E),"audio fail:",len(fail),fail[:20],"->",out, flush=True)
