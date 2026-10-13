# Listini ADM

Copia dei listini dei prezzi di vendita al pubblico dei tabacchi pubblicati dall'Agenzia delle Dogane e dei Monopoli
(https://www.adm.gov.it/portale/monopoli/tabacchi/prezzi/prezzi_pubblico), controllati in automatico due volte al
giorno.

- `indice.json` — elenco dei listini: nome, indirizzo sul sito ADM, impronta SHA-256, dimensione, data dell'ultimo
  cambio.
- `pdf/` — i PDF, uguali byte per byte a quelli del sito ADM.
- `aggiorna.py` — lo script che fa il controllo. Non legge il contenuto dei PDF.
- `.github/workflows/aggiorna.yml` — l'esecuzione automatica.

I documenti sono atti pubblici dell'ADM: questa è solo una copia di servizio, la fonte ufficiale resta il sito
dell'Agenzia. Nessun dato di negozi o clienti passa da qui.

## Se arriva un'email "Run failed"
La pagina dell'ADM è cambiata e lo script non trova più i listini. Fino alla correzione l'elenco resta quello
dell'ultimo controllo riuscito; nel gestionale i listini si possono sempre caricare a mano.
