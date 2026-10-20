#!/usr/bin/env python3
"""Construiește index.html din harta de operațiuni (Excel) + parola echipei.

Utilizare:
    pip install openpyxl cryptography
    python3 tools/build.py Harta_Operatiuni_Blinkers_Brew.xlsx

Parola se cere interactiv (sau din variabila BB_PAROLA). Conținutul e criptat
AES-256-GCM cu o cheie derivată din parolă (PBKDF2-SHA256), așa că în repo
ajunge doar textul criptat. Excel-ul NU se pune în repo.
"""
import base64
import getpass
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


def cripteaza(date, parola):
    sare, iv = os.urandom(16), os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sare, iterations=ITERATII)
    cheie = kdf.derive(parola.encode("utf-8"))
    ct = AESGCM(cheie).encrypt(iv, json.dumps(date, ensure_ascii=False).encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": ITERATII, "salt": b64(sare), "iv": b64(iv), "ct": b64(ct)}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    date = citeste(sys.argv[1])
    parola = os.environ.get("BB_PAROLA") or getpass.getpass("Parola echipei: ")
    if len(parola) < 8:
        sys.exit("Parola trebuie să aibă minimum 8 caractere.")

    sablon = (ROOT / "src" / "template.html").read_text(encoding="utf-8")
    html = sablon.replace("/*PAYLOAD*/null", json.dumps(cripteaza(date, parola)))
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html scris: {len(date['procese'])} procese, {len(date['taskuri'])} task-uri, "
          f"{len(date['proceduri'])} proceduri, {len(date['roluri'])} roluri.")


if __name__ == "__main__":
    main()
