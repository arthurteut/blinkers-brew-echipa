# Blinkers Brew · Ghidul echipei

Pagina internă a echipei din taproom-ul Blinkers Brew (Strada Industriei nr. 7,
Timișoara): cine face, ce face, când și cum se verifică. Adresa:
**echipa.blinkersbrew.ro**.

## Ce conține

Construită din *Harta operațiunilor Blinkers Brew* (Excel), în stilul vizual
Blinkers: gri de afiș `#e7e7e4`, negru `#151515`, portocaliu de bere `#f09a1a`,
Archivo + Instrument Serif + DM Mono, logo-ul BB cu ochii care se mișcă.

- **Acasă**: căutare, starea de azi (deschis / închis, ultima comandă),
  momentele turei, rolurile și fișa locației (program, contacte, echipamente).
- **Procese** pe momentele turei (deschidere, în tură, închidere, săptămânal,
  situații speciale), cu filtru pe rol: task-urile rolului ales apar marcate.
- **Proceduri** pas cu pas (maximum 10 pași, un singur rol), filtrabile.
- **Fișa fiecărui rol**: Manager taproom, Vânzător, Preparator hot dog.
- **Căutare** pe tot conținutul, fără diacritice obligatorii (tasta `/`).

## Confidențialitate

Repo-ul e public (cerință GitHub Pages pe contul gratuit), dar conținutul **nu**:
tot ce e în ghid e criptat în `index.html` (AES-256-GCM, cheie derivată din
parola echipei cu PBKDF2-SHA256, 310.000 de iterații). Fără parolă se vede doar
ecranul de intrare. Excel-ul sursă nu se pune niciodată în repo (`.gitignore`).
Pagina e exclusă de la indexare (`robots.txt` + `noindex`).

Parola se împarte doar oral sau în grupul intern. Pe telefoanele și tabletele
din taproom, bifa „Ține-mă minte” păstrează accesul.

## Actualizare (conținut nou sau parolă nouă)

```bash
pip install openpyxl cryptography
python3 tools/build.py /cale/catre/Harta_Operatiuni_Blinkers_Brew.xlsx
# cere parola; apoi:
git add index.html && git commit -m "Actualizare ghid" && git push
```

- Conținutul (program, contacte, roluri, procese, task-uri, proceduri) se
  editează în Excel. Build-ul verifică harta și oprește dacă un task trimite la
  un proces, rol sau procedură care nu există.
- Aspectul se editează în `src/template.html`.
- Schimbarea parolei = rulezi build-ul cu parola nouă. Dispozitivele cu parola
  veche salvată vor cere din nou parola.

## Publicare

Detaliile pentru domeniu sunt în [`DNS-SETUP.md`](DNS-SETUP.md).
