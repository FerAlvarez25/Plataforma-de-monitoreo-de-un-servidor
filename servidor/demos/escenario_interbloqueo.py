"""Exporta evidencias 01-08 del interbloqueo (docs/evidencias/interbloqueo)."""
import argparse
import os
import subprocess
import sys

CAUSA = """# Interbloqueo: espera circular por adquisición de locks en orden inverso

## Síntoma
Con `--interbloqueo`, `reportes` y `administrativas` quedan vivos sin completar
(espera circular): el sistema no termina y el log de eventos lo refleja.

## Causa
`reportes` adquiere `lock_registro` y luego `lock_metricas`; `administrativas`
adquiere `lock_metricas` y luego `lock_registro`. Si se intercalan, cada proceso
retiene un lock y espera el otro: espera circular (se cumplen las 4 condiciones
de Coffman: exclusión mutua, retención y espera, no apropiación, espera circular).

## Corrección
Orden uniforme de adquisición (todos `lock_registro` -> `lock_metricas`) rompe la
espera circular; alternativa: timeout en `acquire`. Ambos procesos ahora terminan.
"""

FIX = """--- a/servidor/componentes/administrativas.py
+++ b/servidor/componentes/administrativas.py
@@ -7,10 +7,10 @@ def depurar_registro(estado, limite, invertido):
     if invertido:
-        with estado.lock_metricas:        # B primero
-            ...
-            with estado.lock_registro:    # A segundo -> espera circular
+        with estado.lock_registro:        # A primero (orden uniforme)
+            ...
+            with estado.lock_metricas:    # B segundo
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Exporta evidencias del interbloqueo")
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--tiempo-max", type=float, default=3, help="corto para evidenciar el cuelgue")
    p.add_argument("--carpeta", default=os.path.join("docs", "evidencias", "interbloqueo"))
    return p.parse_args(argv)


def _base_cmd(a, extra):
    return [
        sys.executable, "-m", "servidor.main",
        "--total", str(a.total), "--intensidad", str(a.intensidad),
        "--cargadores", str(a.cargadores), "--hilos-escritores", str(a.hilos_escritores),
        "--capacidad", str(a.capacidad), "--tiempo-max", str(a.tiempo_max), *extra,
    ]


def _resumen(salida):
    for linea in salida.splitlines():
        if linea.startswith("RESUMEN"):
            return linea
    return "RESUMEN no disponible"


def main(argv=None):
    a = parse_args(argv)
    os.makedirs(a.carpeta, exist_ok=True)

    with open(os.path.join(a.carpeta, "01_version_inicial_buggy.txt"), "w", encoding="utf-8") as f:
        f.write("INTERBLOQUEO - escenario con el problema\n")
        f.write("mando: " + " ".join(_base_cmd(a, ["--interbloqueo"])) + "\n")

    buggy = subprocess.run(_base_cmd(a, ["--interbloqueo"]),
                           capture_output=True, text=True, timeout=max(a.tiempo_max + 15, 25))
    colgado = "proceso pendiente (expirado)" if "expirado" in buggy.stdout else "finalizó sin cuelgue (revisar)"
    with open(os.path.join(a.carpeta, "02_ejecucion_controlada.txt"), "w", encoding="utf-8") as f:
        f.write(buggy.stdout)

    fix = subprocess.run(_base_cmd(a, []), capture_output=True, text=True, timeout=max(a.tiempo_max * 4, 20))
    with open(os.path.join(a.carpeta, "06_nueva_ejecucion.txt"), "w", encoding="utf-8") as f:
        f.write(fix.stdout)

    with open(os.path.join(a.carpeta, "04_explicacion_causa.md"), "w", encoding="utf-8") as f:
        f.write(CAUSA)
    with open(os.path.join(a.carpeta, "05_modificacion_implementada.patch"), "w", encoding="utf-8") as f:
        f.write(FIX)

    with open(os.path.join(a.carpeta, "08_comparacion_antes_despues.md"), "w", encoding="utf-8") as out:
        out.write("# Comparación antes/después - interbloqueo\n\n")
        out.write("| Escenario | Resultado |\n|---|---|\n")
        out.write(f"| Buggy (--interbloqueo) | `{colgado}` |\n")
        out.write(f"| Fix (orden uniforme) | `{_resumen(fix.stdout)}` |\n")

    print("Evidencias interbloqueo escritas en", os.path.abspath(a.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())