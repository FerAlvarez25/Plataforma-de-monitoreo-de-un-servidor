#!/usr/bin/env bash
# Captura evidencias del SO durante la ejecución del servidor.
# Uso: observar.sh <pid_del_servidor> <carpeta> [sufijo]
#   - sufijo por defecto "03" (escribe 03_evidencia_comportamiento.txt);
#     usa "07" para la evidencia de la corrección.
set -u
PID="${1:?indicar pid del servidor}"
CARPETA="${2:?indicar carpeta de evidencias}"
SUFIJO="${3:-03}"
mkdir -p "$CARPETA"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  echo "=== pstree -p $PID ==="
  pstree -p "$PID" 2>&1
  echo "=== ps -eLf (filtro servidor) ==="
  ps -eLf | grep -E "servidor|cargador|PID" | head -60
  echo "=== top -b -n 1 (resumen) ==="
  top -b -n 1 | head -30
  echo "=== /proc/$PID/status ==="
  grep -E "Threads|VmRSS|State" "/proc/$PID/status" 2>&1 || true
  echo "=== /proc/$PID/stat ==="
  cat "/proc/$PID/stat" 2>&1 || true
} | tee "$CARPETA/${SUFIJO}_evidencia_comportamiento.txt"