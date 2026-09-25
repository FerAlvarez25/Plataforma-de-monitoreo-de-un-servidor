# Proyecto 5 — Plataforma de monitoreo de un servidor

Proyecto práctico de **Sistemas Operativos** (UPTC) — Primer 50%.
Aplicación integrada de procesos, hilos, concurrencia, sincronización, interbloqueos, CPU y memoria.

> **Estado:** implementado ✅ — pruebas en verde y sesión de evidencias Linux lista.
> Ver [propuesta-técnica](propuesta-proyecto5.md) y
> [guía de evidencias](docs/evidencias/GUIA-SESION-LINUX.md).

## Estructura

```
servidor/              # código fuente (administrador + 5 componentes + demos)
  main.py              # proceso administrador (CLI, watchdog, centinelas)
  componentes/         # procesamiento, almacenamiento, reportes, monitoreo, administrativas
  shared/              # estado compartido, registro (RMW), cola PQ, eventos
  demos/               # exportadores de evidencias 01–08 (carrera, interbloqueo, cpu-memoria)
herramientas/          # scripts de observación del SO: observar.sh, capturar_uso.sh, sesion_evidencias.sh
tests/                 # pytest: unitarias + escenarios de concurrencia
docs/evidencias/       # traza §9.3: carrera/, interbloqueo/, cpu-memoria/ (+ README y guía)
propuesta-proyecto5.md # spec de diseño
```

## Ejecución paso a paso

### Requisitos

- **Python ≥ 3.10** en Linux/WSL2 o Windows. Ejecución con **solo la biblioteca estándar**.
- `python -m pip install pytest` — solo para correr las pruebas.
- En Linux (evidencias del SO): `sudo apt install -y psmisc procps` (`pstree`, `ps`, `top`).

### Paso 1 — Ubicar el proyecto

```bash
# Ya clonado: solo entra
cd ruta/al/proyecto

# O clónalo:
git clone https://github.com/FerAlvarez25/Plataforma-de-monitoreo-de-un-servidor.git
cd Plataforma-de-monitoreo-de-un-servidor
```

### Paso 2 — Versión corregida (sin bugs)

```bash
python -m servidor.main --total 20 --intensidad 5 --cargadores 2 --hilos-escritores 2 --tiempo-max 20
```

Qué ocurre: el **proceso administrador** lanza los 5 componentes
(`procesamiento`, `almacenamiento`, `reportes`, `monitoreo`, `administrativas`) y
`procesamiento` instancia N `cargador_cpu` (procesos CPU-intensivos). Sin flags
corre con **exclusión mutua** y **orden uniforme de bloqueos**.

Salida esperada:

- Log de eventos con la jerarquía: `componente <rol> pid=... iniciado` y
  `cargador_cpu <i> pid=... iniciado`.
- `RESUMEN registrados=20 esperados=20 sync=mutex` ← **todas las tareas
  registradas consistentemente**.

### Paso 3 — Reproducir la condición de carrera (`--raza`)

```bash
python -m servidor.main --total 20 --intensidad 5 --cargadores 2 --hilos-escritores 2 --demora 0.0002 --raza
```

Salida esperada: `RESUMEN registrados < 20 esperados=20 sync=raza` → se **pierden
actualizaciones** (lectura-modificación-escritura sin `lock`). Repite la ejecución:
el número perdido varía.

### Paso 4 — Reproducir el interbloqueo (`--interbloqueo`)

```bash
python -m servidor.main --total 20 --intensidad 5 --cargadores 2 --hilos-escritores 2 --tiempo-max 3 --interbloqueo
```

Salida esperada: `reportes` y `administrativas` terminan como **`expirado`** (espera
circular tomando los bloqueos en orden inverso: `lock_registro` ↔ `lock_metricas`).
El watchdog del administrador los da por vencidos al superar `--tiempo-max`.

### Paso 5 — Correr las pruebas

```bash
python -m pytest tests/ -v
```

- **Windows:** `28 passed, 1 skipped` (el salto es el muestreo real de `/proc`, solo Linux).
- **Linux:** las 29 pasan (incluye parseo real de `/proc`, `metricas` poblada).

### Paso 6 — Generar evidencias §9.3 (en Linux)

```bash
bash herramientas/sesion_evidencias.sh          # todo automático: carrera, interbloqueo y cpu-memoria
bash herramientas/observar.sh <pid> docs/evidencias/carrera    # captura manual del SO
```

Escribe los archivos `01…08_*` en `docs/evidencias/{carrera,interbloqueo,cpu-memoria}/`.
Guía completa (requisitos, tabla de los 8 pasos, verificación manual):
[`docs/evidencias/GUIA-SESION-LINUX.md`](docs/evidencias/GUIA-SESION-LINUX.md).

### Parámetros de la CLI

| Flag | Default | Qué controla |
|---|---|---|
| `--total` | 200 | nº de tareas a procesar |
| `--intensidad` | 50 | trabajo CPU por tarea (checksum SHA-256) |
| `--cargadores` | 3 | procesos `cargador_cpu` (hijos de `procesamiento`) |
| `--hilos-escritores` | 3 | hilos escritores de `almacenamiento` |
| `--capacidad` | 16 | tamaño de la cola PQ (productor–consumidor) |
| `--demora` | 0.0 | pausa entre tareas (hace visible la raza) |
| `--limite-registros` | 5000 | tope del registro compartido (memoria acotada) |
| `--tiempo-max` | 60 | tiempo límite del watchdog en segundos |
| `--raza` | off | **DEMO_RAZA**: RMW sin `lock` (condition de carrera) |
| `--interbloqueo` | off | **DEMO_INTERBLOQUEO**: orden de bloqueos invertido |

> Nota Windows: la plataforma corre igual (spawn), pero `metricas={}` porque no
> hay `/proc`; las evidencias del SO se generan en Linux.

## Evidencias

`docs/evidencias/` sigue la **traza de 8 pasos** (§9.3 de la guía) con prefijos
`01…08` en tres carpetas (`carrera`, `interbloqueo`, `cpu-memoria`). Convención de
nombres: [`docs/evidencias/README.md`](docs/evidencias/README.md).