#!/usr/bin/env bash
# Captura de uso de CPU/memoria/hilos del árbol de procesos del servidor.
# Uso: capturar_uso.sh <pid_del_servidor> <carpeta> [sufijo]
#     sufijo por defecto "03" -> escribe <sufijo>_uso_cpu_memoria.txt
set -u
PID="${1:?indicar pid del servidor}"
CARPETA="${2:?indicar carpeta de evidencias}"
SUFIJO="${3:-03}"
mkdir -p "$CARPETA"
DESTINO="$CARPETA/${SUFIJO}_uso_cpu_memoria.txt"

recoger() {
  local p="$1"
  [ -r "/proc/$p/status" ] || return
  echo "--- pid $p ($(cat "/proc/$p/comm" 2>/dev/null || true))"
  grep -E "Name|State|Threads|VmRSS|VmSize" "/proc/$p/status" 2>/dev/null || true
  for hijo in $(pgrep -P "$p" 2>/dev/null); do
    recoger "$hijo"
  done
}

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  echo "=== ps -eo pid,ppid,pcpu,rss,comm (ordenado por %CPU) ==="
  ps -eo pid,ppid,pcpu,rss,comm | sort -k3 -nr | head -25
  echo "=== ps -eLf (hilos por proceso: NLWP x TID) ==="
  ps -eLf | grep -E "PID|servidor|python|cargador" | head -40
  echo "=== /proc status por proceso del árbol (recursivo) ==="
  recoger "$PID"
} | tee "$DESTINO"