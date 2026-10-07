# group-project-1

A digital document signing and verification service: a React frontend, a FastAPI
backend, and PostgreSQL.

- **Frontend** — React + Vite dev server (`frontend/`), served on port 3000.
- **Backend** — FastAPI + SQLAlchemy (`backend/`), served on port 8000 inside the
  compose network.
- **Database** — PostgreSQL 16.
- **Document storage** — uploaded files are kept privately on a Docker volume
  (`uploads`, mounted at `/data/documents`). There is no public URL; files are
  only reachable through the API by signing token.
- **Encryption** — every stored file is an AES-256-GCM envelope under its own
  data key, which is wrapped by a service master key. A document key can be
  shared with a recipient over an X25519 key exchange, so the recipient can
  decrypt the file locally.

The browser only ever talks to port 3000; Vite proxies `/api/*` to the backend,
so there is a single origin and no CORS setup.

## How it works

1. **Upload** a document on the home page. The service computes its SHA-256
   hash, encrypts it with a fresh data key, stores the envelope and creates a
   unique **signing link** (`/sign/<token>`).
2. **Send the link** to the signer. Opening it shows the document for review and
   a form to sign with a name and email.
3. **Signing** records three layers, all bound to the document hash:
   - an *acknowledgement record* — signer name, email, timestamp, IP;
   - an *HMAC-SHA256 signature* keyed with the service's secret;
   - an *RSA (X.509) signature* verifiable by anyone holding the certificate.
4. **Verify** on the `/verify` page: upload a file and the service reports
   whether it matches a signed document, plus a pass/fail check for each layer.
   A changed file hashes differently and matches no signature.
5. **Share securely**: the recipient generates an X25519 keypair locally
   (`python -m app.cli keygen`) and sends only the public key. The service wraps
   the document's data key for that key, and the recipient fetches the
   ciphertext and decrypts it on their own machine
   (`python -m app.cli decrypt`). The private key is never uploaded.

The RSA keypair, self-signed certificate, HMAC secret and AES master key are
generated once by the `migrate` service and stored in the `signing_keys` and
`encryption_keys` tables, so signatures and stored files stay readable across
restarts.

## Cryptography

All primitives come from the `cryptography` library (see `backend/app/crypto.py`
for the primitives and `backend/app/vault.py` for the key management); nothing is
hand-rolled and no key is derived from a password or hardcoded.

| Purpose | Primitive | How it is used |
| --- | --- | --- |
| Confidentiality + integrity | AES-256-GCM | A fresh 96-bit nonce per encryption and a fresh 256-bit key per document, so nonces are never reused. The authentication tag is checked before any plaintext is released. |
| Key agreement | X25519 ECDH + HKDF-SHA256 | A fresh ephemeral keypair per share; the raw ECDH secret is expanded with HKDF (random salt, fixed `info`) instead of being used as a key. |
| Key management | AES-256-GCM key wrapping | Master key → per-document data key → document bytes. The wrapping is bound with AAD to the document token and the recipient key fingerprint, so a wrapped key cannot be replayed onto another document. |
| Authentication | HMAC-SHA256 + RSA-2048/X.509 | Both are computed over the document's SHA-256 hash, so they stay valid for the plaintext regardless of how the file is encrypted at rest. |

The recipient's private key never leaves the recipient: the service only stores
public values (their public key, the ephemeral public key, the HKDF salt and the
wrapped data key).

## Run it (development)

The sandbox environment is defined in `docker-compose.base44.yml`:

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

Then open the preview (host port 3000). The stack runs from the cloned source
with live reload, so edits to `backend/` and `frontend/` apply without a rebuild.

Services: `db` (Postgres), `migrate` (one-shot table create + key generation),
`api` (FastAPI), `web` (Vite dev server).

## API

- `GET /api/documents` — list documents with signature status
- `POST /api/documents` — upload a document (multipart `file`), returns its signing token
- `GET /api/documents/{token}` — document detail
- `GET /api/documents/{token}/download` — download the stored original
- `POST /api/documents/{token}/sign` — sign (`{ "name", "email" }`)
- `POST /api/documents/{token}/key-exchange` — wrap the document key for a
  recipient (`{ "recipient_name", "recipient_email", "recipient_public_key" }`)
- `GET /api/documents/{token}/key-exchange` — the stored key exchange for a document
- `GET /api/documents/{token}/ciphertext` — the encrypted envelope as stored
- `POST /api/verify` — verify an uploaded file (multipart `file`)

Interactive docs are available at `/api/docs` when running locally.

## Command line client

`backend/app/cli.py` runs the whole flow from outside the app, using only the
standard library and `cryptography`. Run it inside the api container:

```bash
# the full end-to-end demonstration (upload -> sign -> key exchange -> decrypt)
docker compose -f docker-compose.base44.yml exec -T api python -m app.cli demo

# recipient side: create a keypair, then open a shared document
docker compose -f docker-compose.base44.yml exec -T api python -m app.cli keygen --out /tmp/recipient.key
docker compose -f docker-compose.base44.yml exec -T api python -m app.cli decrypt \
  --token <token> --private-key /tmp/recipient.key --out /tmp/document
```

The demo prints every layer: the AES-256-GCM envelope, the wrapped key, local
decryption with the recipient's private key, a tamper check that the GCM tag
rejects, and the HMAC/RSA verification of the recovered plaintext.

## Tests

```bash
docker compose -f docker-compose.base44.yml exec -T api python -m unittest discover -s tests
```

`backend/tests/test_crypto.py` covers the primitives: unique nonces, tamper and
wrong-key rejection, AAD binding, ECDH agreement between both sides, rejection of
an impostor's key and of non-X25519 keys, and envelope framing.
