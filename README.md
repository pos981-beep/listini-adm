# Listini ADM

Copia dei listini dei prezzi di vendita al pubblico dei tabacchi pubblicati dall'Agenzia delle Dogane e dei Monopoli
(https://www.adm.gov.it/portale/monopoli/tabacchi/prezzi/prezzi_pubblico), controllati in automatico due volte al
giorno.

- `indice.json` — elenco dei listini: nome, indirizzo sul sito ADM, impronta SHA-256, dimensione, data dell'ultimo
  cambio.
- `pdf/` — i PDF, uguali byte per byte a quelli del sito ADM.
- `determinazioni/` — le ultime determinazioni ADM di variazione dei prezzi (PDF ufficiali), che spesso escono prima
  dei listini completi aggiornati.
- `gratta_e_vinci.json` — i Gratta e Vinci in vendita (lotterie istantanee attive dell'ADM): nome, costo del
  biglietto, codici del gioco presi dalle immagini dei biglietti, pagina ADM.
- `aggiorna.py` — lo script che controlla i listini. Non legge il contenuto dei PDF.
- `gratta_e_vinci.py` — lo script che legge l'elenco dei Gratta e Vinci attivi.
- `.github/workflows/aggiorna.yml` — l'esecuzione automatica.

I documenti sono atti pubblici dell'ADM: questa è solo una copia di servizio, la fonte ufficiale resta il sito
dell'Agenzia. Nessun dato di negozi o clienti passa da qui.

## Se arriva un'email "Run failed"
La pagina dell'ADM è cambiata e lo script non trova più i listini. Fino alla correzione l'elenco resta quello
dell'ultimo controllo riuscito; nel gestionale i listini si possono sempre caricare a mano.
Se si ferma solo il passo "Elenco dei Gratta e Vinci", i listini si aggiornano lo stesso e `gratta_e_vinci.json` resta
quello dell'ultimo controllo riuscito; nel gestionale i Gratta e Vinci si possono sempre creare a mano.
