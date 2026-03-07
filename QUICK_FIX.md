# 🚨 Quick Fix: Camera/Mic Not Working on IP Address

## The Problem
✅ Works on `localhost`  
❌ Doesn't work on IP (like `10.7.32.74:8000`)

## Why?
Browsers require HTTPS for camera/mic access on IP addresses (security feature).

## The Fix (2 minutes)

### Step 1: Install packages
```bash
pip install django-extensions werkzeug pyOpenSSL
```

### Step 2: Run with HTTPS
```bash
run_https.bat
```

Or:
```bash
python manage.py runserver_plus --cert-file cert 0.0.0.0:8000
```

### Step 3: Access via HTTPS
- This computer: `https://localhost:8000`
- Other devices: `https://10.7.32.74:8000` (use your IP)

### Step 4: Accept the security warning
When you see "Your connection is not private":
1. Click "Advanced"
2. Click "Proceed to localhost (unsafe)" or "Accept the Risk"

✅ Done! Camera and mic will now work.

## Alternative: Use ngrok (No setup needed)

1. Keep your server running normally:
```bash
python manage.py runserver 0.0.0.0:8000
```

2. In another terminal:
```bash
ngrok http 8000
```

3. Use the HTTPS URL ngrok gives you (e.g., `https://abc123.ngrok.io`)

## Why This Happens

| Access Method | HTTP Works? | Reason |
|---------------|-------------|--------|
| `localhost` | ✅ Yes | Browser trusts localhost |
| `127.0.0.1` | ✅ Yes | Browser trusts loopback |
| `10.x.x.x` (IP) | ❌ No | Requires HTTPS for security |
| Domain name | ❌ No | Requires HTTPS for security |

This is a browser security feature, not a bug in your code!

## Need More Help?

See [MEETING_SETUP.md](MEETING_SETUP.md) for detailed instructions.
