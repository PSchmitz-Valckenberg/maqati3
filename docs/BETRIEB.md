# Betrieb — Upload und Admin-Bereich

*Stand 2026-10-27. Genau die Schritte, die bei der Verifikation tatsächlich gelaufen sind.*

## Auf einen Server bringen (Docker Compose)

Getestet mit genau diesen Dateien (`deploy/`): am 2026-10-25 lokal (Arm, Chrome-Durchlauf,
208-MB-Video), am 2026-10-26 **auf einem echten Server** (Hetzner CPX12, x86, Ubuntu 26.04,
Docker 29.9): Build, Start, echtes Let's-Encrypt-Zertifikat über Caddy, Test-Uploads
(neu / identisch / neu kodierte Kopie / ohne Ton / Vorschau). Datenbank und Backend-Port
sind von außen nicht erreichbar. **Der Admin-Bereich** (Dashboard) ist am 2026-10-27 lokal getestet
(Chrome, echte Datenbank, ein Platzhalter statt Google) und noch **nicht auf dem Server**
eingespielt; er bleibt dort ohnehin zu, bis Domain und Google-Zugang eingerichtet sind.

1. **Server anlegen** (Hetzner Cloud Console): Ubuntu 24.04, Standort Nürnberg, Typ
   **CPX12** (1 vCPU, 2 GB RAM, 40 GB SSD; 11,49 €/Monat + 0,50 € IPv4, jeweils netto,
   dazu MwSt.). Gemessen am laufenden Stack: alle vier Container zusammen ~0,35 GB RAM,
   Frontend-Build in der Spitze ~0,35 GB, Images ~2,7 GB auf der Platte. Der kleinere
   CPX02 (1 GB, 20 GB) wäre zu knapp, besonders die Platte; CPX22 (19,49 €) bräuchten wir
   nicht. Später wächst man über Server-Upgrade oder ein Volume. SSH-Key hinterlegen.
   **Backups einschalten** (+20 %), bevor echte Uploads kommen: Der Server hält die einzige
   Kopie jedes Uploads, bis ein Admin ihn registriert. Danach einmal Swap anlegen (Puffer
   beim Image-Build, Standardbefehle, auf Hetzner nicht getestet):
   `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab`
2. **Domain**: A-Record auf die IPv4 des Servers setzen.
   *Vorläufig, solange der Projektname nicht feststeht:* kostenlos über duckdns.org (Login
   mit Google/GitHub, Namen wählen, Server-IP eintragen) und `DOMAIN=<name>.duckdns.org`.
   Nicht sslip.io/nip.io: beide stehen nicht auf der Public Suffix List und teilen sich
   das Let's-Encrypt-Limit mit allen Nutzern weltweit, das Zertifikat kann scheitern.
   Mit der echten Domain: `DOMAIN` in `.env` ändern, `docker compose up -d` — Daten
   bleiben, nur der Link ändert sich (den Brüdern neu geben). Ungetestet auf einem Server.
3. **Auf dem Server:**
   ```bash
   curl -fsSL https://get.docker.com | sh
   git clone https://github.com/PSchmitz-Valckenberg/maqati3.git /opt/maqati3 && cd /opt/maqati3/deploy
   cat > .env <<EOF
   DOMAIN=archiv.example.org
   POSTGRES_PASSWORD=$(openssl rand -hex 24)
   UPLOAD_KEY=$(openssl rand -base64 24 | tr '+/' '-_' | tr -d '=')
   EOF
   docker compose up -d --build
   ```
   Caddy holt das HTTPS-Zertifikat selbst, sobald die Domain auf den Server zeigt.
4. **Firewall** (Hetzner Console): nur 22, 80, 443 eingehend.
5. **Aktualisieren**: `git pull && docker compose up -d --build` — Migrationen laufen
   beim Start mit.

## Einstellungen (Backend)

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `DATABASE_URL` | ja | setzt `deploy/compose.yml` selbst |
| `UPLOAD_KEY` | ja | Der Schlüssel im Upload-Link. Ohne ihn startet der Server nicht. Ändern = alle alten Links ungültig. |
| `TRUST_FORWARDED_FOR` | nein | `true` nur hinter dem eigenen Reverse-Proxy (in `deploy/compose.yml` gesetzt). Falsche Upload-Schlüssel werden pro Absender begrenzt (30 pro 10 Minuten, danach 429); ohne diese Einstellung sieht der Server für alle die Adresse des Proxys. Ohne Proxy auf `true` gesetzt, lässt sich die Grenze mit einem selbst gesendeten Header umgehen. |
| `STAGING_DIR` | nein | Wo Uploads liegen, bis ein Admin sie registriert. Im Container `/var/lib/maqati3/staging` auf dem Volume `staging`. |
| `MAX_UPLOAD_BYTES` | nein | Standard 2 GiB je Datei (Caddy lässt bis 2 GB durch) |
| `FPCALC_PATH` | nein | Standard `fpcalc` (im Image enthalten) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | für den Admin-Bereich | Der OAuth-Client von Google, siehe unten |
| `PUBLIC_URL` | für den Admin-Bereich | Die Adresse der Seite, `https://<domain>`, ohne Pfad |
| `SESSION_SECRET` | für den Admin-Bereich | Signiert das Login-Cookie, mind. 32 Zeichen. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Ändern = alle Admins abgemeldet. |
| `SONIOX_API_KEY` | für die Transkription | Der Schlüssel des Anbieters. Leer: der Knopf im Dashboard antwortet 503 und der `worker`-Container startet nicht. |
| `SONIOX_MODEL` | nein | Standard `stt-async-v5`. |
| `TRANSCRIPTION_DAILY_MINUTES` | nein | Wie viele Audiominuten pro Tag zum Anbieter dürfen. Standard 600 (zehn Audiostunden, rund ein Dollar). Danach antwortet der Knopf 429 bis Mitternacht. |
| `UPLOAD_KEY_MAX_FAILURES` | nein | Falsche Upload-Schlüssel je Absender, bevor gesperrt wird. Standard 30. |
| `UPLOAD_KEY_WINDOW_MINUTES` | nein | Das Zeitfenster dazu. Standard 10. |

Die vier Admin-Werte gehören zusammen: **alle oder keine**. Keine → der Admin-Bereich ist
geschlossen (jede Adresse antwortet 503). Nur ein Teil → der Server startet nicht, mit
Meldung, welcher Wert fehlt.

## Ohne Docker (Entwicklung)

```bash
docker compose up -d --wait db   # nur die Datenbank, leer; Port belegt? DB_PORT=55432 ...
cd backend
export DATABASE_URL=postgresql://maqati3:devonly@127.0.0.1:5432/maqati3
uv run python -m maqati3 migrate && uv run python -m maqati3 seed
UPLOAD_KEY=dev STAGING_DIR=.staging uv run python -m maqati3 serve --port 8000
cd frontend && npm run dev   # leitet /api an :8000 weiter (API_ORIGIN, beim Build eingebacken)
```

Die Datenbank startet bewusst leer: das Schema legt `migrate` an, wie auf dem Server.
`STAGING_DIR` muss lokal gesetzt sein, sonst scheitert der erste Upload am Standardpfad
`/var/lib/maqati3/staging`.

Die Weiterleitung von Next kappt Uploads bei **10 MB** — nur in dieser Entwicklungs-Variante.
Auf dem Server geht `/api` über Caddy direkt zum Backend (208 MB getestet). Große Dateien
lokal deshalb direkt an Port 8000 schicken oder den Docker-Stack benutzen.

Braucht lokal `fpcalc` und `ffmpeg` (`brew install chromaprint ffmpeg`).

## Der Link für die Brüder

```
https://<domain>/ar/upload#k=<UPLOAD_KEY>
```

(`/en/` bzw. `/de/` für die anderen Sprachen.) Der Schlüssel steht hinter `#` und
erreicht deshalb nie Server-Logs oder Referrer. Nur in der Gruppe teilen.

## Der Admin-Bereich

Adresse: `https://<domain>/de/admin` (auch `/en/`, `/ar/`). Ablauf und Gründe:
`CLAUDE.md`, „The Admin Workflow“. Kurz: Admins melden sich mit Google an, sehen alle
behaltenen Uploads mit Player, wählen den Gelehrten und **registrieren** das Video (das legt
den Eintrag an, Zuschreibung bleibt „nicht sicher“) oder **verwerfen** es. Alles, was ein
Admin tut, steht mit seiner Adresse in der Tabelle `admin_log`.

### Einrichten (einmalig, ca. 15 Minuten, braucht die endgültige Domain)

Google trägt die Adresse der Seite fest ein; mit der vorläufigen DuckDNS-Adresse müsste
alles später neu gemacht werden.

1. <https://console.cloud.google.com> → ein Projekt (das aus `docs/SETUP-GOOGLE.md` oder ein neues).
2. **APIs & Dienste → OAuth-Zustimmungsbildschirm**: Nutzertyp *Extern*, App-Name und
   Support-E-Mail eintragen. Bereiche: nur `openid`, `email`, `profile` (nichts Sensibles).
   Solange der Status *Testing* ist, dürfen nur dort eingetragene **Testnutzer** hinein:
   die Admin-Adressen auch dort eintragen.
3. **Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID**, Typ **Webanwendung**
   (nicht „Desktop“ wie bei der Drive-Anleitung). *Autorisierte Weiterleitungs-URI*:
   `https://<domain>/api/v1/admin/auth/callback` — genau so, Zeichen für Zeichen.
4. Client-ID und Client-Secret kopieren und **nur** in die `.env` auf dem Server:
   ```
   GOOGLE_CLIENT_ID=…
   GOOGLE_CLIENT_SECRET=…
   PUBLIC_URL=https://<domain>
   SESSION_SECRET=<die erzeugte Zeichenfolge>
   ```
   Dann `docker compose up -d`. Das Secret nie in den Chat, ein Repository oder ein Foto.
5. Erste Admins eintragen (die **Google-Adresse**, mit der sich die Person anmeldet):
   ```bash
   cd /opt/maqati3/deploy
   docker compose exec api python -m maqati3 admin add name@gmail.com --name Vorname
   docker compose exec api python -m maqati3 admin list
   docker compose exec api python -m maqati3 admin remove name@gmail.com   # wirkt sofort
   ```

Wer nicht auf der Liste steht, kommt nicht hinein, auch mit gültigem Google-Konto; wer
entfernt wird, ist ab der nächsten Anfrage draußen.

### Transkription auf Knopfdruck

Bei einem registrierten Eintrag steht im Dashboard **Transkribieren**. Der Knopf stellt
nur einen Auftrag in die Warteschlange (`job`-Tabelle); gearbeitet wird im zweiten
Container, `worker`:

```bash
cd /opt/maqati3/deploy
docker compose logs -f worker
```

Im Dashboard steht an jedem registrierten Eintrag, wie es läuft: *angefragt*,
*wird transkribiert*, *hat nicht geklappt* (mit Grund) oder *Entwurf liegt bereit*. Die
Liste lädt sich dabei von selbst nach. Solange ein Lauf unterwegs ist, gibt es keinen
zweiten Knopf.

Was dabei gilt — die Gründe stehen in `CLAUDE.md`, „The Admin Workflow“:

* **Ein Lauf je Eintrag.** Solange einer läuft oder wartet, antwortet ein zweiter Klick
  409. ASR wird pro Audiostunde bezahlt, und zwei Läufe wären zwei Schreiber auf einer
  Zeitleiste.
* **Nie überschreiben.** Gibt es schon Zeilen oder arbeitet jemand am Arabischen, wird
  gar nicht erst angefragt. Kommt ein Ergebnis zu spät, wird es weggeworfen.
* **Der Entwurf ist nicht zitierbar.** Jede Zeile entsteht mit `span_role = unclear` und
  `citable = false`; Herkunft `asr`. Erst ein Mensch macht daraus Zitierbares.
* **Nichts bleibt beim Anbieter.** Datei und Transkription werden nach jedem Lauf dort
  wieder gelöscht.
* **Ohne Schlüssel ist zu.** Kein `SONIOX_API_KEY` → kein Knopf, kein Worker.
* **Eine Tagesgrenze fürs Geld.** `TRANSCRIPTION_DAILY_MINUTES` (Standard 600) begrenzt,
  wie viel Audio pro Tag zum Anbieter geht; gezählt wird, was *angefragt* wurde, nicht
  was gelang — ein gescheiterter Lauf wurde trotzdem geschickt und bezahlt. Zwei
  gleichzeitige Klicks können nicht beide durch: die Prüfung hält einen Advisory-Lock.
* **Nur der Ton geht hoch.** ffmpeg macht aus dem Handyvideo 24 kbit/s Mono-Opus; das
  Original wird nie angefasst, und die Zeitachse verschiebt sich nicht.
* **Sauberes Beenden.** `docker compose stop` schickt SIGTERM: der Lauf in Arbeit wird
  fertig, danach hört der Worker auf. Ein zweites Signal beendet sofort.

Ein Lauf ohne erkannte Wörter gilt als endgültig gescheitert und wird **nicht** vier
weitere Male bezahlt; der Grund steht in `job.last_error`, und man kann danach erneut
anfragen.

**Noch nie gegen den echten Dienst gelaufen** (wir haben keinen Schlüssel): Die
Aufrufformen stammen aus der Dokumentation von Soniox und sind gegen einen gefälschten
Transport getestet. Der erste echte Lauf gehört auf echtes Material, bevor irgendetwas
davon geglaubt wird.

### Ohne Dashboard: die Inbox auf dem Server

```bash
ssh root@<IP>                                      # ggf. -i <dein Schlüssel>
cd /opt/maqati3/deploy && docker compose exec api python -m maqati3 inbox
```

listet abgeschickte Uploads mit Datei und Absender und markiert die, die **trotz Treffer**
behalten wurden. Registrieren und Verwerfen geht nur im Dashboard.
