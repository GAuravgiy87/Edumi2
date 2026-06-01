# EduMi2 — Docker Deployment

## Step 1 — Edit .env.docker

Open `.env.docker` and set **2 things**:

```env
SERVER_IP=192.168.1.100        # your machine's LAN IP  (run: ipconfig)
SECRET_KEY=some-long-random-string-here
```

Everything else has working defaults. Only change `POSTGRES_PASSWORD`,
`LIVEKIT_API_SECRET`, and `FACE_ENCRYPTION_KEY` if you want stronger security.

---

## Step 2 — Build and start (one command)

```bash
bash deploy.sh
```

The script will:
1. Check `.env.docker` exists
2. Stop any existing EduMi2 containers
3. **Check ports 80, 7880, 7881 — kill anything blocking them** (apache2, nginx, etc.)
4. Build images and start all 7 containers

First run takes ~5-10 minutes (downloads + installs packages).
After that, rebuilds take ~30 seconds (layers are cached).

---

## Step 3 — Create admin user

Wait ~30 seconds for migrations to finish:

```cmd
docker compose --env-file .env.docker exec web python manage.py createsuperuser
```

---

## Access

| Who | URL |
|---|---|
| Same machine | `http://localhost` |
| Students on LAN | `http://192.168.1.100` (your SERVER_IP) |
| Admin panel | `http://localhost/admin/` |

---

## Daily commands

```cmd
# Start
docker compose --env-file .env.docker up -d

# Stop
docker compose --env-file .env.docker down

# Status
docker compose --env-file .env.docker ps

# Live logs
docker compose --env-file .env.docker logs -f

# Logs for one service
docker compose --env-file .env.docker logs -f web
docker compose --env-file .env.docker logs -f camera_service

# Rebuild after code changes
docker compose --env-file .env.docker up -d --build web camera_service worker

# Full reset — DELETES all data
docker compose --env-file .env.docker down -v
```

---

## Allow students to connect (Windows Firewall)

Run once as Administrator:
```cmd
netsh advfirewall firewall add rule name="EduMi2" dir=in action=allow protocol=TCP localport=80
```
Or double-click `allow_firewall.bat`.
