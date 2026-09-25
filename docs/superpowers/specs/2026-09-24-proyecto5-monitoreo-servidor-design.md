# SPEC — Proyecto 5: Plataforma de monitoreo de un servidor

| Campo | Valor |
|---|---|
| Curso | Sistemas Operativos — UPTC (Mgrt. Fredy Antonio Alarcón Fonseca) |
| Alcance | Primer 50% (semanas 1–8) |
| Estado | **Validada** — lista para plan de implementación |
| Fecha | 2026-09-24 |
| Repo | https://github.com/FerAlvarez25/Plataforma-de-monitoreo-de-un-servidor |

---

## 1. Problema y objetivo

Una empresa tiene un servidor que ejecuta **procesamiento, monitoreo, almacenamiento, generación de reportes y tareas administrativas**. Durante periodos de carga aparecen: CPU elevada, crecimiento de memoria, procesos que no terminan y resultados inconsistentes.

**Objetivo:** construir una plataforma que modele ese servidor con procesos e hilos, demuestre y explique esos síntomas (condición de carrera, interbloqueo, consumo de CPU/memoria), los corrija y permita observar todo con herramientas del SO (`ps`, `pstree`, `top`/`htop`, `ps -eLf`, `/proc`).

**Requisitos mínimos de la guía (12):** proceso administrador · procesos hijos con roles distintos · hilos en ≥2 componentes · jerarquía PID/PPID reconstruible · carga de CPU · crecimiento de memoria · recurso compartido con acceso concurrente · condición de carrera (generar y corregir) · interbloqueo (generar y corregir) · registro de eventos · diagnóstico con herramientas del SO · relación síntoma→causa→corrección.

## 2. Decisiones de diseño (validadas)

| Decisión | Valor | Nota |
|---|---|---|
| Entorno | Linux vía **WSL2/Ubuntu** (desarrollo en Windows) | Evidencia con `/proc`, `ps`, `top` |
| Lenguaje | **Python ≥ 3.10** (`multiprocessing`, `threading`) | Confirmado por el docente |
| Enfoque | **A — Multiprocessing completo** | Adm. + 5 procesos hijos |
| Componentes | Los 5 del contexto | Procesamiento, monitoreo, almacenamiento, reportes, administrativas |
| Flujo de trabajo | TDD (red–green–refactor) + verificación read-only | Skills instaladas |

### Resoluciones específicas

1. **CPU / GIL:** hilos para concurrencia (requisito) **+ N procesos `cargador_cpu`** (hijos de `procesamiento`) con trabajo CPU-intensivo → carga en varios núcleos. El GIL se documenta en el informe.
2. **Interbloqueo entre procesos** (`reportes` ↔ `administrativas`) con dos `multiprocessing.Lock` reales compartidos y `sleep` para ampliar la ventana. Corrección: **orden uniforme** + análisis de Coffman.
3. **Semáforos**: cola productor–consumidor **acotada propia** con `BoundedSemaphore` (empty/full) + buffer compartido + `Lock` de acceso. El `Lock` restante protege la RMW del registro.
4. **Productor–consumidor**: como en (3), implementado a mano (educativo). *Fallback:* `multiprocessing.Queue` si la cola propietaria se vuelve frágil entre procesos.
5. **YAGNI estricto**: sin abstracciones reutilizables; mínimo para el Proyecto 5.

## 3. Arquitectura

```
                    ┌──────────────────────────────┐
                    │   ADMINISTRADOR (PID base)   │
                    │   main.py                    │
                    │  · crea estado compartido    │
                    │  · lanza 5 procesos hijos    │
                    │  · registra eventos globales │
                    └──────────────┬───────────────┘
                                   │ multiprocessing (fork)
   ┌──────────────┬───────────┬────┴──────┬──────────────┬───────────────┐
   ▼              ▼           ▼           ▼              ▼               ▼
 procesamiento almacenamiento reportes    monitoreo      administrativas
 (coord. + N     (hilos      (2 hilos     (1 ciclico)    (1 ciclico)
  cargador_cpu   escritores)  lectores)
  └──► N procesos hijos cargador_cpu (CPU-intensivos)
```

| Proceso hijo | Responsabilidad | Hilos | Recurso |
|---|---|---|---|
| `procesamiento` | Recibe tareas de la cola PQ, instancia N `cargador_cpu` (procesos hijos) que ejecutan trabajo CPU-intensivo; envía resultados a almacenamiento | 1 coordinador + N subprocesos CPU | `cola_tareas`, `cola_resultados` |
| `almacenamiento` | Opera el **registro compartido**: RMW de contadores/registros; escrituras y consultas | 3–4 hilos escritores | `registro` + `lock_registro` |
| `reportes` | Genera resúmenes desde el registro; participa en el escenario de interbloqueo | 2 hilos lectores | `registro`, `lock_metricas`, `lock_registro` |
| `monitoreo` | Muestrea CPU/memoria/hilos desde `/proc` y `ps`; publica en `metricas` | 1 (ciclado) | `/proc`, `metricas` |
| `administrativas` | Depura registros antiguos, simula mantenimiento; contraparte del interbloqueo | 1 (ciclado) | `registro`, `eventos` |

### IPC y estado compartido

| Mecanismo | Tipo | Uso |
|---|---|---|
| `cola_tareas` | Cola PQ acotada propia (semáforos) | Productor–consumidor: llegada → workers |
| `cola_resultados` | `multiprocessing.Queue` | `procesamiento` → `almacenamiento` |
| `registro` | `Manager().dict` + `multiprocessing.Lock` | Recurso crítico: registros y contadores |
| `metricas` | `Manager().dict` | CPU %, RSS, hilos por PID |
| `eventos` | `Manager().list` | Log compartido con timestamp |
| `lock_registro`, `lock_metricas` | `multiprocessing.Lock` reales compartidos | Exclusión mutua; base del interbloqueo |

## 4. Condición de carrera (req. 8)

RMW sobre el recurso compartido **sin protección** en `almacenamiento` (`DEMO_RAZA=True`):

```python
def registrar(id_tarea, tipo):
    n = contador.value              # leer
    time.sleep(trabajo())           # ampliar ventana
    contador.value = n + 1          # escribir → actualización perdida
    registro[id_tarea] = {"tipo": tipo, "estado": "ok"}
```

**Fix (`DEMO_RAZA=False`):** envolver la RMW en `with lock_registro:`.

**Validación:** con N tareas, buggy → `contador < N` (pérdidas); fix → `contador == N` e registro íntegro. Ambas versiones conviven en el mismo código vía flag (la guía pide versión funcional y versión con el problema).

## 5. Interbloqueo (req. 9)

Adquisición en orden inverso entre dos procesos (`DEMO_INTERBLOQUEO=True`):

```python
# reportes.py
with lock_registro:                 # A
    time.sleep(0.5)
    with lock_metricas:             # B → espera circular con administrativas
        generar_resumen()

# administrativas.py
with lock_metricas:                 # B
    time.sleep(0.5)
    with lock_registro:             # A → nunca avanza
        depurar()
```

**Evidencia:** ambos PIDs vivos (`pstree -p`), hilos esperando (`ps -eLf`), CPU ≈ 0, `/proc/<pid>/status`.

**Fix (`DEMO_INTERBLOQUEO=False`):** **orden uniforme** (todos `lock_registro` → `lock_metricas`), rompiendo la espera circular. El informe documenta las 4 condiciones de Coffman en el escenario buggy y cuál elimina la corrección.

## 6. CPU, memoria y monitoreo (reqs. 5, 6, 11, 12)

| Fenómeno | Simulación | Evidencia |
|---|---|---|
| CPU elevada | N `cargador_cpu` (procesos) con checksum SHA-256 / matrices; intensidad configurable | `top`, `ps -eo pid,pcpu,comm`, `/proc/<pid>/stat` |
| Memoria (controlada) | Workers generan resultados de tamaño creciente; `administrativas` depura con límite | `ps -eo pid,rss`, `VmRSS` de `/proc/<pid>/status`, tendencia desde `metricas` |
| Hilos por proceso | Nº configurable | `ps -eLf` (NLWP), `/proc/<pid>/task/` |
| Jerarquía | Árbol admin→5→N | `pstree -p`, `ps -eo pid,ppid,comm` |

`monitoreo` publica muestras en `metricas` para el informe (comparación antes/después en tablas y gráficas).

## 7. Registro de eventos (req. 10)

`[timestamp] [componente] evento` en `eventos` (compartido). Sirve para correlacionar síntoma→causa→corrección (req. 12).

## 8. Evidencias — trazabilidad con §9.3 de la guía

Cada fenómeno (`carrera/`, `interbloqueo/`, `cpu-memoria/`) sigue los **8 pasos** con prefijos secuenciales:

| Paso | Archivo |
|---|---|
| 1. Versión inicial / escenario con el problema | `01_version_inicial_buggy.txt` |
| 2. Ejecución controlada | `02_ejecucion_controlada.txt` |
| 3. Evidencia del comportamiento | `03_evidencia_comportamiento.png` |
| 4. Explicación de la causa | `04_explicacion_causa.md` |
| 5. Modificación implementada | `05_modificacion_implementada.patch` |
| 6. Nueva ejecución | `06_nueva_ejecucion.txt` |
| 7. Evidencia de la corrección | `07_evidencia_correccion.png` |
| 8. Comparación antes/después | `08_comparacion_antes_despues.md` |

Los escenarios (`servidor/demos/`) **exportan automáticamente** estos artefactos.

## 9. Estructura del repositorio

```
servidor/
├── main.py                       # administrador (entrypoint)
├── shared/
│   ├── estado.py                 # Manager + locks + estructuras compartidas
│   ├── registro.py               # RMW del registro (buggy/fix)
│   ├── cola_pq.py                # cola productor-consumidor con semáforos
│   └── eventos.py                # log compartido
├── componentes/
│   ├── procesamiento.py          # PQ consumidor + N cargador_cpu
│   ├── almacenamiento.py         # hilos escritores
│   ├── reportes.py               # resúmenes + deadlock
│   ├── monitoreo.py              # /proc, ps, metricas
│   └── administrativas.py        # housekeeping + deadlock
└── demos/
    ├── escenario_carrera.py
    └── escenario_interbloqueo.py
herramientas/observar.sh          # capturas ps/pstree/top//proc
tests/                            # pytest (unit + escenarios)
docs/evidencias/                  # convención 01–08
```

## 10. Estrategia de pruebas (TDD)

| Nivel | Prueba | Técnica |
|---|---|---|
| Unitarias (deterministas) | Checksum, resúmenes, invariantes del registro | `pytest` sin concurrencia |
| Escenario carrera | Buggy: `contador < N`; fix: `== N` | Ejecución controlada con N fijo |
| Escenario interbloqueo | Buggy: timeout en `join`; fix: termina | Timeouts + verificación de salida |
| Observación SO | Procesos/hilos según ejecución | `observar.sh` + `/proc` |

Los escenarios buggy son no deterministas por naturaleza; se documentan condiciones de reproducción (la guía pide "prueba reproducible").

## 11. Riesgos y fallbacks

| Riesgo | Mitigación |
|---|---|
| Cola PQ propia frágil entre procesos | Fallback a `multiprocessing.Queue` (sin perder requisitos) |
| GIL limita CPU de hilos | Carga repartida en procesos `cargador_cpu`; GIL documentado |
| Interbloqueo no reproducible | `sleep` controlado garantiza la intercalación |
| No determinismo de escenarios buggy | Múltiples iteraciones; invariantes en fix |

## 12. Entregables

Código organizado · README · diagramas (Mermaid/draw.io) · documento técnico · evidencias 01–08 · comparación antes/después · conclusiones · demostración.

---
*Next:* plan de implementación detallado (writing-plans) → implementación TDD → verificación read-only → evidencias.*