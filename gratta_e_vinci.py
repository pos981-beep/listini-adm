#!/usr/bin/env python3
"""
Elenco dei Gratta e Vinci in vendita (lotterie istantanee attive) dalle pagine ufficiali dell'ADM, in un file che
l'app sa leggere: "gratta_e_vinci.json".

Cosa fa:
  1. legge l'elenco delle lotterie istantanee attive (tutte le pagine dell'elenco);
  2. apre la pagina di ogni gioco e prende il costo del biglietto ("COSTO DEL BIGLIETTO 20,00 Euro");
  3. prende i codici del gioco (4 cifre, le stesse stampate sotto il codice a barre dei biglietti) dai nomi delle
     immagini dei biglietti, per esempio "GVI-3117+100X+New...jpg" -> 3117. Una pagina può avere più edizioni dello
     stesso gioco: si tengono tutte, la più usata per prima.

Non cambia nulla nel gestionale: è l'app a confrontare l'elenco con i suoi articoli (stesso gioco con nomi diversi,
giochi nuovi, giochi chiusi) e a mostrare l'anteprima.
Se l'elenco ha troppi pochi giochi la pagina è cambiata: lo script si ferma con un errore (GitHub avvisa per email)
e il file resta quello dell'ultimo controllo riuscito.

Uso:
  python gratta_e_vinci.py              aggiorna gratta_e_vinci.json
  python gratta_e_vinci.py --solo-elenco    mostra i giochi trovati senza scrivere il file
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ELENCO = "https://www.adm.gov.it/portale/monopoli/giochi/lotterie/lotterie_istantanee/lot_ist_attive"
SITO = "https://www.adm.gov.it"
QUI = Path(__file__).resolve().parent
INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (listini-adm; controllo giornaliero dei Gratta e Vinci attivi)"}
MINIMO_GIOCHI = 20
MASSIMO_PAGINE = 20

VOCE = re.compile(r'<a[^>]+class="lottery-item-link[^"]*"[^>]+href="([^"]+)"[^>]*>.*?<span[^>]*>(.*?)</span>', re.S | re.I)
PAGINA_ELENCO = re.compile(r'href="([^"]*lot_ist_attive\?[^"]*_cur=(\d+)[^"]*)"', re.I)
IMMAGINE = re.compile(r'<img[^>]+src="(/portale/documents/[^"]+)"', re.I)
COSTO = re.compile(r"COSTO DEL BIGLIETTO\s*:?\s*(?:€|euro)?\s*(\d{1,3}(?:,\d{2})?)\s*(?:€|euro)?", re.I)
CODICE = re.compile(r"(?<!\d)([35]\d{3})(?!\d)")


def scarica(indirizzo: str) -> str:
    for tentativo in range(3):
        try:
            richiesta = urllib.request.Request(indirizzo, headers=INTESTAZIONI)
            with urllib.request.urlopen(richiesta, timeout=60) as risposta:
                return risposta.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            if tentativo == 2:
                raise
            time.sleep(3)
    return ""


def testo(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def giochi_nell_elenco() -> list[dict]:
    """Nome e pagina di ogni gioco, da tutte le pagine dell'elenco."""
    trovati: dict[str, dict] = {}
    da_leggere, lette = [ELENCO], set()
    while da_leggere and len(lette) < MASSIMO_PAGINE:
        indirizzo = da_leggere.pop(0)
        if indirizzo in lette:
            continue
        lette.add(indirizzo)
        pagina = scarica(indirizzo)
        for href, nome in VOCE.findall(pagina):
            pagina_gioco = urllib.parse.urljoin(SITO, html.unescape(href))
            trovati.setdefault(pagina_gioco, {"nome": testo(nome).strip("“”\" "), "pagina": pagina_gioco})
        numeri_letti = {re.search(r"_cur=(\d+)", x).group(1) for x in lette if "_cur=" in x} | {"1"}
        for href, numero in PAGINA_ELENCO.findall(pagina):
            if numero not in numeri_letti:
                da_leggere.append(urllib.parse.urljoin(SITO, html.unescape(href)))
                numeri_letti.add(numero)
    return list(trovati.values())


def dettagli(gioco: dict) -> dict:
    pagina = scarica(gioco["pagina"])
    corpo = re.sub(r"<script.*?</script>|<style.*?</style>", "", pagina, flags=re.S)
    m = COSTO.search(testo(corpo))
    prezzo = int(round(float(m.group(1).replace(",", ".")) * 100)) if m else None
    nomi_immagini = [urllib.parse.unquote(src.split("/")[5]) for src in IMMAGINE.findall(pagina) if len(src.split("/")) > 5]
    conta = Counter(c for nome in nomi_immagini for c in set(CODICE.findall(nome)))
    codici = [c for c, _ in sorted(conta.items(), key=lambda x: (-x[1], -int(x[0])))]
    return {**gioco, "prezzo": prezzo, "codici": codici}


def main() -> int:
    opzioni = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opzioni.add_argument("--solo-elenco", action="store_true")
    scelte = opzioni.parse_args()

    elenco = giochi_nell_elenco()
    if len(elenco) < MINIMO_GIOCHI:
        print(f"ERRORE: trovati solo {len(elenco)} Gratta e Vinci nell'elenco dell'ADM (attesi almeno {MINIMO_GIOCHI}). "
              "La pagina è cambiata: va aggiornato lo script.", file=sys.stderr)
        return 1
    giochi = []
    for g in elenco:
        try:
            giochi.append(dettagli(g))
        except Exception as errore:  # noqa: BLE001
            print(f'ATTENZIONE: {g["nome"]}: pagina non letta ({errore})', file=sys.stderr)
            giochi.append({**g, "prezzo": None, "codici": []})
        time.sleep(0.5)
    giochi.sort(key=lambda x: (x["prezzo"] or 0, x["nome"].lower()))
    if scelte.solo_elenco:
        for g in giochi:
            print(f'{(g["prezzo"] or 0) / 100:6.2f} € {g["nome"]:32} {", ".join(g["codici"]) or "-"}')
        return 0
    senza_prezzo = sum(1 for g in giochi if g["prezzo"] is None)
    if senza_prezzo > len(giochi) // 2:
        print(f"ERRORE: {senza_prezzo} giochi senza costo del biglietto: le pagine dei giochi sono cambiate.", file=sys.stderr)
        return 1

    file = QUI / "gratta_e_vinci.json"
    precedente = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    adesso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cambiato = precedente.get("giochi") != giochi
    dati = {"versione": 1, "fonte": ELENCO, "controllato_il": adesso,
            "cambiato_il": adesso if cambiato else precedente.get("cambiato_il", adesso), "giochi": giochi}
    # come per i listini: si riscrive se è cambiato qualcosa, o una volta al giorno
    if cambiato or precedente.get("controllato_il", "")[:10] != adesso[:10]:
        file.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(giochi)} Gratta e Vinci attivi" + (", elenco cambiato" if cambiato else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
