# EduMi2 Server Requirements

- **Operating System:** Windows 11 (Docker Desktop)
- **Docker Desktop** (includes Docker Engine & Docker‑Compose)
- **Python:** 3.11
- **pip:** latest (`python -m pip install --upgrade pip`)

## 🖥️ Hardware Requirements
- **Cores**: 8 or more (video‑processing services such as LiveKit, ffmpeg, video_editing, live_stream benefit from additional cores).
- **Memory (RAM)**: Minimum **32 GB** (recommended 64 GB for high‑load production serving up to 10 000 concurrent users).
- **Storage**:
  - **Base application code & Docker images**: ~5 GB.
  - **PostgreSQL data volume**: Allocate **≥100 GB** (to accommodate user data and meeting logs).
  - **Video assets / recordings**: Allocate **≥1 TB** (for large media archives and recordings).
- **GPU (optional but highly recommended)**: Modern NVIDIA GPU with CUDA support (e.g., GTX 1660 or better) for accelerated video encoding/decoding in `video_editing` and `live_stream` services.


## 🛠️ Required Software

- **Docker Desktop** (includes Docker Engine ≥ 20.10 and Docker‑Compose v2)
- **Python** 3.11 with the latest `pip`


## 📦 Server Software Requirements

- Operating System (Windows 11 with Docker Desktop **or** modern Linux)
- Docker Engine ≥ 20.10
- Docker‑Compose v2
- Python 3.11 and `pip`
- PostgreSQL 15 client libraries (`libpq-dev` for building `psycopg2`)
- Redis server
- LiveKit server binary (Docker image pulls automatically)
- Nginx (optional for TLS termination)
- FFmpeg ≥ 5.0 (installed in Docker image for video processing)
- Git (for source control)
- NVIDIA drivers & CUDA toolkit (if GPU acceleration is required)


## 📦 Installing the Stack (quick guide)
1. **Docker Desktop** – download from https://www.docker.com/products/docker-desktop and follow the installer.
2. **Clone the repository** (if not already local):
   ```powershell
   git clone <repo‑url> "C:\Users\hp\Desktop\Edumi2-my-work2"
   ```
3. **Python (local dev only)** – `python -m venv venv && .\venv\Scripts\activate && pip install -r requirements.txt`
4. **Build & launch containers**:
   ```powershell
   cd C:\Users\hp\Desktop\Edumi2-my-work2
   docker compose build
   docker compose up -d   # starts db, redis, livekit, all micro‑services, nginx, celery
   ```
5. **Verify** – `docker compose ps` should show all services **Up**.  Check DB: `docker exec -it edumi_db psql -U edumi_user -d edumi_db -c "\dt"`.
6. **Persisted data** – PostgreSQL data lives in `./postgres_data`; do not delete this folder.
7. **Optional** – Place TLS certificates in `certs/` and configure `nginx/conf.d/` for HTTPS.

## 📝 Notes
- All containers share the same `.env` file, which already points to Docker service names (`db`, `redis`, `livekit`).
- If you run the app **without Docker**, install PostgreSQL and Redis locally and set `DATABASE_URL` and `REDIS_URL` accordingly.
- For GPU‑accelerated video processing on Linux, expose the GPU to the container (e.g., `--gpus all` in the compose file) and install NVIDIA drivers on the host.
- Regularly back‑up `./postgres_data` and any `./staticfiles`/`./media` directories.
