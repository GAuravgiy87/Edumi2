"""
Generate a self-signed SSL/TLS certificate for edumi.ac.in

Usage:
    python scripts/generate_ssl_cert.py

Generates:
    certs/edumi.key   — RSA 2048-bit private key
    certs/edumi.crt   — Self-signed certificate (valid 10 years)

Subject Alternative Names (SANs) covered:
    - edumi.ac.in
    - www.edumi.ac.in
    - localhost / 127.0.0.1 / ::1
"""

from OpenSSL import crypto
from pathlib import Path
import socket
import datetime

# Paths
CERT_DIR = Path(__file__).resolve().parent.parent / "certs"
CERT_DIR.mkdir(parents=True, exist_ok=True)

KEY_FILE  = CERT_DIR / "edumi.key"
CERT_FILE = CERT_DIR / "edumi.crt"

DOMAIN = "edumi.ac.in"


def generate():
    # ── RSA key pair ──────────────────────────────────────────────────
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # ── X.509 certificate ─────────────────────────────────────────────
    cert = crypto.X509()

    # Subject
    subject = cert.get_subject()
    subject.C  = "IN"
    subject.ST = "Maharashtra"
    subject.L  = "Pune"
    subject.O  = "EduMi Academic"
    subject.OU = "IT Department"
    subject.CN = DOMAIN

    # Serial + issuer (self-signed ⇒ issuer == subject)
    cert.set_serial_number(1000)
    cert.set_issuer(subject)

    # Validity — 10 years from now
    now = datetime.datetime.utcnow()
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)

    # Public key
    cert.set_pubkey(key)

    # ── Extensions (Subject Alternative Names) ────────────────────────
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"

    san_entries = [
        f"DNS:{DOMAIN}",
        f"DNS:www.{DOMAIN}",
        "DNS:localhost",
        "IP:127.0.0.1",
        "IP:::1",
        f"IP:{local_ip}",
    ]
    # Deduplicate
    san_entries = list(dict.fromkeys(san_entries))

    cert.add_extensions([
        crypto.X509Extension(
            b"subjectAltName", False, ", ".join(san_entries).encode()
        ),
        crypto.X509Extension(
            b"basicConstraints", True, b"CA:FALSE"
        ),
    ])

    # ── Sign ──────────────────────────────────────────────────────────
    cert.sign(key, "sha256")

    # ── Write to disk ─────────────────────────────────────────────────
    KEY_FILE.write_bytes(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    CERT_FILE.write_bytes(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    print(f"[OK] Private key  -> {KEY_FILE}")
    print(f"[OK] Certificate  -> {CERT_FILE}")
    print(f"     Domain       : {DOMAIN}")
    print(f"     Valid until  : {now.year + 10}-xx-xx")
    print(f"     SANs         : {', '.join(san_entries)}")
    print()
    print("NOTE: Because this is a self-signed certificate, browsers will show a")
    print("      security warning. Click 'Advanced → Proceed' to continue.")


if __name__ == "__main__":
    generate()
