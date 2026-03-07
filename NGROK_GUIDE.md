# 🚀 Using ngrok for EduMi

ngrok is the easiest way to get HTTPS working without any setup. It creates a secure tunnel to your local server and gives you a public HTTPS URL.

## Step 1: Download ngrok

1. Go to https://ngrok.com/download
2. Download ngrok for Windows
3. Extract the `ngrok.exe` file to your project folder (same folder as `manage.py`)

## Step 2: Sign Up (Optional but Recommended)

1. Go to https://dashboard.ngrok.com/signup
2. Sign up for a free account
3. Copy your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
4. Run this command once:
   ```bash
   ngrok authtoken YOUR_AUTH_TOKEN
   ```

## Step 3: Start Your Django Server

Open a terminal and run:
```bash
python manage.py runserver 0.0.0.0:8000
```

Keep this terminal open!

## Step 4: Start ngrok

Open a NEW terminal and run:
```bash
ngrok http 8000
```

Or use the batch file:
```bash
start_ngrok.bat
```

## Step 5: Use the HTTPS URL

ngrok will show you something like:

```
Forwarding   https://abc123.ngrok.io -> http://localhost:8000
```

Use that HTTPS URL (`https://abc123.ngrok.io`) to access your site from anywhere!

## Benefits of ngrok

✅ No certificate warnings
✅ Works from any device (even outside your network)
✅ Free tier available
✅ No configuration needed
✅ Perfect for testing and demos

## Limitations (Free Tier)

- URL changes every time you restart ngrok
- 40 connections/minute limit
- Session expires after 2 hours

## Pro Tips

1. Keep both terminals open (Django + ngrok)
2. Share the ngrok URL with others to test
3. Use the same URL for all devices during a session
4. Restart ngrok if the URL expires

## Troubleshooting

**Q: "command not found: ngrok"**
A: Make sure `ngrok.exe` is in your project folder or add it to PATH

**Q: "ERR_NGROK_108"**
A: You need to sign up and add your authtoken (see Step 2)

**Q: Django shows "Invalid HTTP_HOST header"**
A: Add the ngrok URL to `ALLOWED_HOSTS` in settings.py:
```python
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.ngrok.io', '*.ngrok-free.app']
```

**Q: Session expired**
A: Free tier sessions expire after 2 hours. Just restart ngrok.

## Alternative: ngrok with Custom Domain (Paid)

If you upgrade to ngrok Pro, you can get:
- Custom domain (e.g., `myapp.ngrok.io`)
- No session limits
- More connections
- Reserved domains

## Quick Commands

```bash
# Start ngrok on port 8000
ngrok http 8000

# Start with custom subdomain (requires paid plan)
ngrok http 8000 --subdomain=myapp

# Start with specific region
ngrok http 8000 --region=us

# View web interface
# Open http://localhost:4040 in browser
```

## Summary

1. Download ngrok.exe
2. Run: `python manage.py runserver 0.0.0.0:8000`
3. Run: `ngrok http 8000`
4. Use the HTTPS URL shown
5. Camera and mic will work! 🎉
