# Proyecto 5 — Plataforma de monitoreo de un servidor: Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una plataforma Python que simule un servidor con 5 componentes (procesamiento, monitoreo, almacenamiento, reportes, administrativas) sobre procesos e hilos, demuestre y corrija una condición de carrera y un interbloqueo, y genere evidencias trazables con la §9.3 de la guía.

**Architecture:** Proceso administrador (`main.py`) que crea un estado compartido (`multiprocessing.Manager` + locks reales) y lanza 5 procesos hijos. `procesamiento` lanza N procesos `cargador_cpu` (carga CPU real); `almacenamiento` registra resultados con hilos (RMW buggy/fix); `reportes` y `administrativas` generan resúmenes y demuestran el interbloqueo con orden de locks invertido; `monitoreo` muestrea `/proc` y `ps`; un log compartido registra eventos. Demos exportan evidencias 01–08.

**Tech Stack:** Python ≥ 3.10 (stdlib: `multiprocessing`, `threading`, `hashlib`, `re`, `time`, `subprocess`, `argparse`). Tests: `pytest`. Sin dependencias de runtime.

**Spec:** `docs/superpowers/specs/2026-09-24-proyecto5-monitoreo-servidor-design.md`

## Global Constraints

- Python ≥ 3.10; runtime SOLO stdlib. `pytest` en `requirements-dev.txt`.
- Ejecución/validación primaria en Linux (WSL2/Ubuntu). El código debe ser `spawn`-safe (desarrollo en Windows): los targets de `mp.Process` son funciones de módulo; los `EstadoServidor` y colas se crean DENTRO de las funciones de test (nunca a nivel de módulo).
- Los fenómenos se controlan con flags CLI en `main.py`: `--raza` (DEMO_RAZA) y `--interbloqueo` (DEMO_INTERBLOQUEO). Sin flags = versión corregida.
- Convención de evidencias 01–08 en `docs/evidencias/{carrera,interbloqueo,cpu-memoria}` (ver `docs/evidencias/README.md`).
- Nombres y firmas exactos según bloques **Interfaces** de cada tarea. Un commit por tarea.
- Comando de tests: `python -m pytest tests/ -v` (dentro de WSL2 preferentemente; unit deterministas corren en Windows).

## Review Focus

1. **Cola PQ acotada:** `get()` sobre cola vacía debe bloquear (no lanzar ni devolver basura) y `put()` con capacidad llena debe bloquear hasta que se libere un hueco → test en Task 3.
2. **Registro con `sync=True`:** bajo 8 hilos × 800 registros el contador final debe ser exactamente `800` y el registro íntegro → Task 2.
3. **Demos independientes:** `--raza` sin `--interbloqueo` y viceversa no deben romper el otro fenómeno (el modo buggy de uno no debe colgar el flujo del otro) → Task 12.
4. **Interbloqueo en demo:** con `--interbloqueo` los procesos deben quedar VIVOS (timeout en join, no crash); con fix deben terminar → Tasks 7, 9, 10, 12.
5. **Parsers `/proc`:** nombres con paréntesis (p.ej. `bash (deleted)`) y campos faltantes no deben romper `parsear_pid_stat`/`parsear_status` → Task 8.

---
---

### Task 1: Scaffold del paquete + `shared/estado.py`

**Files:**
- Create: `servidor/__init__.py`, `servidor/shared/__init__.py`, `servidor/componentes/__init__.py`, `servidor/demos/__init__.py`
- Create: `servidor/shared/estado.py`
- Create: `requirements-dev.txt`
- Test: `tests/test_estado.py`

**Interfaces:**
- Produces: `crear_estado() -> EstadoServidor` con atributos `registro` (Manager dict), `contador` (Manager Value int), `metricas` (Manager dict), `eventos` (Manager list), `lock_registro` y `lock_metricas` (`multiprocessing.Lock`), y `_manager` (el `Manager`, usado por tareas posteriores para construir la cola).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_estado.py
from servidor.shared.estado import crear_estado


def test_estado_inicial():
    e = crear_estado()
    assert e.contador.value == 0
    assert len(e.registro) == 0
    assert len(e.metricas) == 0
    assert len(e.eventos) == 0
    assert hasattr(e, "lock_registro") and hasattr(e, "lock_metricas")


def test_locks_adquiribles():
    e = crear_estado()
    e.lock_registro.acquire()
    e.lock_registro.release()
    e.lock_metricas.acquire()
    e.lock_metricas.release()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_estado.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'servidor'`

- [ ] **Step 3: Write minimal implementation**

Crea los `__init__.py` vacíos en `servidor/`, `servidor/shared/`, `servidor/componentes/`, `servidor/demos/` y `requirements-dev.txt` con una línea: `pytest>=8`.

```python
# servidor/shared/estado.py
import multiprocessing as mp


class EstadoServidor:
    """Estado compartido del servidor: estructuras Manager + locks reales."""

    def __init__(self, manager=None):
        self._manager = manager or mp.Manager()
        self.registro = self._manager.dict()        # id -> {"tipo":..., "estado":...}
        self.contador = self._manager.Value("i", 0)  # total de tareas registradas
        self.metricas = self._manager.dict()        # {"cpu_pct":..., "rss_kb":..., "hilos":...}
        self.eventos = self._manager.list()         # log compartido
        self.lock_registro = mp.Lock()
        self.lock_metricas = mp.Lock()


def crear_estado():
    return EstadoServidor()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_estado.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/ requirements-dev.txt tests/test_estado.py
git commit -m "feat: scaffold del paquete y estado compartido (Manager + locks)"
```

---
---

### Task 2: `shared/registro.py` — RMW del registro (buggy/fix)

**Files:**
- Create: `servidor/shared/registro.py`
- Test: `tests/test_registro.py`

**Interfaces:**
- Consumes: `EstadoServidor` de Task 1 (`estado.registro`, `estado.contador`, `estado.lock_registro`).
- Produces:
  - `registrar_tarea(estado, id_tarea, tipo, sync=True)` — RMW; con `sync=True` usa `lock_registro`, con `sync=False` NO (condición de carrera).
  - `conteo_registrado(estado) -> int`
  - `listar_registros(estado) -> list[dict]` (lista de `{"id":..., "tipo":..., "estado":...}`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registro.py
from concurrent.futures import ThreadPoolExecutor

from servidor.shared.estado import crear_estado
from servidor.shared.registro import conteo_registrado, listar_registros, registrar_tarea


def test_secuencial_sync_true():
    e = crear_estado()
    for i in range(100):
        registrar_tarea(e, i, "tipo_a", sync=True)
    assert conteo_registrado(e) == 100
    assert len(listar_registros(e)) == 100


def test_concurrencia_sync_true_consistente():
    e = crear_estado()
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda i: registrar_tarea(e, i, "a", sync=True), range(800)))
    assert conteo_registrado(e) == 800


def test_raza_sync_false_pierde_actualizaciones():
    perdidas = 0
    for _ in range(3):
        e = crear_estado()

        def reg(i):
            registrar_tarea(e, i, "a", sync=False)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(reg, range(800)))
        if conteo_registrado(e) < 800:
            perdidas += 1
    assert perdidas >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_registro.py -v`
Expected: FAIL con `ImportError: cannot import name 'registrar_tarea'`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/shared/registro.py
import time


def _rmw(estado, id_tarea, tipo):
    n = estado.contador.value          # 1) leer
    time.sleep(0.0002)                 # 2) ventana de carrera
    estado.contador.value = n + 1      # 3) escribir
    estado.registro[id_tarea] = {"tipo": tipo, "estado": "ok"}


def registrar_tarea(estado, id_tarea, tipo, sync=True):
    if sync:
        with estado.lock_registro:     # exclusión mutua sobre la RMW
            _rmw(estado, id_tarea, tipo)
    else:
        _rmw(estado, id_tarea, tipo)   # SIN protección -> carrera


def conteo_registrado(estado):
    return estado.contador.value


def listar_registros(estado):
    return [{"id": k, **v} for k, v in estado.registro.items()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_registro.py -v`
Expected: 3 PASS (el tercero puede tardar unos segundos; 3 repeticiones × 800 registros)

- [ ] **Step 5: Commit**

```bash
git add servidor/shared/registro.py tests/test_registro.py
git commit -m "feat: registro compartido con RMW buggy/fix (condición de carrera)"
```

---
---

### Task 3: `shared/cola_pq.py` — cola productor-consumidor acotada con semáforos

**Files:**
- Create: `servidor/shared/cola_pq.py`
- Test: `tests/test_cola_pq.py`

**Interfaces:**
- Consumes: `estado._manager` (Manager) de Task 1.
- Produces: `ColaProductorConsumidor(capacidad, manager)` con métodos:
  - `put(item)` (bloqueante, respeta capacidad)
  - `get()` (bloqueante)
  - `size() -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cola_pq.py
import threading
import time

from servidor.shared.cola_pq import ColaProductorConsumidor
from servidor.shared.estado import crear_estado


def test_orden_fifo_respetando_capacidad():
    e = crear_estado()
    c = ColaProductorConsumidor(4, e._manager)
    assert c.size() == 0
    for i in range(4):
        c.put(i)
    assert c.size() == 4
    for i in range(4):
        assert c.get() == i


def test_capacidad_bloquea_put():
    e = crear_estado()
    c = ColaProductorConsumidor(2, e._manager)
    c.put("a")
    c.put("b")
    insertado = {"ok": False}

    def productor():
        c.put("c")
        insertado["ok"] = True

    h = threading.Thread(target=productor)
    h.start()
    time.sleep(0.2)
    assert not insertado["ok"]        # bloqueado por capacidad llena
    assert c.get() == "a"             # libera un hueco
    h.join(timeout=2)
    assert insertado["ok"]            # ahora sí pudo insertar
    assert c.get() == "b"
    assert c.get() == "c"


def test_get_vacia_bloquea():
    e = crear_estado()
    c = ColaProductorConsumidor(3, e._manager)
    obtenido = {"ok": False}

    def consumidor():
        c.get()
        obtenido["ok"] = True

    h = threading.Thread(target=consumidor)
    h.start()
    time.sleep(0.2)
    assert not obtenido["ok"]         # bloqueado en cola vacía
    c.put("x")
    h.join(timeout=2)
    assert obtenido["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cola_pq.py -v`
Expected: FAIL con `ImportError: cannot import name 'ColaProductorConsumidor'`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/shared/cola_pq.py
import multiprocessing as mp


class ColaProductorConsumidor:
    """Cola acotada compartible entre procesos: semáforos empty/full + mutex."""

    def __init__(self, capacidad, manager):
        self._capacidad = capacidad
        self._buffer = manager.list()
        self._libre = mp.BoundedSemaphore(capacidad)   # huecos disponibles
        self._lleno = mp.Semaphore(0)                  # ítems disponibles
        self._mutex = mp.Lock()

    def put(self, item):
        self._libre.acquire()
        with self._mutex:
            self._buffer.append(item)
        self._lleno.release()

    def get(self):
        self._lleno.acquire()
        with self._mutex:
            item = self._buffer.pop(0)
        self._libre.release()
        return item

    def size(self):
        return len(self._buffer)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cola_pq.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/shared/cola_pq.py tests/test_cola_pq.py
git commit -m "feat: cola productor-consumidor acotada con semáforos"
```

---
---

### Task 4: `shared/eventos.py` — log compartido

**Files:**
- Create: `servidor/shared/eventos.py`
- Test: `tests/test_eventos.py`

**Interfaces:**
- Consumes: `EstadoServidor` (`estado.eventos`).
- Produces: `log_evento(estado, componente, mensaje)`, `leer_eventos(estado) -> list[str]`, `contar_eventos(estado) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eventos.py
import re

from servidor.shared.estado import crear_estado
from servidor.shared.eventos import contar_eventos, leer_eventos, log_evento


def test_log_formato_y_orden():
    e = crear_estado()
    log_evento(e, "admin", "inicio")
    log_evento(e, "monitoreo", "cpu=50%")
    eventos = leer_eventos(e)
    assert contar_eventos(e) == 2
    assert re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[admin\] inicio$", eventos[0])
    assert "[monitoreo] cpu=50%" in eventos[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_eventos.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/shared/eventos.py
import time


def log_evento(estado, componente, mensaje):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    estado.eventos.append(f"[{ts}] [{componente}] {mensaje}")


def leer_eventos(estado):
    return list(estado.eventos)


def contar_eventos(estado):
    return len(estado.eventos)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_eventos.py -v`
Expected: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/shared/eventos.py tests/test_eventos.py
git commit -m "feat: log compartido de eventos con timestamp"
```

---
---

### Task 5: `componentes/procesamiento.py` — CPU y consumo de la cola PQ

**Files:**
- Create: `servidor/componentes/procesamiento.py`
- Test: `tests/test_procesamiento.py`

**Interfaces:**
- Consumes: `ColaProductorConsumidor.get` (Task 3), `log_evento` (Task 4).
- Produces:
  - `trabajo_cpu(peso: int, semilla: int) -> str` — checksum SHA-256 determinista (carga CPU).
  - `cargador_cpu_main(cola_tareas, cola_resultados, intensidad, idx)` — proceso hijo: consume con `iter(cola_tareas.get, None)` y publica `{"id": tarea, "checksum": ..., "cargador": idx}` en `cola_resultados`.
  - `procesamiento_main(cola_tareas, cola_resultados, n_cargadores, intensidad, estado, intervalo=1.0)` — proceso `procesamiento`: hilo de control (log heartbeat) + N procesos `cargador_cpu`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_procesamiento.py
import multiprocessing as mp

from servidor.componentes.procesamiento import cargador_cpu_main, trabajo_cpu
from servidor.shared.cola_pq import ColaProductorConsumidor
from servidor.shared.estado import crear_estado


def test_trabajo_cpu_determinista():
    assert trabajo_cpu(10, 7) == trabajo_cpu(10, 7)
    assert trabajo_cpu(10, 7) != trabajo_cpu(10, 8)


def test_cargador_procesa_lote():
    e = crear_estado()
    cola_t = ColaProductorConsumidor(16, e._manager)
    cola_r = mp.Queue()
    for i in range(5):
        cola_t.put(i)
    cola_t.put(None)                     # centinela de fin
    p = mp.Process(target=cargador_cpu_main, args=(cola_t, cola_r, 5, 0))
    p.start()
    p.join(timeout=10)
    assert not p.is_alive()
    resultados = []
    while not cola_r.empty():
        resultados.append(cola_r.get())
    assert sorted(r["id"] for r in resultados) == [0, 1, 2, 3, 4]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_procesamiento.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/componentes/procesamiento.py
import hashlib
import multiprocessing as mp
import threading as th

from ..shared.eventos import log_evento


def trabajo_cpu(peso, semilla):
    """Trabajo CPU-intensivo determinista: SHA-256 sobre `peso` bloques."""
    h = hashlib.sha256()
    for i in range(peso):
        h.update(str(semilla + i).encode())
    return h.hexdigest()


def cargador_cpu_main(cola_tareas, cola_resultados, intensidad, idx):
    for tarea in iter(cola_tareas.get, None):
        resumen = trabajo_cpu(intensidad, tarea)
        cola_resultados.put({"id": tarea, "checksum": resumen, "cargador": idx})


def procesamiento_main(cola_tareas, cola_resultados, n_cargadores, intensidad, estado, intervalo=1.0):
    detener = th.Event()

    def control():
        while not detener.is_set():
            detener.wait(intervalo)
            log_evento(estado, "procesamiento", "heartbeat control")

    th.Thread(target=control, daemon=True).start()
    procs = [
        mp.Process(target=cargador_cpu_main, args=(cola_tareas, cola_resultados, intensidad, i))
        for i in range(n_cargadores)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    detener.set()
    log_evento(estado, "procesamiento", f"{n_cargadores} cargadores finalizados")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_procesamiento.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/componentes/procesamiento.py tests/test_procesamiento.py
git commit -m "feat: componente procesamiento con cargadores CPU y consumo de cola PQ"
```

---
---

### Task 6: `componentes/almacenamiento.py` — hilos escritores del registro

**Files:**
- Create: `servidor/componentes/almacenamiento.py`
- Test: `tests/test_almacenamiento.py`

**Interfaces:**
- Consumes: `registrar_tarea` (Task 2), `ColaProductorConsumidor`/`mp.Queue` (Task 3).
- Produces:
  - `manejar_resultado(estado, resultado, sync)` — registra `resultado["id"]` con tipo `resultado.get("tipo", "procesado")` y el flag `sync`.
  - `almacenamiento_main(estado, cola_resultados, n_hilos, sync)` — proceso: `n_hilos` threads que consumen `iter(cola_resultados.get, None)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_almacenamiento.py
import multiprocessing as mp

from servidor.componentes.almacenamiento import almacenamiento_main, manejar_resultado
from servidor.shared.estado import crear_estado
from servidor.shared.registro import conteo_registrado


def test_manejar_resultado_sync_true():
    e = crear_estado()
    manejar_resultado(e, {"id": 1, "tipo": "reporte"}, sync=True)
    assert conteo_registrado(e) == 1


def test_almacenamiento_procesa_lote():
    e = crear_estado()
    cola_r = mp.Queue()
    for i in range(10):
        cola_r.put({"id": i, "tipo": "procesado"})
    for _ in range(3):
        cola_r.put(None)               # centinela por hilo escritor
    p = mp.Process(target=almacenamiento_main, args=(e, cola_r, 3, True))
    p.start()
    p.join(timeout=15)
    assert not p.is_alive()
    assert conteo_registrado(e) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_almacenamiento.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/componentes/almacenamiento.py
import threading as th

from ..shared.registro import registrar_tarea


def manejar_resultado(estado, resultado, sync):
    registrar_tarea(estado, resultado["id"], resultado.get("tipo", "procesado"), sync=sync)


def almacenamiento_main(estado, cola_resultados, n_hilos, sync):
    def worker():
        for res in iter(cola_resultados.get, None):
            manejar_resultado(estado, res, sync)

    hilos = [th.Thread(target=worker) for _ in range(n_hilos)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_almacenamiento.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/componentes/almacenamiento.py tests/test_almacenamiento.py
git commit -m "feat: componente almacenamiento con hilos escritores del registro"
```

---
---

### Task 7: `componentes/reportes.py` — resúmenes (participa en el interbloqueo)

**Files:**
- Create: `servidor/componentes/reportes.py`
- Test: `tests/test_reportes.py`

**Interfaces:**
- Consumes: `listar_registros`, `conteo_registrado` (Task 2), `log_evento` (Task 4).
- Produces:
  - `contar_tipos(estado) -> dict` — `{"tipo": cantidad}`.
  - `generar_resumen(estado) -> dict` — adquiere SIEMPRE `lock_registro` → `lock_metricas` (orden uniforme) y devuelve `{"total": int, "tipos": dict}`.
  - `reportes_main(estado, paro, intervalo=0.5)` — bucle que genera resúmenes hasta `paro.is_set()`, con un `time.sleep(0.1)` entre la adquisición de los dos locks (amplía la ventana del deadlock).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reportes.py
from servidor.componentes.reportes import contar_tipos, generar_resumen
from servidor.shared.estado import crear_estado
from servidor.shared.registro import registrar_tarea


def test_resumen_refleja_registro():
    e = crear_estado()
    registrar_tarea(e, 1, "a", sync=True)
    registrar_tarea(e, 2, "b", sync=True)
    registrar_tarea(e, 3, "b", sync=True)
    res = generar_resumen(e)
    assert res["total"] == 3
    assert res["tipos"] == {"a": 1, "b": 2}


def test_contar_tipos():
    e = crear_estado()
    registrar_tarea(e, 1, "x", sync=True)
    registrar_tarea(e, 2, "x", sync=True)
    assert contar_tipos(e) == {"x": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reportes.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/componentes/reportes.py
import time

from ..shared.eventos import log_evento
from ..shared.registro import conteo_registrado, listar_registros


def contar_tipos(estado):
    tipos = {}
    for v in estado.registro.values():
        t = v.get("tipo", "desconocido")
        tipos[t] = tipos.get(t, 0) + 1
    return tipos


def generar_resumen(estado):
    """Orden uniforme registro->metricas (sin inversión en reportes)."""
    with estado.lock_registro:
        time.sleep(0.1)
        with estado.lock_metricas:
            return {"total": conteo_registrado(estado), "tipos": contar_tipos(estado)}


def reportes_main(estado, paro, intervalo=0.5):
    while not paro.is_set():
        generar_resumen(estado)
        paro.wait(intervalo)
    log_evento(estado, "reportes", "finalizado")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reportes.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/componentes/reportes.py tests/test_reportes.py
git commit -m "feat: componente reportes (resúmenes, lock en orden registro->metricas)"
```

---
---

### Task 8: `componentes/monitoreo.py` — parsers `/proc` y muestreo

**Files:**
- Create: `servidor/componentes/monitoreo.py`
- Test: `tests/test_monitoreo.py`

**Interfaces:**
- Consumes: `log_evento` (Task 4).
- Produces:
  - `parsear_pid_stat(contenido: str) -> dict` — `{"utime": int, "stime": int}` (campos 14–15 del stat; el comm puede contener paréntesis: se parte por el último `") "`).
  - `parsear_status(contenido: str) -> dict` — `{"rss_kb": int|None, "hilos": int|None}` (VmRSS, Threads).
  - `muestrear_proceso(pid: int) -> dict` — lee `/proc/<pid>/stat` y `/proc/<pid>/status` (Linux-only).
  - `monitoreo_main(estado, paro, intervalo=1.0)` — muestrea los PIDs en `eventos` (filtra `pid=` de admin), publica en `estado.metricas`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_monitoreo.py
import pytest

from servidor.componentes.monitoreo import (
    muestrear_proceso,
    parsear_pid_stat,
    parsear_status,
)

STAT_FIXTURE = (
    "1234 (servidor) S 1 1234 1234 0 -1 4194560 100 0 0 0 120 80 0 0 "
    "20 0 1 0 100 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
)
STAT_FIXTURE_ALIAS = (
    "5678 (bash (deleted)) S 1 5678 5678 0 -1 4194560 100 0 0 0 55 44 0 0 "
    "20 0 1 0 100 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
)
STATUS_FIXTURE = "Name:\tservidor\nThreads:\t4\nVmRSS:\t      123456 kB\n"


def test_parsear_pid_stat():
    assert parsear_pid_stat(STAT_FIXTURE) == {"utime": 120, "stime": 80}


def test_parsear_pid_stat_con_parentesis():
    assert parsear_pid_stat(STAT_FIXTURE_ALIAS) == {"utime": 55, "stime": 44}


def test_parsear_status():
    assert parsear_status(STATUS_FIXTURE) == {"rss_kb": 123456, "hilos": 4}


@pytest.mark.skipif(not __import__("os").path.exists("/proc"), reason="requiere Linux")
def test_muestreo_real_en_linux():
    datos = muestrear_proceso(1)  # PID 1 (init/systemd) en Linux
    assert "utime" in datos and "rss_kb" in datos
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monitoreo.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/componentes/monitoreo.py
import re


def parsear_pid_stat(contenido):
    partes = contenido.split(") ", 1)          # comm puede contener paréntesis
    if len(partes) != 2:
        return {}
    numeros = partes[1].split()
    # tras ')' los campos numéricos empiezan en field 3 (state) -> índice 0
    # field 14 utime -> índice 11 ; field 15 stime -> índice 12
    try:
        return {"utime": int(numeros[11]), "stime": int(numeros[12])}
    except (IndexError, ValueError):
        return {}


def parsear_status(contenido):
    m_rss = re.search(r"VmRSS:\s*(\d+)\s*kB", contenido)
    m_thr = re.search(r"Threads:\s*(\d+)", contenido)
    return {
        "rss_kb": int(m_rss.group(1)) if m_rss else None,
        "hilos": int(m_thr.group(1)) if m_thr else None,
    }


def muestrear_proceso(pid):
    with open(f"/proc/{pid}/stat") as f:
        stat = parsear_pid_stat(f.read())
    with open(f"/proc/{pid}/status") as f:
        status = parsear_status(f.read())
    return {**stat, **status}


def monitoreo_main(estado, paro, intervalo=1.0):
    while not paro.is_set():
        pids = set()
        for ev in estado.eventos:
            m = re.search(r"pid=(\d+)", ev)
            if m:
                pids.add(int(m.group(1)))
        for pid in list(pids)[:8]:
            try:
                estado.metricas[f"pid_{pid}"] = muestrear_proceso(pid)
            except FileNotFoundError:
                pass
        paro.wait(intervalo)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monitoreo.py -v`
Expected: 4 PASS (el de `/proc` solo en Linux; en Windows se salta)

- [ ] **Step 5: Commit**

```bash
git add servidor/componentes/monitoreo.py tests/test_monitoreo.py
git commit -m "feat: componente monitoreo con parsers de /proc (cpu, rss, hilos)"
```

---
---

### Task 9: `componentes/administrativas.py` — depuración + orden invertido (interbloqueo)

**Files:**
- Create: `servidor/componentes/administrativas.py`
- Test: `tests/test_administrativas.py`, `tests/test_interbloqueo.py`

**Interfaces:**
- Consumes: `listar_registros` / `estado.registro` (Task 2), `log_evento` (Task 4).
- Produces:
  - `depurar_registro(estado, limite, invertido)` — con `invertido=False` adquiere `lock_registro` → `lock_metricas` (uniforme); con `invertido=True` (buggy) adquiere `lock_metricas` → `lock_registro` después de `time.sleep(0.1)` → espera circular con `generar_resumen`.
  - `administrativas_main(estado, limite, invertido, paro, intervalo=0.5)` — bucle de depuración hasta `paro.is_set()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_administrativas.py
from servidor.componentes.administrativas import depurar_registro
from servidor.shared.estado import crear_estado
from servidor.shared.registro import registrar_tarea


def test_depurar_respeta_limite():
    e = crear_estado()
    for i in range(20):
        registrar_tarea(e, i, "a", sync=True)
    depurar_registro(e, limite=5, invertido=False)
    assert len(e.registro) == 5
    assert all(i not in e.registro for i in range(15))  # se eliminan los más antiguos
```

```python
# tests/test_interbloqueo.py
import threading

from servidor.componentes.administrativas import depurar_registro
from servidor.componentes.reportes import generar_resumen
from servidor.shared.estado import crear_estado


def test_orden_invertido_produce_espera_circular():
    e = crear_estado()
    hechos = {"r": False, "a": False}

    def r():
        generar_resumen(e)
        hechos["r"] = True

    def a():
        depurar_registro(e, limite=1, invertido=True)
        hechos["a"] = True

    t1 = threading.Thread(target=r, daemon=True)
    t2 = threading.Thread(target=a, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert t1.is_alive() and t2.is_alive()   # ambos esperan circularmente
    assert not hechos["r"] and not hechos["a"]


def test_orden_uniforme_termina():
    e = crear_estado()
    hechos = {"r": False, "a": False}

    def r():
        generar_resumen(e)
        hechos["r"] = True

    def a():
        depurar_registro(e, limite=1, invertido=False)
        hechos["a"] = True

    t1 = threading.Thread(target=r, daemon=True)
    t2 = threading.Thread(target=a, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert hechos["r"] and hechos["a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_administrativas.py tests/test_interbloqueo.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/componentes/administrativas.py
import time

from ..shared.eventos import log_evento

RUTINA_CORTA = 0.02  # trabajo simulado bajo el primer lock (segundos)


def depurar_registro(estado, limite, invertido):
    if invertido:                       # BUGGY: metricas -> registro (espera circular)
        with estado.lock_metricas:
            time.sleep(0.1)             # amplía la ventana contra reportes
            with estado.lock_registro:
                _podar(estado, limite)
    else:                               # FIX: registro -> metricas (orden uniforme)
        with estado.lock_registro:
            time.sleep(RUTINA_CORTA)
            with estado.lock_metricas:
                _podar(estado, limite)


def _podar(estado, limite):
    ids = list(estado.registro.keys())
    for k in ids[: max(0, len(ids) - limite)]:
        del estado.registro[k]


def administrativas_main(estado, limite, invertido, paro, intervalo=0.5):
    while not paro.is_set():
        depurar_registro(estado, limite, invertido)
        paro.wait(intervalo)
    log_evento(estado, "administrativas", "finalizado")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_administrativas.py tests/test_interbloqueo.py -v`
Expected: 3 PASS (el de espera circular tarda ~2s)

- [ ] **Step 5: Commit**

```bash
git add servidor/componentes/administrativas.py tests/test_administrativas.py tests/test_interbloqueo.py
git commit -m "feat: administrativas (depuración) + interbloqueo por orden invertido de locks"
```

---
---

### Task 10: `servidor/main.py` — administrador (orquestación + generador + watchdog)

**Files:**
- Create: `servidor/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: todas las tareas 1–9 (`crear_estado`, `ColaProductorConsumidor`, `log_evento`, `procesamiento_main`, `almacenamiento_main`, `reportes_main`, `monitoreo_main`, `administrativas_main`).
- Produces: CLI ejecutable `python -m servidor.main` con flags: `--total N` (200), `--intensidad N` (50), `--cargadores N` (3), `--hilos-escritores N` (3), `--capacidad N` (16), `--raza`, `--interbloqueo`, `--demora s` (0.0), `--limite-registros N` (5000), `--tiempo-max s` (60). Devuelve 0 al terminar e imprime `EVENTOS:` + linea `RESUMEN registrados=X esperados=N sync=raza|mutex`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
import subprocess
import sys


def test_smoke_servidor_modo_fix():
    cmd = (
        f"{sys.executable} -m servidor.main --total 20 --intensidad 5 "
        f"--cargadores 2 --hilos-escritores 2 --capacidad 8 --tiempo-max 20"
    )
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=40)
    assert res.returncode == 0, res.stderr
    assert "RESUMEN registrados=20 esperados=20 sync=mutex" in res.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL con `ModuleNotFoundError`/exit != 0

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/main.py
"""Proceso administrador: coordina los 5 componentes del servidor."""
import argparse
import multiprocessing as mp
import sys
import threading
import time

from .shared.cola_pq import ColaProductorConsumidor
from .shared.estado import crear_estado
from .shared.eventos import log_evento
from .componentes.administrativas import administrativas_main
from .componentes.almacenamiento import almacenamiento_main
from .componentes.monitoreo import monitoreo_main
from .componentes.procesamiento import procesamiento_main
from .componentes.reportes import reportes_main


def generador_tareas(cola, total, demora, n_cargadores):
    for i in range(total):
        cola.put(i)
        if demora:
            time.sleep(demora)
    for _ in range(n_cargadores):       # centinelas: detienen la cola PQ
        cola.put(None)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Plataforma de monitoreo de un servidor")
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--raza", action="store_true", help="DEMO_RAZA: RMW sin lock")
    p.add_argument("--interbloqueo", action="store_true", help="DEMO_INTERBLOQUEO: orden invertido")
    p.add_argument("--demora", type=float, default=0.0)
    p.add_argument("--limite-registros", type=int, default=5000)
    p.add_argument("--tiempo-max", type=float, default=60.0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    estado = crear_estado()
    cola_tareas = ColaProductorConsumidor(args.capacidad, estado._manager)
    cola_resultados = mp.Queue()
    paro = mp.Event()

    log_evento(estado, "admin", f"inicio servidor pid={mp.current_process().pid}")

    gen = threading.Thread(
        target=generador_tareas, args=(cola_tareas, args.total, args.demora, args.cargadores), daemon=True
    )
    gen.start()

    hijos = [
        mp.Process(target=procesamiento_main,
                   args=(cola_tareas, cola_resultados, args.cargadores, args.intensidad, estado, 1.0)),
        mp.Process(target=almacenamiento_main,
                   args=(estado, cola_resultados, args.hilos_escritores, not args.raza)),
        mp.Process(target=reportes_main, args=(estado, paro, 0.5)),
        mp.Process(target=monitoreo_main, args=(estado, paro, 1.0)),
        mp.Process(target=administrativas_main, args=(estado, args.limite_registros, args.interbloqueo, paro, 0.5)),
    ]
    for p in hijos:
        p.start()
        log_evento(estado, "admin", f"componente pid={p.pid} iniciado")

    # Watchdog: procesamiento y almacenamiento deben terminar (o quedar colgados en demos)
    for p in hijos[:2]:
        p.join(timeout=args.tiempo_max)
        log_evento(estado, "admin",
                   f"componente pid={p.pid} expirado" if p.is_alive() else f"componente pid={p.pid} finalizado")

    for _ in range(args.hilos_escritores):   # centinelas: detienen almacenamiento
        cola_resultados.put(None)
    for p in hijos[1:2]:
        p.join(timeout=10)

    paro.set()                              # detiene reportes, monitoreo, administrativas
    for p in hijos[2:]:
        p.join(timeout=5)

    sync = "raza" if args.raza else "mutex"
    log_evento(estado, "admin", f"RESUMEN registrados={estado.contador.value} esperados={args.total} sync={sync}")
    log_evento(estado, "admin", f"final servidor metricas={dict(estado.metricas)}")
    print("EVENTOS:")
    for ev in estado.eventos:
        print(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main.py -v`
Expected: 1 PASS (~5–15 s). Si el registro queda corto al final, repite el test (el modo `--raza` no está activo aquí; para `sync=mutex` debe ser exacto).

- [ ] **Step 5: Commit**

```bash
git add servidor/main.py tests/test_main.py
git commit -m "feat: administrador (orquestación, generador de tareas, watchdog CLI)"
```

---
---

### Task 11: `herramientas/observar.sh` — captura de evidencias del SO

**Files:**
- Create: `herramientas/observar.sh`
- Test: `tests/test_observar.py`

**Interfaces:**
- Produces: script bash `observar.sh <pid_servidor> <carpeta_evidencias>` que guarda `pstree -p`, `ps -eLf`, `top -b -n 1` y `/proc/<pid>/status` en `<carpeta_evidencias>/03_evidencia_comportamiento.txt` (y con la misma ejecución, lista para `07`). Requiere `bash` (Linux/WSL2).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_observar.py
import os
import subprocess


def test_script_existe_y_es_bash():
    ruta = os.path.join("herramientas", "observar.sh")
    assert os.path.exists(ruta)
    with open(ruta, encoding="utf-8") as f:
        primera = f.readline().strip()
    assert primera.startswith("#!/usr/bin/env bash")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_observar.py -v`
Expected: FAIL con `AssertionError`

- [ ] **Step 3: Write minimal implementation**

```bash
#!/usr/bin/env bash
# Captura evidencias del SO durante la ejecución del servidor.
# Uso: observar.sh <pid_del_servidor> <carpeta>  (carpeta ej. docs/evidencias/carrera)
set -u
PID="${1:?indicar pid del servidor}"
CARPETA="${2:?indicar carpeta de evidencias}"
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
} | tee "$CARPETA/03_evidencia_comportamiento.txt"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_observar.py -v`
Expected: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add herramientas/observar.sh tests/test_observar.py
git commit -m "feat: script de captura de evidencias del SO (pstree, ps, top, /proc)"
```

---
---

### Task 12: `demos/` — exportación de evidencias 01–08

**Files:**
- Create: `servidor/demos/escenario_carrera.py`
- Create: `servidor/demos/escenario_interbloqueo.py`
- Test: `tests/test_demos.py`

**Interfaces:**
- Consumes: `python -m servidor.main ...` (exit 0, línea `RESUMEN ...` en stdout).
- Produces (running WSL2, en `<CARPETA>`):
  - `01_version_inicial_buggy.txt` — comando + flags que reproducen el problema.
  - `02_ejecucion_controlada.txt` — salida completa con `--raza` / `--interbloqueo`.
  - `03_evidencia_comportamiento.txt` — provocada por `herramientas/observar.sh`.
  - `04_explicacion_causa.md` — texto técnico de la causa.
  - `05_modificacion_implementada.patch` — diff conceptual buggy→fix.
  - `06_nueva_ejecucion.txt` — salida en modo fix.
  - `07_evidencia_correccion.txt` — salida/resumen con fix.
  - `08_comparacion_antes_despues.md` — tabla comparativa generada.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_demos.py
import subprocess
import sys


def test_carrera_exporta_artefactos_minimos():
    cmd = (
        f"{sys.executable} -m servidor.demos.escenario_carrera --total 15 "
        f"--intensidad 3 --cargadores 2 --hilos-escritores 2 --capacidad 8 "
        f"--tiempo-max 15 --carpeta tmp_evidencias_carrera"
    )
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=40)
    assert res.returncode == 0, res.stderr
    import os
    for n in ("01", "02", "06", "08"):
        ruta = os.path.join("tmp_evidencias_carrera", f"{n}_*.txt" if n in ("02", "06") else f"{n}_*.md")
        assert glob_exists(n, "tmp_evidencias_carrera"), f"falta artefacto 0{n}"


def glob_exists(n, carpeta):
    import glob
    return bool(glob.glob(f"{carpeta}/{n}_*.txt") or glob.glob(f"{carpeta}/{n}_*.md"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_demos.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# servidor/demos/escenario_carrera.py
"""Exporta evidencias 01-08 de la condición de carrera (docs/evidencias/carrera)."""
import argparse
import os
import subprocess
import sys

from ..shared.estado import crear_estado

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
    p = argparse.ArgumentParser()
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--tiempo-max", type=float, default=60)
    p.add_argument("--carpeta", default=os.path.join("docs", "evidencias", "carrera"))
    return p.parse_args(argv)


def _base_cmd(a, extra):
    return (
        f"{sys.executable} -m servidor.main --total {a.total} --intensidad {a.intensidad} "
        f"--cargadores {a.cargadores} --hilos-escritores {a.hilos_escritores} "
        f"--capacidad {a.capacidad} --tiempo-max {a.tiempo_max} {extra}"
    )


def main(argv=None):
    a = parse_args(argv)
    os.makedirs(a.carpeta, exist_ok=True)

    with open(os.path.join(a.carpeta, "01_version_inicial_buggy.txt"), "w") as f:
        f.write("CONDICIÓN DE CARRERA - escenario con el problema\n")
        f.write(f"mando: {_base_cmd(a, '--raza').strip()}\n")

    buggy = subprocess.run(_base_cmd(a, "--raza"), shell=True, capture_output=True, text=True)
    with open(os.path.join(a.carpeta, "02_ejecucion_controlada.txt"), "w") as f:
        f.write(buggy.stdout)

    fix = subprocess.run(_base_cmd(a, ""), shell=True, capture_output=True, text=True)
    with open(os.path.join(a.carpeta, "06_nueva_ejecucion.txt"), "w") as f:
        f.write(fix.stdout)

    with open(os.path.join(a.carpeta, "04_explicacion_causa.md"), "w") as f:
        f.write(CAUSA)
    with open(os.path.join(a.carpeta, "05_modificacion_implementada.patch"), "w") as f:
        f.write(FIX)

    _resumen = lambda salida: [l for l in salida.splitlines() if l.startswith("RESUMEN")]
    b = _resumen(buggy.stdout) or ["RESUMEN no disponible"]
    f = _resumen(fix.stdout) or ["RESUMEN no disponible"]
    with open(os.path.join(a.carpeta, "08_comparacion_antes_despues.md"), "w") as out:
        out.write("# Comparación antes/después - condición de carrera\n\n")
        out.write(f"| Escenario | Resultado |\n|---|---|\n")
        out.write(f"| Buggy (--raza) | `{b[0]}` |\n")
        out.write(f"| Fix (mutex) | `{f[0]}` |\n")

    # El paso 03/07 (pstree/ps/top) lo produce herramientas/observar.sh durante la ejecución.
    print("Evidencias carrera escritas en", os.path.abspath(a.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```python
# servidor/demos/escenario_interbloqueo.py
"""Exporta evidencias 01-08 del interbloqueo (docs/evidencias/interbloqueo)."""
import argparse
import os
import subprocess
import sys

CAUSA = """# Interbloqueo: espera circular por adquisición de locks en orden inverso

## Síntoma
Con `--interbloqueo`, `procesamiento`/`almacenamiento` no terminan: quedan vivos
(tiempo máximo superado) y el sistema no completa el resumen.

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
    p = argparse.ArgumentParser()
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--tiempo-max", type=float, default=3, help="corto para evidenciar el cuelgue")
    p.add_argument("--carpeta", default=os.path.join("docs", "evidencias", "interbloqueo"))
    return p.parse_args(argv)


def _base_cmd(a, extra):
    return (
        f"{sys.executable} -m servidor.main --total {a.total} --intensidad {a.intensidad} "
        f"--cargadores {a.cargadores} --hilos-escritores {a.hilos_escritores} "
        f"--capacidad {a.capacidad} --tiempo-max {a.tiempo_max} {extra}"
    )


def main(argv=None):
    a = parse_args(argv)
    os.makedirs(a.carpeta, exist_ok=True)

    with open(os.path.join(a.carpeta, "01_version_inicial_buggy.txt"), "w") as f:
        f.write(f"INTERBLOQUEO - escenario con el problema\nmando: {_base_cmd(a, '--interbloqueo').strip()}\n")

    buggy = subprocess.run(_base_cmd(a, "--interbloqueo"), shell=True, capture_output=True, text=True)
    colgado = "proceso pendiente" if "expirado" in buggy.stdout else "finalizó sin cuelgue (revisar)"
    with open(os.path.join(a.carpeta, "02_ejecucion_controlada.txt"), "w") as f:
        f.write(buggy.stdout)

    fmax = max(a.tiempo_max * 4, 8)
    fix = subprocess.run(_base_cmd(a, ""), shell=True, capture_output=True, text=True, timeout=fmax)
    with open(os.path.join(a.carpeta, "06_nueva_ejecucion.txt"), "w") as f:
        f.write(fix.stdout)

    with open(os.path.join(a.carpeta, "04_explicacion_causa.md"), "w") as f:
        f.write(CAUSA)
    with open(os.path.join(a.carpeta, "05_modificacion_implementada.patch"), "w") as f:
        f.write(FIX)

    with open(os.path.join(a.carpeta, "08_comparacion_antes_despues.md"), "w") as out:
        out.write("# Comparación antes/después - interbloqueo\n\n")
        out.write("| Escenario | Resultado |\n|---|---|\n")
        out.write(f"| Buggy (--interbloqueo) | `{colgado}` |\n")
        out.write("| Fix (orden uniforme) | procesos completan y generan resumen |\n")

    print("Evidencias interbloqueo escritas en", os.path.abspath(a.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run (WSL2): `python -m pytest tests/test_demos.py -v`
Expected: 1 PASS (genera `tmp_evidencias_carrera/`). Luego borra `tmp_evidencias_carrera/` (los artefactos oficiales van a `docs/evidencias/carrera/`).

- [ ] **Step 5: Commit**

```bash
git add servidor/demos/ tests/test_demos.py
git commit -m "feat: demos que exportan evidencias 01-08 de carrera e interbloqueo"
```

---
---

## Self-Review (hecho por quien escribe el plan)

**1. Cobertura de la spec:** §9 estructura → Tasks 1,5,6,7,8,9,10,11,12 · condición de carrera (§4 spec) → Tasks 2 y 12 · interbloqueo (§5 spec) → Tasks 7, 9, 10, 12 · CPU/memoria (§6 spec) → Tasks 5 y 8 · eventos (§7 spec) → Task 4 · PQ con semáforos (§2-3 spec) → Task 3 · evidencias 01–08 (§8 spec) → Tasks 11 y 12 · pruebas TDD (§10 spec) → cada tarea · smokes/CLI → Task 10. Sin requisitos sin tarea.

**2. Placeholder scan:** no hay TBD/TODO/«similar a»; cada paso tiene código real.

**3. Consistencia de tipos:** `registrar_tarea(estado,id,tipo,sync=True)` idéntico en Tasks 2, 6; `generar_resumen(estado)` en 7, 9, 10; `depurar_registro(estado,limite,invertido)` en 9, 10; `ColaProductorConsumidor(capacidad, manager)` en 3, 5, 10; `log_evento(estado,componente,mensaje)` en 4, 5, 7, 8, 9, 10; sentinels `None` consistentes (cola PQ × cargadores; cola_resultados × hilos-escritores). ✓

**4. Review Focus:** los 5 puntos tienen test: PQ bloqueante (Task 3) · registro sync=True exacto (Task 2) · demos independientes (Task 12 con `--tiempo-max` corto y `--raza`/`--interbloqueo` por separado) · interbloqueo vivo vs fix (Tasks 9 y 12) · parsers con paréntesis y campos faltantes (Task 8). ✓

---
---

## Execution Handoff

**Plan** guardado en `docs/superpowers/plans/2026-09-24-proyecto5-implementacion.md`.

**Método de ejecución recomendado:** Native, porque las tareas 2–9 comparten firmas exactas definidas en los bloques Interfaces (los cambios se encadenan de forma determinista y cada tarea cierra con tests y commit), y el costo de contexto por tarea de subagentes no aporta en este tamaño de plan.