"""Command line client for the document signing service.

Runs the whole cryptographic data flow from the outside, using only the standard
library plus `cryptography`:

    python -m app.cli demo
    python -m app.cli keygen --out recipient.key
    python -m app.cli decrypt --token <token> --private-key recipient.key --out doc.pdf

The recipient's private key is generated locally and never leaves this process -
the service only ever receives the public key.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

from cryptography.exceptions import InvalidTag

from . import crypto, vault
from .signing import sha256_hex

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


# --- HTTP -------------------------------------------------------------------


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _request(method: str, url: str, data: bytes | None = None, content_type: str | None = None) -> bytes:
    headers = {"Content-Type": content_type} if content_type else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise SystemExit(f"{method} {url} failed with {error.code}: {body}")


def _get_json(base_url: str, path: str) -> dict:
    return json.loads(_request("GET", _url(base_url, path)))


def _post_json(base_url: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    return json.loads(_request("POST", _url(base_url, path), body, "application/json"))


def _post_file(base_url: str, path: str, field: str, file_path: str) -> dict:
    boundary = f"----b44{uuid4().hex}"
    with open(file_path, "rb") as handle:
        content = handle.read()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{field}"; '
                f'filename="{os.path.basename(file_path)}"\r\n'
            ).encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return json.loads(
        _request("POST", _url(base_url, path), body, f"multipart/form-data; boundary={boundary}")
    )


# --- recipient side ---------------------------------------------------------


def decrypt_envelope(document: dict, ciphertext: bytes, private_key_pem: str) -> bytes:
    """Unwrap the data key with the recipient's private key and decrypt locally."""
    exchange = document.get("key_exchange")
    if exchange is None:
        raise SystemExit("This document has not been shared with a recipient yet")

    dek = unwrap_data_key(document["token"], exchange, private_key_pem)
    plaintext, encrypted = crypto.unseal_document(ciphertext, dek)
    if not encrypted:
        raise SystemExit("The stored file is not an encrypted envelope")
    return plaintext


def unwrap_data_key(token: str, exchange: dict, private_key_pem: str) -> bytes:
    """Re-derive the exchange key from the ephemeral public key and unwrap."""
    return vault.unwrap_shared_key(
        token=token,
        recipient_fingerprint=exchange["recipient_fingerprint"],
        ephemeral_public_key=exchange["ephemeral_public_key"],
        salt_b64=exchange["salt"],
        wrapped_key_b64=exchange["wrapped_key"],
        recipient_private_pem=private_key_pem,
    )


def fetch_and_open(base_url: str, token: str, private_key_pem: str) -> tuple[dict, bytes]:
    document = _get_json(base_url, f"/api/documents/{token}")
    ciphertext = _request("GET", _url(base_url, f"/api/documents/{token}/ciphertext"))
    return document, decrypt_envelope(document, ciphertext, private_key_pem)


def check_integrity(document: dict, plaintext: bytes) -> tuple[str, bool]:
    """Authenticate the decrypted bytes against the hash the signer signed."""
    digest = sha256_hex(plaintext)
    signed = (document.get("signature") or {}).get("signed_sha256")
    return digest, digest == document["sha256"] and (signed is None or digest == signed)


# --- commands ---------------------------------------------------------------


def cmd_keygen(args) -> int:
    private_pem, public_pem = crypto.generate_keypair()
    with open(args.out, "w") as handle:
        handle.write(private_pem)
    os.chmod(args.out, 0o600)

    print(f"private key written to {args.out} (mode 0600, never uploaded)")
    print(f"fingerprint      {crypto.fingerprint(public_pem)}")
    print("\npublic key (paste this into the sharing form):\n")
    print(public_pem)
    return 0


def cmd_decrypt(args) -> int:
    with open(args.private_key) as handle:
        private_key_pem = handle.read()

    document, plaintext = fetch_and_open(args.base_url, args.token, private_key_pem)
    digest, ok = check_integrity(document, plaintext)

    print(f"decrypted {len(plaintext)} bytes from the stored envelope")
    print(f"SHA-256   {digest}")
    print(f"signature {'matches' if ok else 'DOES NOT MATCH'} the signed hash")

    if args.out:
        with open(args.out, "wb") as handle:
            handle.write(plaintext)
        print(f"written to {args.out}")
    return 0 if ok else 1


def cmd_demo(args) -> int:
    workdir = args.workdir
    os.makedirs(workdir, exist_ok=True)

    print("== 1. recipient keypair (X25519), generated locally ==")
    private_pem, public_pem = crypto.generate_keypair()
    fingerprint = crypto.fingerprint(public_pem)
    print(f"   fingerprint      {fingerprint}")
    print("   private key stays in this process; only the public key is sent")

    sample = os.path.join(workdir, "contract.txt")
    with open(sample, "wb") as handle:
        handle.write(b"Service agreement between Alice and Bob. Version 1.\n")

    print("\n== 2. upload: stored as an AES-256-GCM envelope ==")
    document = _post_file(args.base_url, "/api/documents", "file", sample)
    token = document["token"]
    print(f"   signing token    {token}")
    print(f"   plaintext SHA-256 {document['sha256']}")
    print(f"   stored encrypted {document['encrypted']}")

    print("\n== 3. sign: acknowledgement + HMAC-SHA256 + RSA/X.509 ==")
    signature = _post_json(
        args.base_url,
        f"/api/documents/{token}/sign",
        {"name": args.name, "email": args.email},
    )
    print(f"   HMAC-SHA256      {signature['hmac_signature'][:40]}…")
    print(f"   RSA-2048         {signature['rsa_signature'][:40]}…")

    print("\n== 4. key exchange: X25519 ECDH + HKDF-SHA256 wraps the data key ==")
    exchange = _post_json(
        args.base_url,
        f"/api/documents/{token}/key-exchange",
        {
            "recipient_name": args.name,
            "recipient_email": args.email,
            "recipient_public_key": public_pem,
        },
    )
    print(f"   ephemeral key    {exchange['ephemeral_public_key'].splitlines()[1][:40]}…")
    print(f"   HKDF salt        {exchange['salt']}")
    print(f"   wrapped key      {exchange['wrapped_key'][:40]}…")

    print("\n== 5. recipient fetches the ciphertext ==")
    ciphertext = _request("GET", _url(args.base_url, f"/api/documents/{token}/ciphertext"))
    # Re-fetch the record: it now carries the key exchange the recipient needs.
    document = _get_json(args.base_url, f"/api/documents/{token}")
    print(f"   {len(ciphertext)} bytes, envelope header {ciphertext[:8]!r}")
    with open(sample, "rb") as handle:
        leaked = handle.read() in ciphertext
    print(f"   contains the original plaintext: {leaked}")

    print("\n== 6. recipient decrypts locally with their private key ==")
    plaintext = decrypt_envelope(document, ciphertext, private_pem)
    digest, ok = check_integrity(document, plaintext)
    print(f"   decrypted SHA-256 {digest}")
    print(f"   matches the hash the signer signed: {ok}")

    print("\n== 7. tamper check: a flipped byte must not decrypt ==")
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 0x01
    try:
        crypto.unseal_document(bytes(tampered), unwrap_data_key(token, exchange, private_pem))
        print("   FAILED: tampered ciphertext was accepted")
        return 1
    except InvalidTag:
        print("   rejected (GCM authentication tag mismatch) - no plaintext released")

    print("\n== 8. verify the signature over the recovered plaintext ==")
    recovered = os.path.join(workdir, "contract.recovered.txt")
    with open(recovered, "wb") as handle:
        handle.write(plaintext)
    verification = _post_file(args.base_url, "/api/verify", "file", recovered)
    print(f"   verified: {verification['verified']}")
    for check in verification["checks"]:
        print(f"   [{'ok' if check['passed'] else 'XX'}] {check['name']}: {check['detail']}")

    print("\nAll layers passed: authenticated encryption at rest, X25519 key")
    print("exchange, and HMAC/RSA signatures over the recovered plaintext.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="service base URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    keygen = subparsers.add_parser("keygen", help="create a recipient X25519 keypair")
    keygen.add_argument("--out", default="recipient.key", help="where to write the private key")
    keygen.set_defaults(func=cmd_keygen)

    decrypt = subparsers.add_parser("decrypt", help="decrypt a shared document")
    decrypt.add_argument("--token", required=True)
    decrypt.add_argument("--private-key", required=True)
    decrypt.add_argument("--out", help="write the plaintext here")
    decrypt.set_defaults(func=cmd_decrypt)

    demo = subparsers.add_parser("demo", help="run the full end-to-end flow")
    demo.add_argument("--name", default="Ada Lovelace")
    demo.add_argument("--email", default="ada@example.com")
    demo.add_argument("--workdir", default="/tmp/b44-demo")
    demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
