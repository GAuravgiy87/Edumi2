"""
Generate a self-signed cert and launch Daphne over HTTPS on port 8443.
Usage:  python run_https.py
"""
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CERT_FILE = BASE_DIR / "ssl" / "cert.pem"
KEY_FILE  = BASE_DIR / "ssl" / "key.pem"

def generate_cert():
    ssl_dir = BASE_DIR / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    if CERT_FILE.exists() and KEY_FILE.exists():
        print("[SSL] Using existing cert/key in ./ssl/")
        return
    print("[SSL] Generating self-signed certificate...")
    try:
        from OpenSSL import crypto
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        cert = crypto.X509()
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.add_extensions([
            crypto.X509Extension(b"subjectAltName", False,
                b"IP:127.0.0.1,IP:10.7.32.175,IP:10.17.2.47,DNS:localhost")
        ])
        cert.sign(k, "sha256")
        CERT_FILE.write_bytes(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        KEY_FILE.write_bytes(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
        print(f"[SSL] Certificate written to {CERT_FILE}")
    except ImportError:
        print("pyOpenSSL not found. Install it: pip install pyOpenSSL")
        sys.exit(1)

if __name__ == "__main__":
    generate_cert()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "school_project.settings")
    host = os.environ.get("BIND_HOST", "0.0.0.0")
    port = os.environ.get("BIND_PORT", "8443")
    print(f"[Daphne] Starting HTTPS server on https://{host}:{port}/")
    print(f"[Daphne] Access from other devices: https://10.7.32.175:{port}/")
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "school_project.settings"}
    cmd = [
        sys.executable, "-m", "daphne",
        "-e", f"ssl:{port}:privateKey={KEY_FILE}:certKey={CERT_FILE}",
        "-b", host,
        "school_project.asgi:application",
    ]
    subprocess.run(cmd, env=env)
