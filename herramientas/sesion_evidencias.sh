#!/usr/bin/env bash
# ============================================================================
#  Sesión de evidencias — Proyecto 5: Plataforma de monitoreo de un servidor
# ----------------------------------------------------------------------------
#  Genera los 8 artefactos (traza §9.3 de la guía) en:
#    docs/evidencias/carrera/         condición de carrera   (buggy -> fix)
#    docs/evidencias/interbloqueo/    espera circular        (buggy -> fix)
#    docs/evidencias/cpu-memoria/     carga CPU/memoria      (alto -> controlado)
#
#  Uso:  bash herramientas/sesion_evidencias.sh
#  Requisitos: Linux (WSL2/Ubuntu o nativo), python3 >= 3.10 con pytest,
#              psmisc (pstree) y procps (ps, top). Sin flags -> defaults
#              razonables para evidencia; se pueden ajustar con variables de
#              entorno (TOTAL, INTENSIDAD, CARGADORES, ...).
# ============================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

PY="${PYTHON:-python3}"
CARRERA="docs/evidencias/carrera"
INTERBLOQUEO="docs/evidencias/interbloqueo"
CPU_MEM="docs/evidencias/cpu-memoria"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Parámetros configurables (sobreescribibles por entorno)
TOTAL="${TOTAL:-300}"
INTENSIDAD="${INTENSIDAD:-80}"
CARGADORES="${CARGADORES:-3}"
ESCRITORES="${ESCRITORES:-4}"
CAPACIDAD="${CAPACIDAD:-16}"
TMPO_MAX="${TMPO_MAX:-60}"

echo "==> 0) Suite de pruebas (incluye parseo real de /proc)"
"$PY" -m pytest tests/ -q

# ---------------------------------------------------------------------------
# Condición de carrera
# ---------------------------------------------------------------------------
echo "==> Carrera: artefactos estáticos (01,02,04,05,06,08)"
"$PY" -m servidor.demos.escenario_carrera \
    --total "$TOTAL" --intensidad "$INTENSIDAD" --cargadores "$CARGADORES" \
    --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" --tiempo-max "$TMPO_MAX"

echo "==> Carrera: evidencia 03 (captura viva del SO, escenario buggy --raza)"
"$PY" -m servidor.main --total "$TOTAL" --intensidad "$INTENSIDAD" \
    --cargadores "$CARGADORES" --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max "$TMPO_MAX" --demora 0.05 --raza > "$TMP/raza.log" 2>&1 &
PID_RAZA=$!
sleep 3
bash herramientas/observar.sh "$PID_RAZA" "$CARRERA" "03"
wait "$PID_RAZA" || true
grep -E "expirado|RESUMEN" "$TMP/raza.log" | tail -5 || true

echo "==> Carrera: evidencia 07 (captura viva del SO, corregido)"
"$PY" -m servidor.main --total "$TOTAL" --intensidad "$INTENSIDAD" \
    --cargadores "$CARGADORES" --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max "$TMPO_MAX" --demora 0.05 > "$TMP/fix.log" 2>&1 &
PID_FIX=$!
sleep 3
bash herramientas/observar.sh "$PID_FIX" "$CARRERA" "07"
wait "$PID_FIX" || true
grep -E "resumen|RESUMEN" "$TMP/fix.log" | tail -5 || true

# ---------------------------------------------------------------------------
# Interbloqueo
# ---------------------------------------------------------------------------
echo "==> Interbloqueo: artefactos estáticos (01,02,04,05,06,08)"
"$PY" -m servidor.demos.escenario_interbloqueo \
    --total "$((TOTAL / 2))" --intensidad "$((INTENSIDAD / 2))" --cargadores "$CARGADORES" \
    --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" --tiempo-max 3

echo "==> Interbloqueo: evidencia 03 (procesos vivos en espera circular)"
"$PY" -m servidor.main --total "$((TOTAL / 2))" --intensidad "$((INTENSIDAD / 2))" \
    --cargadores "$CARGADORES" --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max 8 --interbloqueo > "$TMP/bloq.log" 2>&1 &
PID_BLOQ=$!
sleep 4
bash herramientas/observar.sh "$PID_BLOQ" "$INTERBLOQUEO" "03"
wait "$PID_BLOQ" || true
grep -E "expirado" "$TMP/bloq.log" | head -5 || true

echo "==> Interbloqueo: evidencia 07 (corregido, todos finalizan)"
"$PY" -m servidor.main --total "$((TOTAL / 2))" --intensidad "$((INTENSIDAD / 2))" \
    --cargadores "$CARGADORES" --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max 10 > "$TMP/bloq_fix.log" 2>&1 &
PID_BLOQ_FIX=$!
sleep 4
bash herramientas/observar.sh "$PID_BLOQ_FIX" "$INTERBLOQUEO" "07"
wait "$PID_BLOQ_FIX" || true
grep -E "expirado|RESUMEN" "$TMP/bloq_fix.log" | tail -5 || true

# ---------------------------------------------------------------------------
# CPU y memoria
# ---------------------------------------------------------------------------
echo "==> CPU/memoria: artefactos estáticos (01,02,04,05,06,08)"
"$PY" -m servidor.demos.escenario_cpu_memoria \
    --total-alta "$((TOTAL + 100))" --intensidad-alta "$((INTENSIDAD * 3))" --cargadores-alta "$CARGADORES" \
    --total-baja "$((TOTAL / 2))" --intensidad-baja "$((INTENSIDAD / 4))" --cargadores-baja 1 \
    --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" --tiempo-max "$TMPO_MAX"

echo "==> CPU/memoria: evidencia 03 (captura viva bajo sobrecarga)"
"$PY" -m servidor.main --total "$((TOTAL + 100))" --intensidad "$((INTENSIDAD * 3))" \
    --cargadores "$CARGADORES" --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max "$TMPO_MAX" --demora 0.02 > "$TMP/cpu_alta.log" 2>&1 &
PID_CPU=$!
sleep 3
bash herramientas/observar.sh "$PID_CPU" "$CPU_MEM" "03"
bash herramientas/capturar_uso.sh "$PID_CPU" "$CPU_MEM" "03" || true
wait "$PID_CPU" || true

echo "==> CPU/memoria: evidencia 07 (captura viva con carga controlada)"
"$PY" -m servidor.main --total "$((TOTAL / 2))" --intensidad "$((INTENSIDAD / 4))" \
    --cargadores 1 --hilos-escritores "$ESCRITORES" --capacidad "$CAPACIDAD" \
    --tiempo-max "$TMPO_MAX" --demora 0.02 > "$TMP/cpu_baja.log" 2>&1 &
PID_CPU_B=$!
sleep 3
bash herramientas/observar.sh "$PID_CPU_B" "$CPU_MEM" "07"
bash herramientas/capturar_uso.sh "$PID_CPU_B" "$CPU_MEM" "07" || true
wait "$PID_CPU_B" || true

echo
echo "==> Evidencias generadas:"
find docs/evidencias -type f -not -name ".gitkeep" | sort
echo "==> Revisa y haz commit de docs/evidencias/ (git add + commit + push)."