#!/usr/bin/env bash
# Generate RSA key pair used for signing JWT access/refresh tokens.
# The app reads these at startup (see app/core/config.py):
#   keys/jwt_private.pem  - RS256 signing key (never ship in images)
#   keys/jwt_public.pem   - verification key
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="${SCRIPT_DIR}/../keys"

mkdir -p "${KEYS_DIR}"

if [[ -f "${KEYS_DIR}/jwt_private.pem" && -f "${KEYS_DIR}/jwt_public.pem" ]]; then
  echo "Keys already exist in ${KEYS_DIR}; refusing to overwrite." >&2
  echo "Delete them first if you really want to rotate:" >&2
  echo "  rm -f ${KEYS_DIR}/jwt_private.pem ${KEYS_DIR}/jwt_public.pem" >&2
  exit 1
fi

openssl genrsa -out "${KEYS_DIR}/jwt_private.pem" 2048 2>/dev/null
openssl rsa -in "${KEYS_DIR}/jwt_private.pem" -pubout -out "${KEYS_DIR}/jwt_public.pem" 2>/dev/null
chmod 600 "${KEYS_DIR}/jwt_private.pem"
chmod 644 "${KEYS_DIR}/jwt_public.pem"

echo "JWT keys written to ${KEYS_DIR}/"
