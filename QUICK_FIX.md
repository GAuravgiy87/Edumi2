# 🚨 Quick Fix: Camera/Mic Not Working on IP Address

## The Problem
✅ Works on `localhost`  
❌ Doesn't work on IP (like `10.7.32.74:8000`)

## Why?
Browsers require HTTPS for camera/mic access on IP addresses (security feature).

## The Fix - Choose One:

### Option 1: ngrok (Easiest - No Certificate Warnings!)

**Step 1:** Download ngrok
- Go to https://ngrok.com/download
- Download for Windows
- Extract `ngrok.exe` to your project folder

**Step 2:** Start Django
```bash
python manage.py runserver 0.0.0.0:8000
```

**Step 3:** Start ngrok (in a new terminal)
```bash
ngrok http 8000
```
Or double-click: `start_ngrok.bat`

**Step 4:** Use the HTTPS URL
- Copy the URL shown (e.g., `https://abc123.ngrok.io`)
- Open it in your browser
- ✅ Camera and mic work! No warnings!

📖 **See [NGROK_QUICKSTART.txt](NGROK_QUICKSTART.txt) for detailed steps**

---

### Option 2: HTTPS Server (For Local Network)

**Step 1:** Install packages
```bash
pip install django-extensions werkzeug pyOpenSSL
```

**Step 2:** Run with HTTPS
```bash
run_https.bat
```

Or:
```bash
python manage.py runserver_plus --cert-file cert 0.0.0.0:8000
```

**Step 3:** Access via HTTPS
- This computer: `https://localhost:8000`
- Other devices: `https://10.7.32.74:8000` (use your IP)

**Step 4:** Accept the security warning
When you see "Your connection is not private":
1. Click "Advanced"
2. Click "Proceed to localhost (unsafe)" or "Accept the Risk"

✅ Done! Camera and mic will now work.

---

## Comparison

| Method | Certificate Warning | Works Outside Network | Best For |
|--------|-------------------|---------------------|----------|
| **ngrok** | ❌ No | ✅ Yes | Testing, demos, sharing |
| **HTTPS Server** | ⚠️ Yes | ❌ No | Local network only |

## Why This Happens

| Access Method | HTTP Works? | Reason |
|---------------|-------------|--------|
| `localhost` | ✅ Yes | Browser trusts localhost |
| `127.0.0.1` | ✅ Yes | Browser trusts loopback |
| `10.x.x.x` (IP) | ❌ No | Requires HTTPS for security |
| Domain name | ❌ No | Requires HTTPS for security |

This is a browser security feature, not a bug in your code!

## Need More Help?

- **ngrok**: See [NGROK_QUICKSTART.txt](NGROK_QUICKSTART.txt) or [NGROK_GUIDE.md](NGROK_GUIDE.md)
- **HTTPS**: See [MEETING_SETUP.md](MEETING_SETUP.md)
