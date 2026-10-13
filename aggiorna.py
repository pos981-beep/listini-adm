#!/usr/bin/env python3
"""
Controlla la pagina ufficiale dell'ADM con i prezzi di vendita al pubblico dei tabacchi e tiene una copia dei
listini (PDF) con un elenco che l'app sa leggere.

Cosa fa:
  1. scarica la pagina dell'ADM e trova i collegamenti ai listini PDF;
  2. scarica ogni PDF nella cartella "pdf";
  3. scrive "indice.json": per ogni listino nome, indirizzo sul sito ADM, impronta (SHA-256) e dimensione.

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
QUI = Path(__file__).resolve().parent
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


def main() -> int:
    opzioni = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni.add_argument("--solo-elenco", action="store_true")
    opzioni.add_argument("--pagina")
    scelte = opzioni.parse_args()

    testo = Path(scelte.pagina).read_text(encoding="utf-8", errors="ignore") if scelte.pagina else scarica(PAGINA).decode("utf-8", errors="ignore")
    listini = listini_nella_pagina(testo)
    if len(listini) < MINIMO_LISTINI:
        print(f"ERRORE: trovati solo {len(listini)} listini nella pagina dell'ADM (attesi almeno {MINIMO_LISTINI}). "
              "La pagina è cambiata: va aggiornato lo script.", file=sys.stderr)
        return 1
    if scelte.solo_elenco:
        for x in listini:
            print(f'{x["nome"]:16} {x["etichetta"]:45} {x["origine"]}')
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
    indice = {"versione": 1, "fonte": PAGINA, "controllato_il": adesso, "listini": sorted(listini, key=lambda x: x["nome"])}
    # "controllato_il" cambia a ogni giro: si riscrive il file solo se è cambiato un listino, o una volta al giorno
    if cambiati or precedente.get("controllato_il", "")[:10] != adesso[:10]:
        file_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(listini)} listini controllati, {cambiati} cambiati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
