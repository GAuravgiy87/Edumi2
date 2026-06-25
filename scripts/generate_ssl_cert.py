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

from pathlib import Path
import socket
import datetime

# Try modern cryptography library first, fall back to pyOpenSSL
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    USE_CRYPTOGRAPHY = True
except ImportError:
    from OpenSSL import crypto
    USE_CRYPTOGRAPHY = False

# Paths
CERT_DIR = Path(__file__).resolve().parent.parent / "certs"
CERT_DIR.mkdir(parents=True, exist_ok=True)

KEY_FILE  = CERT_DIR / "edumi.key"
CERT_FILE = CERT_DIR / "edumi.crt"

DOMAIN = "edumi.ac.in"


def generate_with_cryptography():
    """Generate using modern cryptography library"""
    # ── RSA key pair ──────────────────────────────────────────────────
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # ── Subject Alternative Names ─────────────────────────────────────
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"

    san_list = [
        x509.DNSName(DOMAIN),
        x509.DNSName(f"www.{DOMAIN}"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv6Address("::1")),
    ]
    
    # Add local IP if it's different from 127.0.0.1
    if local_ip != "127.0.0.1":
        try:
            san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except Exception:
            pass

    # ── X.509 certificate ─────────────────────────────────────────────
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Maharashtra"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Pune"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EduMi Academic"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IT Department"),
        x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN),
    ])

    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365 * 10))
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # ── Write to disk ─────────────────────────────────────────────────
    KEY_FILE.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    )
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[OK] Private key  -> {KEY_FILE}")
    print(f"[OK] Certificate  -> {CERT_FILE}")
    print(f"     Domain       : {DOMAIN}")
    print(f"     Valid until  : {now.year + 10}-xx-xx")
    print(f"     SANs         : {len(san_list)} entries")
    print()
    print("NOTE: Because this is a self-signed certificate, browsers will show a")
    print("      security warning. Click 'Advanced -> Proceed' to continue.")


def generate_with_pyopenssl():
    """Generate using legacy pyOpenSSL library"""
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
    print("      security warning. Click 'Advanced -> Proceed' to continue.")


if __name__ == "__main__":
    if USE_CRYPTOGRAPHY:
        import ipaddress
        print("Using cryptography library...")
        generate_with_cryptography()
    else:
        print("Using pyOpenSSL library...")
        generate_with_pyopenssl()
