# docs/DEPLOY.md — pocket-dnd

Due modalita' di deploy, lo stesso container in entrambe.

> Filosofia (vedi `DECISIONS.md` D4, D5): un solo processo, un solo file
> SQLite, una sola porta. La differenza tra "casa" e "pub" non e' nel
> container: e' soltanto in chi gli mette davanti la rete.

## Quick start

```bash
# build + run sulla devbox/laptop/nodo k3s
docker compose up -d --build

# popola la SRD una sola volta (poi il volume tiene la persistenza)
docker compose exec pocket-dnd python3 scripts/seed_srd.py /data/pocket-dnd.db

# apri http://localhost:8000
```

Per esporre in LAN locale (modalita' pub):

```bash
# basta l'IP del laptop sulla rete dell'hotspot
ip addr show | grep 'inet '
# es. 10.5.0.1 — i telefoni vanno su http://10.5.0.1:8000
```

Il container fa gia' bind su `0.0.0.0:8000`, niente da configurare.

## Modalita' casa — Cloudflare Tunnel

L'idea: un sottodominio (es. `dnd.tuodominio.it`) → Cloudflare Tunnel
→ `pocket-dnd:8000` dentro la rete docker locale.

Una sola macchina deve girare `cloudflared`. Tre modi per farlo, tutti
equivalenti dal punto di vista di pocket-dnd:

### Opzione A — cloudflared di sistema (semplice)

Installa `cloudflared` sull'host (devbox o nodo k3s), poi:

```bash
cloudflared tunnel login
cloudflared tunnel create pocket-dnd          # salva l'UUID del tunnel
cloudflared tunnel route dns pocket-dnd dnd.tuodominio.it
```

Crea `~/.cloudflared/config.yml`:

```yaml
tunnel: <UUID-del-tunnel>
credentials-file: /home/<utente>/.cloudflared/<UUID>.json

ingress:
  - hostname: dnd.tuodominio.it
    service: http://localhost:8000
  - service: http_status:404
```

Avvia:

```bash
cloudflared tunnel run pocket-dnd
# oppure come systemd: sudo cloudflared service install
```

### Opzione B — cloudflared accanto a pocket-dnd via compose

Aggiungi al `docker-compose.yml` (qui in repo) un secondo service. Tieni
il token in un file `.env` **fuori dal repo** (gia' nel `.gitignore` per
default — verifica che `.env` non venga committato):

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: pocket-dnd-tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token ${CF_TUNNEL_TOKEN}
    depends_on:
      - pocket-dnd
    environment:
      CF_TUNNEL_TOKEN: ${CF_TUNNEL_TOKEN}
```

Lato Cloudflare (dashboard "Zero Trust" → Tunnels):
1. crea un tunnel (modalita' "Cloudflared", connector via container)
2. copia il token, mettilo in `.env` come `CF_TUNNEL_TOKEN=...`
3. nella sezione "Public Hostname" del tunnel:
   - Subdomain: `dnd` (o quello che vuoi)
   - Domain: `tuodominio.it`
   - Service: `http://pocket-dnd:8000` (nome del service compose, non
     `localhost`: i container si vedono per nome nella rete compose)

`docker compose up -d` e basta.

### Opzione C — gia' hai un cloudflared che gira

Aggiungi al `config.yml` del tunnel esistente una entry:

```yaml
  - hostname: dnd.tuodominio.it
    service: http://<ip-host-pocket-dnd>:8000
```

E `cloudflared tunnel route dns <tunnel-name> dnd.tuodominio.it`.

## WebSocket dietro Cloudflare

Niente da fare lato app: Cloudflare passa i WS in modo trasparente per
qualsiasi piano (Free incluso). Il client di pocket-dnd usa il protocollo
sulla stessa origin (`new WebSocket(<wss>://${host}/ws/...)`), quindi
funziona out-of-the-box.

## Persistenza

Il volume `pocket-dnd-data` montato su `/data` tiene il file SQLite.
Backup banale:

```bash
docker compose exec pocket-dnd sqlite3 /data/pocket-dnd.db ".backup /data/backup.db"
docker cp pocket-dnd:/data/backup.db ./pocket-dnd-$(date +%F).db
```

## Aggiornamento

```bash
git pull
docker compose build
docker compose up -d
# se cambia lo schema: il backend lo applica con CREATE IF NOT EXISTS,
# le tabelle nuove vengono create al riavvio. Migrazioni distruttive
# (rinomine, drop) richiedono passo manuale.
```

## Cosa NON committare

- `.env` con `CF_TUNNEL_TOKEN`
- credenziali in `~/.cloudflared/`
- il file SQLite con i tuoi PG (se lo provi in locale)
