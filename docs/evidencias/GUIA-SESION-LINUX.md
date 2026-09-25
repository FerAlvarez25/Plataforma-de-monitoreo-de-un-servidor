# Sesión de evidencias en Linux — Proyecto 5 🖥️

> Esta guía es para generar las evidencias (traza **§9.3** de la guía del curso) en una
> máquina **Linux** (recomendado: **WSL2/Ubuntu** o distribución nativa). Todo el código
> corre igual en Windows, pero **las capturas del SO (`ps`, `pstree`, `top`, `/proc`, `ps -eLf`)
> requieren Linux** porque leen `/proc/<pid>/status` y `/proc/<pid>/stat`.

---

## 1. Requisitos previos (una sola vez)

```bash
sudo apt update
sudo apt install -y python3 python3-pip psmisc procps
python3 -m pip install pytest
```

| Herramienta | Paquete | Para qué |
|---|---|---|
| `python3` (≥ 3.10) | `python3` | Plataforma |
| `pytest` | `python3-pip` + `pip install pytest` | Suite de pruebas |
| `pstree` | `psmisc` | Jerarquía PID/PPID (evidencia) |
| `ps`, `top` | `procps` | Carga CPU/memoria/hilos (evidencia) |

## 2. Clonar y ubicar el proyecto

```bash
git clone https://github.com/FerAlvarez25/Plataforma-de-monitoreo-de-un-servidor.git
cd Plataforma-de-monitoreo-de-un-servidor
chmod +x herramientas/*.sh
```

> Desde Windows, el repositorio ya existe en `C:\Users\luisi\Desktop\OperativosProyecto`
> y es accesible desde WSL2 como `/mnt/c/Users/luisi/Desktop/OperativosProyecto`.

## 3. Ejecutar la sesión de evidencias (todo automático)

```bash
bash herramientas/sesion_evidencias.sh
```

El script (con `set -euo pipefail`) hace:

1. **Suite de pruebas completa** en Linux (incluye el test real de `/proc`).
2. **Condición de carrera** → demo estática (01,02,04,05,06,08) + capturas vivas
   del SO **buggy** (`--raza`) → `03` y **corregida** → `07`.
3. **Interbloqueo** → demo (01,02,04,05,06,08) + capturas vivas con la espera
   circular en curso (`03`) y corregida (`07`).
4. **CPU/memoria** → demo antes/después (01,02,04,05,06,08) + capturas vivas de
   uso CPU/RSS (05 usa además `capturar_uso.sh`).

Resultado: archivos `01…08_*.{txt,md,patch}` en las 3 carpetas
`docs/evidencias/{carrera,interbloqueo,cpu-memoria}/`.

### Ajustar la carga (opcional)

Variables de entorno para equipos pequeños/rápidos:

```bash
TOTAL=200 INTENSIDAD=50 CARGADORES=2 bash herramientas/sesion_evidencias.sh
```

## 4. Trazabilidad §9.3 (los 8 pasos)

| Paso | Nombre del archivo | Carrera | Interbloqueo | CPU/memoria |
|---|---|---|---|---|
| 1. Versión con el problema | `01_version_inicial_buggy.txt` | ✅ flag `--raza` | ✅ flag `--interbloqueo` | ✅ sobrecarga (N cargadores, intensidad alta) |
| 2. Ejecución controlada | `02_ejecucion_controlada.txt` | ✅ salida buggy | ✅ salida con cuelgue | ✅ salida con sobrecarga |
| 3. Evidencia del comportamiento | `03_evidencia_comportamiento.txt` | ✅ `pstree/ps/top/proc` | ✅ procesos vivos en espera | ✅ `top/ps/proc` bajo carga |
| 4. Explicación de la causa | `04_explicacion_causa.md` | ✅ RMW sin mutex | ✅ Coffman (espera circular) | ✅ procesos CPU + buffers |
| 5. Modificación implementada | `05_modificacion_implementada.patch` | ✅ `with lock_registro` | ✅ orden uniforme | ✅ ajuste intensidad/depuración |
| 6. Nueva ejecución | `06_nueva_ejecucion.txt` | ✅ salida corregida | ✅ salida corregida | ✅ salida controlada |
| 7. Evidencia de la corrección | `07_evidencia_correccion.txt` | ✅ captura fix | ✅ captura fix | ✅ captura controlada |
| 8. Comparación antes/después | `08_comparacion_antes_despues.md` | ✅ tabla | ✅ tabla | ✅ tabla |

> Los pasos 3 y 7 en la guía del curso dicen `.png`: aquí se entregan **capturas de
> texto reales de las herramientas del SO** (equivalentes y verificables). Si quieres
> además la imagen, abre la tercera terminal durante el paso correspondiente y
> captura `htop`/`top` (ej. `gnome-screenshot -a`). El dato de `/proc` es texto plano,
> así que la captura `.txt` es igualmente válida como evidencia.

## 5. Verificación manual recomendada (lo que el profe pide)

Durante el paso 3 (mientras `sesion_evidencias.sh` corre) o repetidas a mano:

```bash
# Jerarquía (proceso administrador -> 5 componentes -> N cargador_cpu)
pstree -p <pid_del_admin>

# Hilos por proceso (ps -eLf) — requisito "hilos en >=2 componentes"
ps -eLf | grep -E "servidor|python|cargador" | head -40

# Carga de CPU y memoria
top -b -n 1 | head -25
ps -eo pid,ppid,pcpu,rss,comm | sort -k3 -nr | head -20

# Memoria de un proceso puntual
cat /proc/<pid>/status | grep -E "Threads|VmRSS|State"

# Interbloqueo: con --interbloqueo, reportes/administrativas quedan VIVOS
ps -eo pid,stat,comm | grep -E "servidor|python"
```

Evidencia esperada:
- **Jerarquía**: el log de eventos registra `componente <rol> pid=<pid> iniciado`
  para los 5 componentes y `cargador_cpu <i> pid=<pid> iniciado` para los
  cargadores → correlaciona 1:1 con los PIDs de `pstree -p <admin>`.
- **Carrera buggy**: `RESUMEN registrados < esperados` (`sync=raza`).
- **Carrera fix**: `registrados == esperados` (`sync=mutex`).
- **Interbloqueo**: `expirado` en el log de eventos; en `pstree -p` se ven los dos
  procesos `reportes` y `administrativas` vivos esperando.
- **CPU**: varios procesos `cargador_cpu` con %CPU ≈ 100 en núcleos distintos.

## 6. Entregar

```bash
git add docs/evidencias/
git commit -m "evidencias: traza 01-08 (carrera, interbloqueo, cpu-memoria) en Linux"
git push origin main
```

Revisa que cada carpeta tenga 8 archivos y que `04_explicacion_causa.md`/`08_comparacion_*`
reflejen tus mediciones reales (ajusta los números si difieren de tu hardware).