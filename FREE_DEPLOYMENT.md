# Deploy EduMi2 for FREE on Render

**Best Platform: Render** — supports Docker Compose, PostgreSQL, Redis, workers, and all your services in one place for free!

---

## 🚀 Step-by-Step Deployment Guide

### Step 1: Create a GitHub/GitLab Account
- If you don't already have one, sign up for **GitHub** (https://github.com) or **GitLab** (https://gitlab.com)
- Create a **new repository** for your EduMi2 project

### Step 2: Push Your Code to GitHub/GitLab
Open your terminal (in `Edumi2` folder):

```bash
# Initialize git repository (if not already)
git init

# Add all files
git add .

# Commit changes
git commit -m "Initial EduMi2 commit"

# Link to your GitHub repo
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 3: Create a Render Account
1. Go to https://render.com and sign up (use GitHub/GitLab to sign in for easiest setup)
2. No credit card required for free tier!

### Step 4: Deploy Using Render Blueprint
1. From Render dashboard, click **"New +"** (top right corner)
2. Select **"Blueprint"**
3. Connect your GitHub/GitLab account if not already connected
4. Find and select your EduMi2 repository
5. You'll see a preview of all services Render will deploy (web, worker, camera, livekit, db, redis)
6. Enter a **Blueprint Name** (e.g., "edumi2")
7. Click **"Apply Resources"** to start deployment!

### Step 5: Wait for Deployment
- Deployment will take 5-15 minutes
- You can watch the progress in Render dashboard

### Step 6: Create an Admin Account
1. Once all services are **"Live"**, click on your `edumi2-web` service
2. On the left sidebar, click **"Shell"**
3. In the shell, run:
   ```bash
   python manage.py createsuperuser
   ```
4. Follow the prompts to create a username, email, and password
5. Done! You can now log into the admin interface at `https://your-edumi2-web.onrender.com/admin`

---

## 📱 Visit Your Live Site
- Your main EduMi2 app will be at: `https://edumi2-web.onrender.com`
- Admin interface at: `https://edumi2-web.onrender.com/admin`

---

## 📊 Free Tier Limitations (Render)
1. **Web Services**:
   - Sleep after 15 minutes of inactivity (but wake up on first request)
   - 0.5 CPU, 512 MB RAM each
2. **Databases**:
   - 1 GB storage each
   - Free PostgreSQL and Redis
3. **Runtime**: 750 hours/month total (enough for 24/7 operation)

---

## ❓ Why Not Vercel/Netlify?
- **Vercel/Netlify**: Great for static sites or Next.js, but **CANNOT RUN DOCKER COMPOSE, CELERY, REDIS, LIVEKIT, OR POSTGRESQL**
- **Render**: Perfect for full-stack apps like EduMi2!

---

## 📌 Alternative Free Platforms
If Render doesn't work for you:
1. **Fly.io**: Also supports Docker, but requires credit card verification
2. **Oracle Cloud Free Tier**: Always-free VMs, but more complex to set up
3. **Railway**: Limited free credits, good for testing
