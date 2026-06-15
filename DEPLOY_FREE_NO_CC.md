# Deploy EduMi2 for FREE (No Credit Card Required!)
---

## 1. Complete Service List & Deployment Plan
Here's every service and where we'll host it:

| Service | Purpose | Host |
|---------|---------|------|
| **Main Django App** | Core web UI/API | Render (Free Web Service) |
| **Celery Worker** | Background tasks | Render (Free Web Service — runs in background of main app) |
| **Camera Service** | Computer vision (face recognition) | Render (Free Web Service) |
| **LiveKit SFU** | Video conferencing (WebRTC) | LiveKit Cloud (Free Tier) |
| **Redis** | Message broker for Celery/Channels | Render (Free Redis) |
| **Database** | Data storage | Render (Free PostgreSQL) |
| **Nginx** | Reverse proxy | Not needed (Render handles routing) |

---

## 2. Step 1: Set Up LiveKit Cloud (5 mins)
LiveKit Cloud hosts your WebRTC SFU for FREE (no credit card):
1. Go to https://cloud.livekit.io/
2. Sign up with email or GitHub
3. Click **Create Project**
4. Name your project (e.g., `edumi2-classroom`)
5. Once created, copy these 5 values from your project dashboard:
   - `LIVEKIT_URL`: e.g., `wss://edumi2-classroom-abc123.livekit.cloud`
   - `LIVEKIT_INTERNAL_URL`: Same as LIVEKIT_URL
   - `LIVEKIT_INTERNAL_HTTP_URL`: Replace `wss://` with `https://` (e.g., `https://edumi2-classroom-abc123.livekit.cloud`)
   - `LIVEKIT_API_KEY`: e.g., `devkey` or `APIabc123`
   - `LIVEKIT_API_SECRET`: A long secret string (keep this safe!)

---

## 3. Step 2: Deploy to Render (10 mins)
Render hosts your Django app, worker, camera service, Redis, and database for FREE (no credit card):

### A. Prepare your code
1. Make sure all your code is pushed to GitHub/GitLab
2. The `render.yaml` in your repo is already configured correctly!

### B. Create Render Blueprint
1. Go to https://render.com/ and sign up (no credit card)
2. Click **New +** → **Blueprint**
3. Connect your GitHub/GitLab account
4. Select your EduMi2 repo and branch
5. Review the resources Render will create (you should see: web, worker, camera, db, redis)
6. Click **Apply**

### C. Wait for deployment
Render will take ~5-10 minutes to create all resources.

### D. Add LiveKit Secrets to Render
1. In Render, go to your **edumi2-web** service
2. Click **Environment**
3. Click **Add Environment Variable** and add these 5 variables (you copied them from LiveKit Cloud):
   | Key | Value |
   |-----|-------|
   | `LIVEKIT_URL` | Your LiveKit WebSocket URL (e.g., `wss://...`) |
   | `LIVEKIT_INTERNAL_URL` | Same as LIVEKIT_URL |
   | `LIVEKIT_INTERNAL_HTTP_URL` | HTTPS version (e.g., `https://...`) |
   | `LIVEKIT_API_KEY` | Your LiveKit API key |
   | `LIVEKIT_API_SECRET` | Your LiveKit API secret |
4. Click **Save Changes** – Render will automatically redeploy your app

---

## 4. File Changes Summary
**Good news! No code changes needed!**
- Your `school_project/settings.py` already uses environment variables for all config
- We only updated `render.yaml` to remove the LiveKit service and use LiveKit Cloud instead

---

## 5. Access Your App!
Once Render is done deploying:
- Your main app URL will be something like `https://edumi2-web.onrender.com`
- Create a superuser to access the admin panel (optional):
  1. In Render, go to **edumi2-web** → **Shell**
  2. Run: `python manage.py createsuperuser`
  3. Follow the prompts

---

## 6. Local vs Production Config
For reference, here's how config changes between environments:

| Setting | Local (`.env`) | Production (Render Secrets) |
|---------|----------------|----------------------------|
| `LIVEKIT_URL` | `ws://localhost:7880` | `wss://your-project.livekit.cloud` |
| `REDIS_URL` | `redis://localhost:6379/0` | Render's Redis URL (auto-set) |
| `DATABASE_URL` | SQLite (file) | Render's PostgreSQL URL (auto-set) |

---

## Troubleshooting
- If meetings don't work: Double-check your LiveKit secrets in Render
- If static files don't load: Make sure `collectstatic` ran (it's in the `render.yaml` docker command)
