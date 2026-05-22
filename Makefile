# pocket-dnd — Makefile
.PHONY: seed test clean

DB ?= backend/pocket-dnd.db

seed:          ## Popola il DB con i dati SRD
	cd backend && python3 scripts/seed_srd.py $(notdir $(DB))

test:          ## Esegue la suite di test del backend
	cd backend && python3 -m pytest tests/ -v

clean:         ## Rimuove il DB generato
	rm -f $(DB) $(DB)-journal $(DB)-wal
