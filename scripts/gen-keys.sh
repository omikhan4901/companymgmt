#!/usr/bin/env bash
# Prints fresh secrets for staging/production. Put them in Secret Manager, never in git.
set -euo pipefail
cd "$(dirname "$0")/../api"
uv run python - <<'PY'
import base64, json, os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Ed25519PrivateKey.generate()
private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
print("JWT_PRIVATE_KEY=" + json.dumps(private.decode()))
print("JWT_PUBLIC_KEY=" + json.dumps(public.decode()))
print("FIELD_ENCRYPTION_KEYS=" + json.dumps(json.dumps({"k1": base64.b64encode(os.urandom(32)).decode()})))
print("INTERNAL_TOKEN=" + base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("="))
PY
