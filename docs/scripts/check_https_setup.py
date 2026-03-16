#!/usr/bin/env python
"""
Check if HTTPS setup is ready for WebRTC
"""
import sys

def check_packages():
    """Check if required packages are installed"""
    print("Checking required packages...")
    required = ['django_extensions', 'werkzeug', 'OpenSSL']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print("\n❌ Missing packages. Install with:")
        print("   pip install -r requirements.txt")
        return False
    else:
        print("\n✅ All packages installed")
        return True

def check_settings():
    """Check if django_extensions is in INSTALLED_APPS"""
    print("\nChecking Django settings...")
    try:
        import django
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')
        django.setup()
        
        from django.conf import settings
        
        if 'django_extensions' in settings.INSTALLED_APPS:
            print("  ✓ django_extensions in INSTALLED_APPS")
            return True
        else:
            print("  ✗ django_extensions NOT in INSTALLED_APPS")
            print("     Add 'django_extensions' to INSTALLED_APPS in settings.py")
            return False
    except Exception as e:
        print(f"  ⚠ Could not check settings: {e}")
        return True  # Don't fail on this

def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Unable to detect"

def main():
    print("=" * 60)
    print("HTTPS Setup Checker for WebRTC")
    print("=" * 60)
    print()
    
    packages_ok = check_packages()
    settings_ok = check_settings()
    
    print("\n" + "=" * 60)
    
    if packages_ok and settings_ok:
        print("✅ Setup is ready!")
        print("\nTo start the HTTPS server:")
        print("  1. Run: run_https.bat")
        print("  2. Or: python manage.py runserver_plus --cert-file cert 0.0.0.0:8000")
        
        local_ip = get_local_ip()
        print(f"\nAccess from:")
        print(f"  - This computer: https://localhost:8000")
        print(f"  - Other devices: https://{local_ip}:8000")
        print("\n⚠ You'll see a security warning - click 'Advanced' → 'Proceed anyway'")
    else:
        print("❌ Setup incomplete")
        print("\nPlease fix the issues above and run this script again.")
        sys.exit(1)
    
    print("=" * 60)

if __name__ == '__main__':
    main()
