#!/usr/bin/env bash
set -euo pipefail

OUT_BASE="${1:-$PWD/pihole-export}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${OUT_BASE}/${TS}"

DB_SRC="/etc/pihole/gravity.db"
if [[ ! -r "${DB_SRC}" ]]; then
  echo "ERROR: No puedo leer ${DB_SRC}. Ejecuta con sudo o revisa permisos." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
echo "Exportando a: ${OUT_DIR}"

sudo cp "${DB_SRC}" "${OUT_DIR}/gravity.db"

sudo sqlite3 "${DB_SRC}"   "SELECT address FROM adlist WHERE enabled=1 ORDER BY address;"   > "${OUT_DIR}/adlists_enabled.txt"

sudo sqlite3 "${DB_SRC}"   "SELECT domain FROM domainlist WHERE enabled=1 AND type=0 ORDER BY domain;"   > "${OUT_DIR}/allow_exact.txt"

sudo sqlite3 "${DB_SRC}"   "SELECT domain FROM domainlist WHERE enabled=1 AND type=1 ORDER BY domain;"   > "${OUT_DIR}/deny_exact.txt"

sudo sqlite3 "${DB_SRC}"   "SELECT domain FROM domainlist WHERE enabled=1 AND type=2 ORDER BY domain;"   > "${OUT_DIR}/allow_regex.txt"

sudo sqlite3 "${DB_SRC}"   "SELECT domain FROM domainlist WHERE enabled=1 AND type=3 ORDER BY domain;"   > "${OUT_DIR}/deny_regex.txt"

sudo sqlite3 "${DB_SRC}"   "SELECT DISTINCT domain FROM gravity ORDER BY domain;"   > "${OUT_DIR}/gravity_domains_baseline.txt"

( cd "${OUT_DIR}" && sha256sum *.txt gravity.db > SHA256SUMS.txt )
( cd "${OUT_DIR}" && wc -l *.txt > COUNTS.txt )

echo "OK."
ls -1 "${OUT_DIR}"
