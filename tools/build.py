#!/usr/bin/env python3
"""Construiește index.html din harta de operațiuni (Excel), cursul de manager și parole.

Utilizare:
    pip install openpyxl cryptography
    python3 tools/build.py Harta_Operatiuni_Blinkers_Brew.xlsx curs-manager/

Parolele se cer interactiv (sau din variabilele BB_PAROLA și BB_PAROLA_MANAGER).
Ghidul e criptat cu parola echipei, cursul cu parola de manager (AES-256-GCM,
cheie derivată din parolă cu PBKDF2-SHA256), așa că în repo ajunge doar textul
criptat. Excel-ul și folderul cursului NU se pun în repo.
"""
import base64
import getpass
import html
import json
import os
import re
import sys
from pathlib import Path

import openpyxl
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
ITERATII = 310_000
ZILE = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]
MOMENTE = ["Deschidere", "În tură", "Închidere", "Săptămânal", "Situații speciale"]


def curat(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def randuri(wb, foaie, coloane):
    for r in wb[foaie].iter_rows(min_row=5, values_only=True):
        r = [curat(c) for c in r[:coloane]] + [""] * max(0, coloane - len(r))
        if any(r):
            yield r


def linii(text):
    return [x.strip() for x in text.splitlines() if x.strip()]


def citeste(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    greseli = []

    loc = {"nume": "", "adresa": "", "program": [], "contacte": [], "echipamente": [], "note": []}
    for sec, cheie, val, det, rol in randuri(wb, "Locatie", 5):
        if sec == "Info":
            loc["nume" if cheie == "Nume" else "adresa"] = val
        elif sec == "Program":
            loc["program"].append({"zi": cheie, "ore": val, "detaliu": det})
        elif sec == "Contacte":
            loc["contacte"].append({"rol": rol, "functie": cheie, "nume": val, "telefon": det})
        elif sec == "Echipamente":
            loc["echipamente"].append({"nume": cheie, "raportezi": val, "detaliu": det})
        elif sec == "Note":
            loc["note"].append({"titlu": cheie, "text": val})
        else:
            greseli.append(f"Locatie: secțiune necunoscută „{sec}”.")

    roluri = [{"cod": c, "nume": n, "raspunde": r, "oameni": [o.strip() for o in om.split(",") if o.strip()]}
              for c, n, r, om in randuri(wb, "Roluri", 4)]
    coduri_rol = {r["cod"] for r in roluri}

    procese = {}
    for cod, nume, moment, rol, miza, sub in randuri(wb, "Procese", 6):
        if moment not in MOMENTE:
            greseli.append(f"{cod}: momentul „{moment}” nu e unul din {', '.join(MOMENTE)}.")
        procese[cod] = {"cod": cod, "nume": nume, "moment": moment, "rol": rol, "miza": miza, "sub": linii(sub)}

    taskuri = []
    for pc, sub, task, rol, minute, cand, verif, proc in randuri(wb, "Taskuri", 8):
        taskuri.append({"id": len(taskuri), "p": pc, "sub": sub, "t": task, "rol": rol, "min": minute,
                        "cand": cand, "verif": verif, "proc": proc})

    proceduri = []
    for cod, titlu, pc, rol, decl, prio, pasi in randuri(wb, "Proceduri", 7):
        proceduri.append({"cod": cod, "titlu": titlu, "p": pc, "rol": rol, "decl": decl,
                          "prio": prio, "pasi": linii(pasi)})
    coduri_proc = {p["cod"] for p in proceduri}

    # Verificări, ca o greșeală de tipar din Excel să nu ajungă în ghid.
    for p in procese.values():
        if p["rol"] not in coduri_rol:
            greseli.append(f"{p['cod']}: rolul „{p['rol']}” nu există în foaia Roluri.")
    for t in taskuri:
        if t["p"] not in procese:
            greseli.append(f"Task „{t['t']}”: procesul „{t['p']}” nu există.")
        elif not any(s.split(" ")[0] == t["sub"] for s in procese[t["p"]]["sub"]):
            greseli.append(f"Task „{t['t']}”: sub-procesul „{t['sub']}” nu există în {t['p']}.")
        if t["rol"] not in coduri_rol:
            greseli.append(f"Task „{t['t']}”: rolul „{t['rol']}” nu există.")
        if t["proc"] and t["proc"] not in coduri_proc:
            greseli.append(f"Task „{t['t']}”: procedura „{t['proc']}” nu există.")
    for p in proceduri:
        if p["p"] not in procese:
            greseli.append(f"{p['cod']}: procesul „{p['p']}” nu există.")
        if p["rol"] not in coduri_rol:
            greseli.append(f"{p['cod']}: rolul „{p['rol']}” nu există.")
        if len(p["pasi"]) > 10:
            greseli.append(f"{p['cod']}: are {len(p['pasi'])} pași (maximum 10).")
    zile = [z["zi"] for z in loc["program"] if z["zi"] in ZILE]
    if zile != ZILE:
        greseli.append(f"Locatie / Program: zilele trebuie să fie, în ordine, {', '.join(ZILE)}.")
    for z in loc["program"]:
        if z["zi"] in ZILE and z["ore"] and not re.fullmatch(r"\d\d:\d\d – \d\d:\d\d|Închis", z["ore"]):
            greseli.append(f"Program {z['zi']}: scrie orele ca „16:00 – 23:00” sau „Închis”.")
    if greseli:
        sys.exit("Harta are greșeli:\n  - " + "\n  - ".join(greseli))

    return {"loc": loc, "roluri": roluri, "procese": procese, "taskuri": taskuri,
            "proceduri": proceduri, "momente": MOMENTE}


# ---------------------------------------------------------------------------
# Cursul de manager (paginile HTML Blinkers Brew × ATC + explicatii.json)
# ---------------------------------------------------------------------------
MODULE = {"00": "00-ghidul-managerului.html", "01": "01-operatiuni.html", "02": "02-produs-bere.html",
          "03": "03-client.html", "04": "04-oameni.html", "05": "05-bani.html", "06": "06-evaluare.html"}
MODUL_INTREBARI = {"Operațiuni": "01", "Produs": "02", "Client": "03", "Oameni": "04", "Bani": "05"}


def un_singur(model, text, ce, flags=re.S):
    gasite = re.findall(model, text, flags)
    if len(gasite) != 1:
        sys.exit(f"Curs: „{ce}” apare de {len(gasite)} ori (trebuie exact o dată).")
    return gasite[0]


def corp_pagina(sursa, fisier):
    corp = un_singur(r'<main><div class="wrap">(.*)</div></main>', sursa, f"{fisier} <main>")
    corp = re.sub(r"<script>.*?</script>", "", corp, flags=re.S)
    corp = re.sub(r'<p class="sig">.*?</p>', "", corp, flags=re.S)
    corp = re.sub(r'<div class="pn">.*?</div>', "", corp, flags=re.S)
    corp = re.sub(r'<a class="print"[^>]*>.*?</a>', "", corp, flags=re.S)
    # Linkurile între pagini devin rute în ghid.
    corp = re.sub(r'href="index\.html"', 'href="#/curs"', corp)
    corp = re.sub(r'href="(\d\d)-[\w-]+\.html"', r'href="#/curs/m/\1"', corp)
    return corp.strip()


def citeste_curs(folder):
    folder = Path(folder)
    module = []
    for mid, fisier in MODULE.items():
        s = (folder / fisier).read_text(encoding="utf-8")
        erou = un_singur(r'<section class="hero">(.*?)</section>', s, f"{fisier} hero")
        corp = corp_pagina(s, fisier)
        aplicat = ""
        m = re.search(r"<h2>De aplicat săptămâna asta</h2>(.*)$", corp, re.S)
        if m:
            aplicat = m.group(1).strip()
            corp = corp[:m.start()].rstrip()
        elif mid != "06":
            sys.exit(f"Curs: {fisier} nu are secțiunea „De aplicat săptămâna asta”.")
        if mid == "06":
            plan_exemple = [[html.unescape(c) for c in r] for r in re.findall(
                r"<tr><td>Exemplu: (.*?)</td><td>(.*?)</td><td>(.*?)</td>", corp)]
            if not plan_exemple:
                sys.exit("Curs: nu am găsit exemplele din planul de 90 de zile.")
            # Testul, grila și planul devin componente interactive ale ghidului.
            corp = re.sub(r"<h2>2\. Testul de verificare</h2>.*?</form>",
                          '<h2>2. Testul de verificare</h2><p>20 de întrebări, câte patru din fiecare modul. '
                          'Pragul de trecere este 16, cu minimum 2 din 4 la fiecare modul.</p>'
                          '<div data-widget="test-final"></div>', corp, flags=re.S)
            corp = re.sub(r'(<h2>3\. Planul de 90 de zile</h2>\s*<p>.*?</p>)\s*<div class="tscroll">.*?</table></div>',
                          r'\1<div data-widget="plan90"></div>', corp, count=1, flags=re.S)
            corp = re.sub(r'(<h2>2\. Testul)', r'<div data-widget="autoevaluare"></div>\1', corp, count=1)
            for w in ("test-final", "plan90", "autoevaluare"):
                if f'data-widget="{w}"' not in corp:
                    sys.exit(f"Curs: nu am găsit locul pentru „{w}” în 06-evaluare.html.")
        module.append({
            "id": mid,
            "kicker": html.unescape(re.sub(r"<[^>]+>", "", un_singur(r'<div class="kicker">(.*?)</div>', erou, f"{fisier} kicker"))),
            "titlu": html.unescape(un_singur(r"<h1>(.*?)</h1>", erou, f"{fisier} titlu")),
            "sub": html.unescape(un_singur(r'<p class="sub">(.*?)</p>', erou, f"{fisier} subtitlu")),
            "meta": [html.unescape(x) for x in re.findall(r"<span>(.*?)</span>", erou)],
            "html": corp,
            "aplicat": aplicat,
        })

    # Testul final: lista Q din scriptul paginii de evaluare.
    ev = (folder / MODULE["06"]).read_text(encoding="utf-8")
    intrebari = []
    for m, q, a, c in re.findall(r"\{m:'(.*?)',q:'(.*?)',a:\[(.*?)\],c:(\d)\}", ev):
        variante = [html.unescape(x) for x in re.findall(r"'(.*?)'", a)]
        intrebari.append({"modul": MODUL_INTREBARI[m], "q": html.unescape(q), "a": variante, "c": int(c)})
    explicatii = json.loads((folder / "explicatii.json").read_text(encoding="utf-8"))["explicatii"]
    if len(intrebari) != 20 or len(explicatii) != 20:
        sys.exit(f"Curs: am găsit {len(intrebari)} întrebări și {len(explicatii)} explicații (trebuie 20 și 20).")
    for i, e in zip(intrebari, explicatii):
        i["e"] = e
        if not 0 <= i["c"] < len(i["a"]):
            sys.exit(f"Curs: răspunsul corect lipsește la „{i['q']}”.")

    acasa = (folder / "index.html").read_text(encoding="utf-8")
    intro = corp_pagina(acasa, "index.html")
    intro = re.sub(r'<h2>Cum este construit cursul</h2>.*?<div class="grid">.*?</div>\s*</div>', "", intro, flags=re.S)
    return {"intro": intro, "module": module, "intrebari": intrebari, "plan_exemple": plan_exemple}


def cripteaza(date, parola):
    sare, iv = os.urandom(16), os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sare, iterations=ITERATII)
    cheie = kdf.derive(parola.encode("utf-8"))
    ct = AESGCM(cheie).encrypt(iv, json.dumps(date, ensure_ascii=False).encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": ITERATII, "salt": b64(sare), "iv": b64(iv), "ct": b64(ct)}


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    date = citeste(sys.argv[1])
    curs = citeste_curs(sys.argv[2])
    parola = os.environ.get("BB_PAROLA") or getpass.getpass("Parola echipei: ")
    parola_m = os.environ.get("BB_PAROLA_MANAGER") or getpass.getpass("Parola de manager (cursul): ")
    if len(parola) < 8 or len(parola_m) < 8:
        sys.exit("Parolele trebuie să aibă minimum 8 caractere.")
    if parola == parola_m:
        sys.exit("Parola de manager trebuie să fie diferită de parola echipei.")

    sablon = (ROOT / "src" / "template.html").read_text(encoding="utf-8")
    for semn in ("/*PAYLOAD*/null", "/*CURS*/null"):
        if sablon.count(semn) != 1:
            sys.exit(f"Șablonul trebuie să conțină exact o dată {semn}.")
    pagina = (sablon.replace("/*PAYLOAD*/null", json.dumps(cripteaza(date, parola)))
                    .replace("/*CURS*/null", json.dumps(cripteaza(curs, parola_m))))
    (ROOT / "index.html").write_text(pagina, encoding="utf-8")
    print(f"index.html scris: {len(date['procese'])} procese, {len(date['taskuri'])} task-uri, "
          f"{len(date['proceduri'])} proceduri, {len(date['roluri'])} roluri; "
          f"curs: {len(curs['module'])} module, {len(curs['intrebari'])} întrebări.")


if __name__ == "__main__":
    main()
