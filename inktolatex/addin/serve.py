"""Lightweight dev server for InkToLaTeX Add-in.

Serves the Add-in frontend on port 3000 over HTTPS (Word requires HTTPS).
No Node.js / npm required. On the first run it creates a self-signed
certificate for localhost and adds it to the Windows trusted store.

Usage:
    python serve.py
    python serve.py --trust   (add the certificate to the Windows trusted store again)
    python serve.py --http    (plain HTTP, only for tests; Word will NOT load it)
"""

import argparse
import functools
import http.server
import importlib
import ipaddress
import os
import ssl
import subprocess
import sys
from pathlib import Path

ADDIN_DIR = Path(__file__).resolve().parent
DIST_DIR = ADDIN_DIR / "dist"
CERTS_DIR = ADDIN_DIR / ".certs"


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    # Drop a stalled connection after 30 s (browsers open spare connections).
    timeout = 30

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


class TLSThreadingServer(http.server.ThreadingHTTPServer):
    """Threaded server. The TLS handshake happens inside the worker thread,
    so one stalled connection cannot freeze the whole server."""

    daemon_threads = True
    ssl_context = None

    def get_request(self):
        sock, addr = self.socket.accept()
        if self.ssl_context is not None:
            sock = self.ssl_context.wrap_socket(
                sock, server_side=True, do_handshake_on_connect=False
            )
        return sock, addr

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ssl.SSLError, ConnectionError, TimeoutError)):
            return  # normal noise: browser aborted or probed the TLS connection
        super().handle_error(request, client_address)


def ensure_cryptography() -> None:
    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("Installing the 'cryptography' package (one time only)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], check=True)
        importlib.invalidate_caches()


def generate_cert(cert_path: Path, key_path: Path) -> None:
    """Create a self-signed certificate (PEM) valid for localhost / 127.0.0.1."""
    ensure_cryptography()
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    x509.IPAddress(ipaddress.ip_address("::1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(key, hashes.SHA256())
    )

    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Certificate created: {cert_path}")


def trust_cert(cert_path: Path) -> None:
    """Add the certificate to the Windows 'Trusted Root' store of the current user."""
    if os.name != "nt":
        print(f"Not Windows: trust the certificate manually: {cert_path}")
        return
    print("Adding the certificate to the Windows trusted store.")
    print(">>> A Windows security window will appear: click 'Yes'. <<<")
    result = subprocess.run(
        ["certutil", "-user", "-addstore", "-f", "Root", str(cert_path)],
        capture_output=True,
    )
    if result.returncode == 0:
        print("Certificate is trusted now.")
    else:
        print("Could not add the certificate automatically.")
        print(f"Double-click {cert_path} -> Install Certificate -> Current User ->")
        print("'Place all certificates in the following store' -> Trusted Root Certification Authorities.")


def get_cert() -> tuple[Path, Path]:
    # Certificate from office-addin-dev-certs (if it was installed with npx)
    user_certs = Path.home() / ".office-addin-dev-certs"
    if (user_certs / "localhost.crt").exists() and (user_certs / "localhost.key").exists():
        return user_certs / "localhost.crt", user_certs / "localhost.key"

    cert_path = CERTS_DIR / "localhost.crt"
    key_path = CERTS_DIR / "localhost.key"
    if not (cert_path.exists() and key_path.exists()):
        generate_cert(cert_path, key_path)
        trust_cert(cert_path)
    return cert_path, key_path


def main():
    parser = argparse.ArgumentParser(description="InkToLaTeX Addin Dev Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on (default: 3000)")
    parser.add_argument("--http", action="store_true", help="Serve via HTTP instead of HTTPS")
    parser.add_argument("--trust", action="store_true", help="Add the certificate to the Windows trusted store and exit")
    args = parser.parse_args()

    if args.trust:
        cert_path, _ = get_cert()
        trust_cert(cert_path)
        return

    serve_dir = DIST_DIR if DIST_DIR.exists() else (ADDIN_DIR / "src" / "taskpane")
    handler = functools.partial(CORSRequestHandler, directory=str(serve_dir))
    server = TLSThreadingServer(("0.0.0.0", args.port), handler)

    protocol = "http"
    if not args.http:
        try:
            cert_path, key_path = get_cert()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
            server.ssl_context = ctx
            protocol = "https"
            print(f"🔒 HTTPS enabled using {cert_path}")
        except Exception as e:
            # Word needs HTTPS, so do NOT silently fall back to HTTP.
            print(f"❌ HTTPS setup failed: {e}")
            print("   Fix the error above, or run with --http only for tests.")
            sys.exit(1)

    print(f"\n=======================================================")
    print(f"🚀 InkToLaTeX Add-in Server running at:")
    print(f"   {protocol}://localhost:{args.port}/taskpane.html")
    print(f"   Serving directory: {serve_dir}")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
