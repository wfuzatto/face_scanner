#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
HTTP_PORT="${STANDALONE_PORT:-8092}"
HTTPS_PORT="${STANDALONE_HTTPS_PORT:-8445}"
HTTPS_HOST="${STANDALONE_HTTPS_HOST:-}"

if [[ -f .env ]]; then
  env_value() {
    local key="$1"
    grep -E "^${key}=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true
  }
  [[ -z "$HTTPS_HOST" ]] && HTTPS_HOST="$(env_value STANDALONE_HTTPS_HOST)"
  [[ "$HTTP_PORT" == "8092" ]] && HTTP_PORT="$(env_value STANDALONE_PORT)"
  [[ "$HTTPS_PORT" == "8445" ]] && HTTPS_PORT="$(env_value STANDALONE_HTTPS_PORT)"
fi

HTTP_PORT="${HTTP_PORT:-8092}"
HTTPS_PORT="${HTTPS_PORT:-8445}"

if [[ -z "$HTTPS_HOST" ]]; then
  HTTPS_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi

if [[ -z "$HTTPS_HOST" ]]; then
  echo "ERRO: não foi possível detectar o IP do servidor."
  echo "Defina STANDALONE_HTTPS_HOST no .env."
  exit 1
fi

for cmd in caddy systemctl curl ss; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERRO: comando ausente: $cmd"
    exit 1
  fi
done

if [[ ! -f "$CADDYFILE" ]]; then
  echo "ERRO: Caddyfile não encontrado em $CADDYFILE"
  exit 1
fi

if ! systemctl is-active --quiet caddy; then
  echo "ERRO: caddy.service não está ativo."
  exit 1
fi

# A porta HTTPS pode já estar ocupada pelo próprio Caddy; isso é aceitável
# quando o bloco já existe. Outro processo não deve ser sobrescrito.
listener="$(sudo ss -lntp 2>/dev/null | grep -E ":${HTTPS_PORT}[[:space:]]" || true)"
if [[ -n "$listener" && "$listener" != *caddy* ]]; then
  echo "ERRO: porta HTTPS $HTTPS_PORT já está ocupada por outro processo:"
  echo "$listener"
  exit 1
fi

BEGIN_MARKER="# BEGIN FACE_SCANNER_STANDALONE"
END_MARKER="# END FACE_SCANNER_STANDALONE"
BACKUP="${CADDYFILE}.face-scanner.$(date +%Y%m%d_%H%M%S).bak"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

sudo cp -a "$CADDYFILE" "$BACKUP"

# Remove somente o bloco gerenciado por este projeto, preservando todo o resto.
sudo awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
  $0 == begin {skip=1; next}
  $0 == end {skip=0; next}
  !skip {print}
' "$CADDYFILE" > "$TMP"

cat >> "$TMP" <<EOF

$BEGIN_MARKER
https://${HTTPS_HOST}:${HTTPS_PORT} {
    tls internal
    reverse_proxy 127.0.0.1:${HTTP_PORT}
}
$END_MARKER
EOF

sudo install -m 0644 "$TMP" "$CADDYFILE"

if ! sudo caddy validate --config "$CADDYFILE"; then
  echo "ERRO: configuração Caddy inválida. Restaurando backup."
  sudo cp -a "$BACKUP" "$CADDYFILE"
  exit 1
fi

if ! sudo systemctl reload caddy; then
  echo "ERRO: falha ao recarregar Caddy. Restaurando backup."
  sudo cp -a "$BACKUP" "$CADDYFILE"
  sudo systemctl reload caddy || true
  exit 1
fi

echo "Caddy configurado para o Face Scanner standalone."
echo "URL HTTPS: https://${HTTPS_HOST}:${HTTPS_PORT}"
echo "Upstream local: http://127.0.0.1:${HTTP_PORT}"
echo "Backup: $BACKUP"

echo
echo=""
if curl -kfsS --max-time 5 "https://${HTTPS_HOST}:${HTTPS_PORT}/api/v1/health" >/dev/null; then
  echo "Teste HTTPS: OK"
else
  echo "AVISO: Caddy recarregou, mas o healthcheck HTTPS ainda não respondeu."
  echo "Confirme se o container Face Scanner está rodando em 127.0.0.1:${HTTP_PORT}."
fi
