# Blinkers Brew · Ghidul echipei

Pagina internă a echipei din taproom-ul Blinkers Brew (Strada Industriei nr. 7,
Timișoara): cine face, ce face, când și cum se verifică. Adresa:
**echipa.blinkersbrew.com**.

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
- **Curs manager** (Blinkers Brew × Around The Corner Development), cu parolă
  separată: 7 module deblocate pe rând. Fiecare modul se termină când e citit,
  mini-testul e trecut (minimum 3/4, cu explicații) și sarcina săptămânii e
  aplicată în taproom (cu o notă). La final: autoevaluarea, testul de 20 de
  întrebări (prag 16) și planul de 90 de zile. Checklist-urile și
  calculatoarele din curs își păstrează bifele și valorile.

## Confidențialitate

Repo-ul e public (cerință GitHub Pages pe contul gratuit), dar conținutul **nu**:
tot ce e în ghid e criptat în `index.html` (AES-256-GCM, cheie derivată din
parola echipei cu PBKDF2-SHA256, 310.000 de iterații). Fără parolă se vede doar
ecranul de intrare. Excel-ul sursă nu se pune niciodată în repo (`.gitignore`).
Pagina e exclusă de la indexare (`robots.txt` + `noindex`).

Cursul de manager e criptat separat, cu **parola de manager** (alta decât
parola echipei), pentru că are cifrele locației.

Progresul cursului se ține pe telefon și se sincronizează în Supabase (proiectul
`atc-toolkit`, tabelul `blinkers_curs_progres`, vezi `supabase/`), ca să-l vadă
și Arthur de pe alt dispozitiv. Tabelul nu se poate citi direct: doar prin două
funcții care cer o cheie derivată din parola de manager. Adresa proiectului și
cheia publică din `src/template.html` sunt publice prin design.

Parolele se împart doar oral sau în grupul intern. Pe telefoanele și tabletele
din taproom, bifa „Ține-mă minte” păstrează accesul.

## Actualizare (conținut nou sau parolă nouă)

```bash
pip install openpyxl cryptography
python3 tools/build.py /cale/catre/Harta_Operatiuni_Blinkers_Brew.xlsx /cale/catre/curs-manager/
# cere parola echipei și parola de manager; apoi:
git add index.html && git commit -m "Actualizare ghid" && git push
```

- Conținutul (program, contacte, roluri, procese, task-uri, proceduri) se
  editează în Excel. Build-ul verifică harta și oprește dacă un task trimite la
  un proces, rol sau procedură care nu există.
- Cursul se editează în folderul lui (paginile HTML din arhiva ATC +
  `explicatii.json` cu explicațiile de la mini-teste). Nici el nu intră în repo.
- Aspectul se editează în `src/template.html`.
- Schimbarea parolei = rulezi build-ul cu parola nouă. Dispozitivele cu parola
  veche salvată vor cere din nou parola. La parola de manager se actualizează și
  `cheie_hash` în Supabase (comanda e în `supabase/blinkers_curs_progres.sql`),
  altfel progresul nu se mai poate salva online.

## Publicare

Detaliile pentru domeniu sunt în [`DNS-SETUP.md`](DNS-SETUP.md).
