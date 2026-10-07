"""
Smart Attendance System — Application Entrypoint
Supports HTTP and development HTTPS with SSL context for LAN camera access.
"""

import os
import argparse
from pathlib import Path
from app import create_app

env_name = os.getenv('FLASK_ENV', 'development')
app = create_app(env_name)


def generate_dev_ssl_context():
    certs_dir = Path(__file__).resolve().parent / 'certs'
    certs_dir.mkdir(parents=True, exist_ok=True)
    cert_file = certs_dir / 'dev_cert.pem'
    key_file = certs_dir / 'dev_key.pem'

    if cert_file.exists() and key_file.exists():
        return str(cert_file), str(key_file)

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.DNSName(u"127.0.0.1"),
                x509.IPAddress(__import__('ipaddress').ip_address('127.0.0.1')),
            ]),
            critical=False,
        ).sign(key, hashes.SHA256())

        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return str(cert_file), str(key_file)
    except Exception as e:
        return 'adhoc'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run Smart Attendance System Server")
    parser.add_argument('--https', action='store_true', help='Enable HTTPS development mode for camera testing over LAN')
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', 5000)), help='Port to bind to')
    parser.add_argument('--host', type=str, default=os.getenv('HOST', '0.0.0.0'), help='Host address to bind to')
    args = parser.parse_args()

    use_https = args.https or os.getenv('HTTPS', 'false').lower() in ('true', '1', 't', 'yes')
    ssl_context = generate_dev_ssl_context() if use_https else None
    protocol = "https" if use_https else "http"

    print("\n" + "=" * 65)
    print(f"  SMART ATTENDANCE SYSTEM — SERVER RUNNING")
    print("=" * 65)
    print(f"  • Localhost URL:    {protocol}://127.0.0.1:{args.port}")
    print(f"  • Localhost (name): {protocol}://localhost:{args.port}")
    if args.host == '0.0.0.0':
        print(f"  • LAN Access URL:   {protocol}://192.168.1.81:{args.port}")
    print(f"  • HTTPS Active:     {use_https}")
    print("=" * 65 + "\n")

    app.run(
        host=args.host,
        port=args.port,
        debug=app.config.get('DEBUG', True),
        ssl_context=ssl_context
    )
