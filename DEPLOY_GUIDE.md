# 🚀 Quick Start Deployment Guide (10 Steps)

## 📋 What You Need Before Starting
- A GitHub or GitLab account
- 10-15 minutes of time

---

## 🎯 Step 1: Push Your Code to GitHub
1. Go to [github.com/new](https://github.com/new)
2. Name your repo (e.g., "edumi2")
3. Click "Create repository"
4. Follow GitHub's instructions to push your local code

---

## 🎯 Step 2: Sign Up for Render
1. Go to [render.com](https://render.com)
2. Sign up with your GitHub/GitLab account

---

## 🎯 Step 3: Deploy via Render Blueprint
1. In Render, click **"New +"** (top right)
2. Select **"Blueprint"**
3. Click **"Connect account"** and connect your GitHub/GitLab if needed
4. Find your "edumi2" repo and click **"Select"**
5. Wait for Render to detect your `render.yaml`
6. Click **"Apply Resources"**

---

## 🎯 Step 4: Wait for Deployment
- Render will take 10-15 minutes to deploy everything
- You can watch the progress on the dashboard

---

## 🎯 Step 5: Create an Admin Account
1. When "edumi2-web" shows **"Live"**, click on it
2. On the left sidebar, click **"Shell"**
3. Run this command:
   ```bash
   python manage.py createsuperuser
   ```
4. Follow the prompts to enter username, email, password

---

## 🎯 Step 6: Visit Your Live App!
Your app will be at: `https://edumi2-web.onrender.com`

---

## 📦 All Services That Will Run
1. **edumi2-web** - Main Django app
2. **edumi2-worker** - Celery background tasks
3. **edumi2-camera** - Camera service
4. **edumi2-livekit** - Video server
5. **edumi2-db** - PostgreSQL database
6. **edumi2-redis** - Redis cache

---

## 💡 Free Tier Tips
- Services will sleep after 15 minutes of inactivity (but wake up quickly)
- 1GB of storage per database
- 750 hours/month of runtime (plenty for normal use)
