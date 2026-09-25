"""Exporta evidencias 01-08 de CPU/memoria (docs/evidencias/cpu-memoria).

"Antes" = sobrecarga (N cargadores, intensidad alta). "Después" = carga
controlada (menos cargadores, intensidad baja + depuración con límite).
"""
import argparse
import os
import subprocess
import sys

CAUSA = """# Carga de CPU y memoria en un servidor multiproceso

## Síntoma (escenario "antes")
Con `--cargadores-alta N` e `--intensidad-alta` alta, varios procesos
`cargador_cpu` (hijos de `procesamiento`) saturan los núcleos: `top` / `ps`
muestran %CPU elevados por proceso (≈100% por núcleo) y, conforme avanzan las
tareas, los buffers compartidos (cola PQ, `cola_resultados`, `registro`) crecen:
`VmRSS` de `/proc/<pid>/status` sube.

## Causa
- **CPU:** el trabajo intensivo (checksum SHA-256 sobre `peso` bloques) corre en
  N procesos reales. Al ser procesos, la carga se reparte en varios núcleos (el
  GIL solo limita hilos del mismo proceso; aquí la concurrencia CPU es entre
  procesos, y se documenta).
- **Memoria:** los resultados intermediarios y el registro compartido con el
  `Manager` acumulan ítems; sin depuración, el `registro` crece sin límite.

## Corrección (escenario "después")
- Ajustar intensidad y nº de cargadores a la capacidad del equipo.
- `administrativas` depura el registro con `--limite-registros`
  (retención de los N más recientes), acotando la memoria.
- `monitoreo` muestra la tendencia (utime, VmRSS, Threads por PID) para
  verificar que la carga vuelve a valores base.
"""

FIX = """--- a/servidor/main.py
+++ b/servidor/main.py
@@ -28,13 +28,13 @@ def parse_args(argv=None):
     p.add_argument("--total", type=int, default=200)
-    p.add_argument("--intensidad", type=int, default=50)
+    p.add_argument("--intensidad", type=int, default=10)      # ajuste de carga
-    p.add_argument("--cargadores", type=int, default=3)
+    p.add_argument("--cargadores", type=int, default=1)       # ajuste de núcleos
     p.add_argument("--hilos-escritores", type=int, default=3)
     p.add_argument("--capacidad", type=int, default=16)
     p.add_argument("--raza", action=\"store_true\", help=\"DEMO_RAZA: RMW sin lock\")
     p.add_argument("--interbloqueo\", action=\"store_true\", help=\"DEMO_INTERBLOQUEO: orden invertido\")
     p.add_argument("--demora\", type=float, default=0.0)
-    p.add_argument("--limite-registros\", type=int, default=5000)
+    p.add_argument("--limite-registros\", type=int, default=500)  # memoria acotada
     p.add_argument("--tiempo-max\", type=float, default=60.0)
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Exporta evidencias de CPU/memoria")
    p.add_argument("--total-alta", type=int, default=400)
    p.add_argument("--intensidad-alta", type=int, default=200)
    p.add_argument("--cargadores-alta", type=int, default=3)
    p.add_argument("--total-baja", type=int, default=200)
    p.add_argument("--intensidad-baja", type=int, default=10)
    p.add_argument("--cargadores-baja", type=int, default=1)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--tiempo-max", type=float, default=60)
    p.add_argument("--carpeta", default=os.path.join("docs", "evidencias", "cpu-memoria"))
    return p.parse_args(argv)


def _cmd(a, total, intensidad, cargadores):
    return [
        sys.executable, "-m", "servidor.main",
        "--total", str(total), "--intensidad", str(intensidad),
        "--cargadores", str(cargadores),
        "--hilos-escritores", str(a.hilos_escritores),
        "--capacidad", str(a.capacidad), "--tiempo-max", str(a.tiempo_max),
    ]


def _linea(salida, prefijo):
    for linea in salida.splitlines():
        if linea.startswith(prefijo):
            return linea
    return f"{prefijo} no disponible"


def main(argv=None):
    a = parse_args(argv)
    os.makedirs(a.carpeta, exist_ok=True)
    tmo = max(a.tiempo_max + 15, 30)

    cmd_alta = _cmd(a, a.total_alta, a.intensidad_alta, a.cargadores_alta)
    cmd_baja = _cmd(a, a.total_baja, a.intensidad_baja, a.cargadores_baja)

    with open(os.path.join(a.carpeta, "01_version_inicial_buggy.txt"), "w", encoding="utf-8") as f:
        f.write("CPU/MEMORIA - escenario con sobrecarga\n")
        f.write("mando: " + " ".join(cmd_alta) + "\n")

    alta = subprocess.run(cmd_alta, capture_output=True, text=True, timeout=tmo)
    with open(os.path.join(a.carpeta, "02_ejecucion_controlada.txt"), "w", encoding="utf-8") as f:
        f.write(alta.stdout)

    baja = subprocess.run(cmd_baja, capture_output=True, text=True, timeout=tmo)
    with open(os.path.join(a.carpeta, "06_nueva_ejecucion.txt"), "w", encoding="utf-8") as f:
        f.write(baja.stdout)

    with open(os.path.join(a.carpeta, "04_explicacion_causa.md"), "w", encoding="utf-8") as f:
        f.write(CAUSA)
    with open(os.path.join(a.carpeta, "05_modificacion_implementada.patch"), "w", encoding="utf-8") as f:
        f.write(FIX)

    with open(os.path.join(a.carpeta, "08_comparacion_antes_despues.md"), "w", encoding="utf-8") as out:
        out.write("# Comparación antes/después - CPU y memoria\n\n")
        out.write("| Escenario | Configuración | Resumen | Métricas (muestra final) |\n")
        out.write("|---|---|---|---|\n")
        out.write(f"| Antes (sobrecarga) | "
                  f"{a.cargadores_alta} cargadores, intensidad {a.intensidad_alta}, "
                  f"{a.total_alta} tareas | `{_linea(alta.stdout, 'RESUMEN')}` | "
                  f"`{_linea(alta.stdout, 'final servidor metricas')}` |\n")
        out.write(f"| Después (controlada) | "
                  f"{a.cargadores_baja} cargadores, intensidad {a.intensidad_baja}, "
                  f"{a.total_baja} tareas | `{_linea(baja.stdout, 'RESUMEN')}` | "
                  f"`{_linea(baja.stdout, 'final servidor metricas')}` |\n")
        out.write("\nLas capturas vivas de `top`, `ps` y `/proc` (antes/después) quedan "
                  "en 03_evidencia_comportamiento y 07_evidencia_correccion (sesión en Linux).\n")

    print("Evidencias cpu-memoria escritas en", os.path.abspath(a.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())