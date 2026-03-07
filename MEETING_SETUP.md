# Meeting Room Setup - Camera/Mic Access

## The Problem

Your meeting room works on `localhost` but not when accessing via IP address (like `10.7.32.74:8000`). This is because:

**WebRTC Security Requirements:**
- ✅ `localhost` or `127.0.0.1` - Works with HTTP
- ❌ IP addresses (10.x.x.x, 192.168.x.x) - Requires HTTPS
- ❌ Domain names - Requires HTTPS

Browsers block camera/microphone access on non-localhost HTTP connections for security.

## Solution: Run with HTTPS

### Quick Start (Recommended)

1. Install required packages:
```bash
pip install -r requirements.txt
```

2. Run the HTTPS server:
```bash
run_https.bat
```

Or manually:
```bash
python manage.py runserver_plus --cert-file cert 0.0.0.0:8000
```

3. Access the site:
- From this computer: `https://localhost:8000`
- From other devices: `https://YOUR_IP:8000` (e.g., `https://10.7.32.74:8000`)

4. **Important**: You'll see a security warning because it's a self-signed certificate:
   - Click "Advanced" or "Show Details"
   - Click "Proceed to localhost (unsafe)" or "Accept the Risk and Continue"
   - This is normal for development

### What Changed

✅ Added `django-extensions` to enable HTTPS development server
✅ Added helpful error messages when accessing via HTTP on IP
✅ Created `run_https.bat` for easy HTTPS server startup
✅ Updated `requirements.txt` with HTTPS dependencies

### Alternative Solutions

#### Option 1: Use ngrok (Easiest for remote testing)
```bash
# Terminal 1: Run Django normally
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Run ngrok
ngrok http 8000
```
Use the HTTPS URL provided by ngrok (e.g., `https://abc123.ngrok.io`)

#### Option 2: Chrome Flags (Development only)
1. Open Chrome
2. Go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
3. Add: `http://10.7.32.74:8000` (your IP)
4. Restart Chrome

**Warning**: Only works on that specific browser, not recommended.

## Testing Checklist

After running with HTTPS:

- [ ] Camera access works on localhost
- [ ] Camera access works on IP address
- [ ] Microphone works
- [ ] Screen sharing works
- [ ] Other devices can join the meeting
- [ ] WebSocket connection is stable

## Troubleshooting

### "NET::ERR_CERT_AUTHORITY_INVALID"
This is expected with self-signed certificates. Click "Advanced" → "Proceed anyway"

### Camera still not working
1. Check browser console for errors (F12)
2. Verify you're using `https://` not `http://`
3. Grant camera/mic permissions when prompted
4. Try a different browser (Chrome/Edge recommended)

### WebSocket connection fails
Make sure Daphne is running:
```bash
python manage.py runserver 0.0.0.0:8000
```

## Production Deployment

For production, use a real SSL certificate:

1. Get a domain name
2. Use Let's Encrypt (free SSL):
```bash
certbot certonly --standalone -d yourdomain.com
```
3. Configure nginx/Apache as reverse proxy
4. Update Django settings for production

## Need Help?

Check the browser console (F12) for detailed error messages about camera/mic access.
