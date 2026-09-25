"""Exporta evidencias 01-08 de la condición de carrera (docs/evidencias/carrera)."""
import argparse
import os
import subprocess
import sys

FIX = """--- a/servidor/shared/registro.py
+++ b/servidor/shared/registro.py
@@ -10,7 +10,7 @@ def registrar_tarea(estado, id_tarea, tipo, sync=True):
     if sync:
-        _rmw(estado, id_tarea, tipo)      # sin exclusión mutua -> carrera
+        with estado.lock_registro:         # exclusión mutua sobre la RMW
+            _rmw(estado, id_tarea, tipo)
"""

CAUSA = """# Condición de carrera: lectura-modificación-escritura sin exclusión mutua

## Síntoma
Con `--raza`, el contador final es menor al número de tareas esperado
(`registrados < esperados`): se pierden actualizaciones y faltan registros.

## Causa
Varios hilos escritores ejecutan la RMW (`leer contador -> computar -> escribir`)
de forma intercalada sobre `estado.contador`, sin `lock_registro`. Dos hilos leen
el mismo valor `n` y ambos escriben `n+1` -> una actualización se pierde.

## Corrección
Envolver la RMW en `with lock_registro:` (exclusión mutua) hace la operación
atómica. La ejecución corregida entrega `registrados == esperados`.
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Exporta evidencias de la condición de carrera")
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--tiempo-max", type=float, default=60)
    p.add_argument("--carpeta", default=os.path.join("docs", "evidencias", "carrera"))
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
    tmo = max(a.tiempo_max + 15, 30)

    with open(os.path.join(a.carpeta, "01_version_inicial_buggy.txt"), "w", encoding="utf-8") as f:
        f.write("CONDICIÓN DE CARRERA - escenario con el problema\n")
        f.write("mando: " + " ".join(_base_cmd(a, ["--raza"])) + "\n")

    buggy = subprocess.run(_base_cmd(a, ["--raza"]), capture_output=True, text=True, timeout=tmo)
    with open(os.path.join(a.carpeta, "02_ejecucion_controlada.txt"), "w", encoding="utf-8") as f:
        f.write(buggy.stdout)

    fix = subprocess.run(_base_cmd(a, []), capture_output=True, text=True, timeout=tmo)
    with open(os.path.join(a.carpeta, "06_nueva_ejecucion.txt"), "w", encoding="utf-8") as f:
        f.write(fix.stdout)

    with open(os.path.join(a.carpeta, "04_explicacion_causa.md"), "w", encoding="utf-8") as f:
        f.write(CAUSA)
    with open(os.path.join(a.carpeta, "05_modificacion_implementada.patch"), "w", encoding="utf-8") as f:
        f.write(FIX)

    b = _resumen(buggy.stdout)
    f_ = _resumen(fix.stdout)
    with open(os.path.join(a.carpeta, "08_comparacion_antes_despues.md"), "w", encoding="utf-8") as out:
        out.write("# Comparación antes/después - condición de carrera\n\n")
        out.write("| Escenario | Resultado |\n|---|---|\n")
        out.write(f"| Buggy (--raza) | `{b}` |\n")
        out.write(f"| Fix (mutex) | `{f_}` |\n")

    # El paso 03/07 (pstree/ps/top) lo produce herramientas/observar.sh durante la ejecución.
    print("Evidencias carrera escritas en", os.path.abspath(a.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())