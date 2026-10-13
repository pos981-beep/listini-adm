#!/usr/bin/env python3
"""
Controlla la pagina ufficiale dell'ADM con i prezzi di vendita al pubblico dei tabacchi e tiene una copia dei
listini (PDF) con un elenco che l'app sa leggere.

Cosa fa:
  1. scarica la pagina dell'ADM e trova i collegamenti ai listini PDF;
  2. scarica ogni PDF nella cartella "pdf";
  3. scrive "indice.json": per ogni listino nome, indirizzo sul sito ADM, impronta (SHA-256) e dimensione;
  4. fa lo stesso con le ultime determinazioni di "Variazione del prezzo" (cartella "determinazioni"): l'ADM le
     pubblica quando cambia il prezzo di alcune marche, spesso prima di aggiornare i listini completi.

Non legge il contenuto dei PDF: prezzi e articoli li legge l'app, con il suo lettore e la sua anteprima.
Se la pagina cambia e i listini non si trovano più, lo script si ferma con un errore (GitHub avvisa per email).

Uso:
  python aggiorna.py                 scarica tutto e aggiorna indice.json
  python aggiorna.py --solo-elenco   mostra solo i listini trovati nella pagina, senza scaricare i PDF
  python aggiorna.py --pagina file   legge la pagina da un file salvato (per le prove)
"""
import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAGINA = "https://www.adm.gov.it/portale/monopoli/tabacchi/prezzi/prezzi_pubblico"
DETERMINAZIONI = "https://www.adm.gov.it/portale/tabacchi-determinazioni-provvedimenti-gu"
QUI = Path(__file__).resolve().parent
# Quante determinazioni di variazione dei prezzi tenere nell'elenco, e di quanti giorni al massimo.
DETERMINAZIONI_DA_TENERE = 6
GIORNI_DETERMINAZIONI = 45
# Meno di così vuol dire che la pagina è cambiata: meglio fermarsi che pubblicare un elenco monco.
MINIMO_LISTINI = 6
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (listini-adm; controllo giornaliero dei listini pubblici)"}

# Parole dell'etichetta sulla pagina -> nome breve del file. L'ordine conta: "sigaretti" prima di "sigarette".
CATEGORIE = [
    ("inalazione", "inalazione"),
    ("sigaretti", "sigaretti"),
    ("sigarette", "sigarette"),
    ("sigari", "sigari"),
    ("fiuto", "fiuto_mastico"),
    ("trinciati", "trinciati"),
    ("altri tabacchi", "altri_tabacchi"),
]

COLLEGAMENTO = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)


def scarica(indirizzo: str) -> bytes:
    richiesta = urllib.request.Request(indirizzo, headers=INTESTAZIONI)
    with urllib.request.urlopen(richiesta, timeout=60) as risposta:
        return risposta.read()


def listini_nella_pagina(pagina: str) -> list[dict]:
    """I listini PDF trovati nella pagina: nome breve, etichetta, indirizzo completo."""
    trovati: dict[str, dict] = {}
    for m in COLLEGAMENTO.finditer(pagina):
        indirizzo = html.unescape(m.group(1))
        etichetta = re.sub(r"<[^>]+>|\s+", " ", html.unescape(m.group(2))).strip()
        if ".pdf" not in indirizzo.lower() or "/documents/" not in indirizzo:
            continue
        minuscolo = etichetta.lower()
        nome = next((breve for parola, breve in CATEGORIE if parola in minuscolo), None)
        if nome is None or nome in trovati:
            continue
        trovati[nome] = {
            "nome": nome,
            "etichetta": etichetta.replace(" - pdf", "").strip(),
            "origine": urllib.parse.urljoin(PAGINA, indirizzo),
        }
    return list(trovati.values())


TITOLO_DETERMINAZIONE = re.compile(r"\[\s*(\d+)(?:/RU)?\s+del\s+(\d{2})/(\d{2})/(\d{4})\s*\]", re.I)


def determinazioni_nella_pagina(pagina: str, oggi: datetime) -> list[dict]:
    """Le ultime determinazioni di variazione dei prezzi: numero, data, etichetta e indirizzo del PDF."""
    trovate: dict[str, dict] = {}
    for m in COLLEGAMENTO.finditer(pagina):
        indirizzo = html.unescape(m.group(1))
        etichetta = re.sub(r"<[^>]+>|\s+", " ", html.unescape(m.group(2))).strip()
        if ".pdf" not in indirizzo.lower() or "/documents/" not in indirizzo:
            continue
        titolo = TITOLO_DETERMINAZIONE.search(etichetta)
        if not titolo or "variazione del prezzo" not in etichetta.lower():
            continue
        numero, giorno, mese, anno = titolo.groups()
        data = datetime(int(anno), int(mese), int(giorno), tzinfo=timezone.utc)
        if (oggi - data).days > GIORNI_DETERMINAZIONI or numero in trovate:
            continue
        marche = re.search(r"di\s+(\d+)\s+marc", etichetta, re.I)
        trovate[numero] = {
            "nome": f"determinazione_{numero}",
            "etichetta": f"Variazione prezzi del {giorno}/{mese}/{anno}" + (f" ({marche.group(1)} marche)" if marche else ""),
            "origine": urllib.parse.urljoin(DETERMINAZIONI, indirizzo),
            "data": f"{anno}-{mese}-{giorno}",
        }
    return sorted(trovate.values(), key=lambda x: x["data"], reverse=True)[:DETERMINAZIONI_DA_TENERE]


def main() -> int:
    opzioni = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni.add_argument("--solo-elenco", action="store_true")
    opzioni.add_argument("--pagina")
    opzioni.add_argument("--pagina-determinazioni")
    scelte = opzioni.parse_args()

    testo = Path(scelte.pagina).read_text(encoding="utf-8", errors="ignore") if scelte.pagina else scarica(PAGINA).decode("utf-8", errors="ignore")
    listini = listini_nella_pagina(testo)
    if len(listini) < MINIMO_LISTINI:
        print(f"ERRORE: trovati solo {len(listini)} listini nella pagina dell'ADM (attesi almeno {MINIMO_LISTINI}). "
              "La pagina è cambiata: va aggiornato lo script.", file=sys.stderr)
        return 1
    # Le determinazioni sono un aiuto in più: se la loro pagina non risponde o cambia, i listini si aggiornano lo stesso.
    try:
        testo_det = (Path(scelte.pagina_determinazioni).read_text(encoding="utf-8", errors="ignore")
                     if scelte.pagina_determinazioni else scarica(DETERMINAZIONI).decode("utf-8", errors="ignore"))
        determinazioni = determinazioni_nella_pagina(testo_det, datetime.now(timezone.utc))
    except Exception as errore:  # noqa: BLE001
        print(f"ATTENZIONE: determinazioni non lette ({errore})", file=sys.stderr)
        determinazioni = None
    if scelte.solo_elenco:
        for x in listini + (determinazioni or []):
            print(f'{x["nome"]:22} {x["etichetta"]:45} {x["origine"]}')
        return 0

    cartella = QUI / "pdf"
    cartella.mkdir(exist_ok=True)
    file_indice = QUI / "indice.json"
    precedente = json.loads(file_indice.read_text(encoding="utf-8")) if file_indice.exists() else {}
    prima = {x["nome"]: x for x in precedente.get("listini", [])}
    adesso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cambiati = 0
    for x in listini:
        dati = scarica(x["origine"])
        if not dati.startswith(b"%PDF"):
            print(f'ERRORE: {x["nome"]} non è un PDF ({len(dati)} byte).', file=sys.stderr)
            return 1
        x["file"] = f'pdf/{x["nome"]}.pdf'
        x["sha256"] = hashlib.sha256(dati).hexdigest()
        x["byte"] = len(dati)
        vecchio = prima.get(x["nome"])
        if vecchio and vecchio.get("sha256") == x["sha256"]:
            x["cambiato_il"] = vecchio.get("cambiato_il", adesso)
        else:
            x["cambiato_il"] = adesso
            cambiati += 1
            (QUI / x["file"]).write_bytes(dati)
            print(f'nuovo: {x["etichetta"]} ({len(dati)} byte)')
    # determinazioni: stesse regole dei listini; se oggi la pagina non si è letta si tengono quelle di prima
    prima_det = {x["nome"]: x for x in precedente.get("determinazioni", [])}
    if determinazioni is None:
        determinazioni = list(prima_det.values())
    else:
        (QUI / "determinazioni").mkdir(exist_ok=True)
        for x in determinazioni:
            vecchio = prima_det.get(x["nome"])
            if vecchio and vecchio.get("origine") == x["origine"]:
                x.update({k: vecchio[k] for k in ("file", "sha256", "byte", "cambiato_il") if k in vecchio})
                continue
            dati = scarica(x["origine"])
            if not dati.startswith(b"%PDF"):
                print(f'ATTENZIONE: {x["nome"]} non è un PDF, saltata', file=sys.stderr)
                continue
            x["file"] = f'determinazioni/{x["nome"].split("_")[1]}.pdf'
            x["sha256"] = hashlib.sha256(dati).hexdigest()
            x["byte"] = len(dati)
            x["cambiato_il"] = adesso
            cambiati += 1
            (QUI / x["file"]).write_bytes(dati)
            print(f'nuova: {x["etichetta"]} ({len(dati)} byte)')
        determinazioni = [x for x in determinazioni if "sha256" in x]
    indice = {"versione": 1, "fonte": PAGINA, "controllato_il": adesso, "listini": sorted(listini, key=lambda x: x["nome"]),
              "determinazioni": determinazioni}
    # "controllato_il" cambia a ogni giro: si riscrive il file solo se è cambiato un listino, o una volta al giorno
    if cambiati or precedente.get("controllato_il", "")[:10] != adesso[:10]:
        file_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(listini)} listini controllati, {cambiati} cambiati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
