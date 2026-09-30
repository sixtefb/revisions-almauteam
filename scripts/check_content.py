"""Valide les fichiers content/*.json et signale les biais (réponse la plus longue, doublons)."""
import json, glob, sys, os
base = os.path.join(os.path.dirname(__file__), "..", "content")
ok = True
for f in sorted(glob.glob(os.path.join(base, "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    fiches = {x["id"] for x in d["fiches"]}
    ids, longest, tot = set(), 0, 0
    for q in d["qcm"]:
        if q["id"] in ids: print("DOUBLON", q["id"]); ok = False
        ids.add(q["id"])
        if q["fiche"] not in fiches: print("FICHE INCONNUE", q["id"], q["fiche"]); ok = False
        if len(q["wrong"]) != 3: print("3 mauvaises réponses attendues", q["id"]); ok = False
        opts = [q["correct"]] + q["wrong"]
        if len(set(opts)) != 4: print("Options identiques", q["id"]); ok = False
        if len(q["correct"]) > max(len(w) for w in q["wrong"]): longest += 1
        tot += 1
    for fi in d["fiches"]:
        for lang in ("fr", "en"):
            if not fi["body"][lang]: print("fiche vide", fi["id"], lang); ok = False
        if len(fi["body"]["fr"]) != len(fi["body"]["en"]): print("FR/EN désalignés", fi["id"]); ok = False
    print(f"{d['id']:22} {len(d['fiches'])} fiches, {tot} QCM, bonne réponse la plus longue : {longest}/{tot} ({100*longest//tot}%)")
sys.exit(0 if ok else 1)
