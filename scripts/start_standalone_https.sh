#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

START_PORT="${STANDALONE_PORT_START:-18092}"
END_PORT="${STANDALONE_PORT_END:-18120}"
HTTPS_PORT="${STANDALONE_HTTPS_PORT:-8445}"

if [[ -f .env ]]; then
  env_value() {
    local key="$1"
    grep -E "^${key}=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true
  }
  candidate="$(env_value STANDALONE_HTTPS_PORT)"
  [[ -n "$candidate" ]] && HTTPS_PORT="$candidate"
fi

for cmd in docker ss curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERRO: comando ausente: $cmd"
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "ERRO: Docker daemon não está acessível."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERRO: Docker Compose não está disponível."
  exit 1
fi

# Remove somente instâncias antigas conhecidas deste módulo de teste.
docker rm -f face-scanner-test 2>/dev/null || true

echo "[standalone] removendo instância Compose anterior do Face Scanner..."
docker compose down --remove-orphans || true

port_in_use() {
  local p="$1"
  ss -ltnH | awk '{print $4}' | grep -Eq "(^|:)${p}$"
}

HTTP_PORT=""
for p in $(seq "$START_PORT" "$END_PORT"); do
  if ! port_in_use "$p"; then
    HTTP_PORT="$p"
    break
  fi
done

if [[ -z "$HTTP_PORT" ]]; then
  echo "ERRO: nenhuma porta local livre entre $START_PORT e $END_PORT."
  exit 1
fi

export STANDALONE_BIND=127.0.0.1
export STANDALONE_PORT="$HTTP_PORT"
export STANDALONE_HTTPS_PORT="$HTTPS_PORT"

cat > .standalone-runtime.env <<EOF
STANDALONE_BIND=127.0.0.1
STANDALONE_PORT=${HTTP_PORT}
STANDALONE_HTTPS_PORT=${HTTPS_PORT}
EOF
chmod 600 .standalone-runtime.env

echo "[standalone] upstream local escolhido: 127.0.0.1:${HTTP_PORT}"
echo "[standalone] construindo/subindo container..."
docker compose up -d --build --force-recreate

DEADLINE=$((SECONDS + 120))
until curl -fsS --max-time 3 "http://127.0.0.1:${HTTP_PORT}/api/v1/health" >/dev/null 2>&1; do
  if (( SECONDS >= DEADLINE )); then
    echo "ERRO: Face Scanner não ficou saudável em 120s."
    docker compose ps || true
    docker compose logs --tail=200 face-scanner || true
    exit 1
  fi
  sleep 2
done

echo "[standalone] Face Scanner saudável. Configurando HTTPS no Caddy..."
chmod +x scripts/configure_https_standalone.sh
STANDALONE_PORT="$HTTP_PORT" STANDALONE_HTTPS_PORT="$HTTPS_PORT" ./scripts/configure_https_standalone.sh

echo
printf 'Standalone HTTPS pronto.\n'
printf 'Upstream privado: http://127.0.0.1:%s\n' "$HTTP_PORT"
printf 'Abra somente a URL HTTPS informada acima.\n'
