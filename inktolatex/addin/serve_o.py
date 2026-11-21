"""Lightweight dev server for InkToLaTeX Add-in.

Serves the Add-in frontend on port 3000 (HTTPS or HTTP fallback).
No Node.js / npm required.

Usage:
    python serve.py
    python serve.py --http   (force plain HTTP on port 3000)
"""

import argparse
import http.server
import os
import ssl
import subprocess
import sys
from pathlib import Path

ADDIN_DIR = Path(__file__).resolve().parent
DIST_DIR = ADDIN_DIR / "dist"
CERTS_DIR = ADDIN_DIR / ".certs"


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def ensure_self_signed_cert() -> tuple[Path, Path]:
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    cert_path = CERTS_DIR / "localhost.crt"
    key_path = CERTS_DIR / "localhost.key"

    # Also check office-addin-dev-certs location
    user_certs = Path.home() / ".office-addin-dev-certs"
    if (user_certs / "localhost.crt").exists() and (user_certs / "localhost.key").exists():
        return user_certs / "localhost.crt", user_certs / "localhost.key"

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    # Generate using PowerShell or cryptography/openssl
    try:
        ps_cmd = (
            f"$cert = New-SelfSignedCertificate -DnsName 'localhost', '127.0.0.1' "
            f"-CertStoreLocation 'cert:\\CurrentUser\\My' -NotAfter (Get-Date).AddYears(5); "
            f"$pwd = ConvertTo-SecureString -String 'inktolatex' -Force -AsPlainText; "
            f"Export-PfxCertificate -Cert $cert -FilePath '{CERTS_DIR / 'cert.pfx'}' -Password $pwd"
        )
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
    except Exception as e:
        print(f"Could not auto-generate cert via PowerShell: {e}")

    return cert_path, key_path


def main():
    parser = argparse.ArgumentParser(description="InkToLaTeX Addin Dev Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on (default: 3000)")
    parser.add_argument("--http", action="store_true", help="Serve via HTTP instead of HTTPS")
    args = parser.parse_args()

    serve_dir = DIST_DIR if DIST_DIR.exists() else (ADDIN_DIR / "src" / "taskpane")
    os.chdir(serve_dir)

    handler = CORSRequestHandler
    server = http.server.HTTPServer(("0.0.0.0", args.port), handler)

    protocol = "http"
    if not args.http:
        try:
            cert_path, key_path = ensure_self_signed_cert()
            if cert_path.exists() and key_path.exists():
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
                server.socket = ctx.wrap_socket(server.socket, server_side=True)
                protocol = "https"
                print(f"🔒 HTTPS enabled using {cert_path}")
        except Exception as e:
            print(f"⚠️  HTTPS setup fallback to HTTP: {e}")
            protocol = "http"

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
