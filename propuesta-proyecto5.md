# Propuesta técnica — Proyecto 5: Plataforma de monitoreo de un servidor

> **Curso:** Sistemas Operativos — Universidad Pedagógica y Tecnológica de Colombia (UPTC)
> **Docente:** Mgrt. Fredy Antonio Alarcón Fonseca
> **Alcance:** Primer 50% (semanas 1–8)
> **Estado:** Propuesta en validación (documento para revisión con otra IA)
> **Fecha:** 2026-09-24

---

## 1. Contexto y objetivos

El proyecto integra los conceptos de las semanas 1–8: **procesos, hilos, concurrencia, sincronización, interbloqueos, CPU y memoria**. La solución debe construir un sistema que:

1. Simule una situación real de procesamiento concurrente.
2. Permita **observar, diagnosticar y validar** el comportamiento con herramientas del sistema operativo (`ps`, `pstree`, `top`/`htop`, `ps -eLf`, `/proc`).
3. Demuestre problemas de concurrencia reales (condición de carrera e interbloqueo), los explique, los corrija y compare **antes/después**.

### Objetivo del Proyecto 5 (extraído de la guía)

Desarrollar la plataforma de monitoreo de un servidor con los siguientes **requisitos mínimos**:

| # | Requisito |
|---|---|
| 1 | Proceso principal que administre los componentes |
| 2 | Procesos hijos con responsabilidades diferentes |
| 3 | Múltiples hilos en al menos dos componentes |
| 4 | Jerarquía reconstruible mediante PID y PPID |
| 5 | Simular carga elevada de CPU |
| 6 | Simular crecimiento controlado de memoria |
| 7 | Acceso concurrente a un recurso compartido |
| 8 | Generar deliberadamente una condición de carrera y corregirla |
| 9 | Generar deliberadamente un interbloqueo y corregirlo |
| 10 | Registrar eventos relevantes |
| 11 | Usar herramientas del sistema operativo para diagnosticar |
| 12 | Relacionar cada síntoma con su causa y con la corrección implementada |

### Contexto del problema (de la guía)

> Una empresa tiene un servidor que ejecuta procesamiento, monitoreo, almacenamiento, generación de reportes y tareas administrativas. Durante periodos de carga se presentan: CPU elevada, crecimiento de memoria, procesos que no terminan y resultados inconsistentes.

---

## 2. Decisiones ya tomadas

| Decisión | Valor | Justificación |
|---|---|---|
| **Entorno de ejecución** | Linux vía **WSL2 (Ubuntu)** | La guía exige Linux y herramientas `/proc`, `ps`, `top`. WSL2 permite validarlas desde Windows. |
| **Lenguaje** | **Python** (confirmado por el docente) | Recomendado por la guía; `multiprocessing`/`threading` expresan bien los conceptos de SO. |
| **Enfoque** | **A — Multiprocessing completo** (administrador + 5 procesos hijos) | Único enfoque que integra procesos, hilos, jerarquía PID/PPID, condición de carrera e interbloqueo con evidencia rica. |
| **Componentes** | Los **5 del contexto**: procesamiento, monitoreo, almacenamiento, reportes, administrativas | Máxima riqueza de evidencia sin exceso de código. |
| **Flujo de trabajo** | TDD (red–green–refactor) + skill `verifier-diffs-tests` como auditoría | Aplica la disciplina del curso y mejora la calidad del entregable. |

---

## 3. Arquitectura propuesta

### 3.1 Diagrama general

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
 (3-5 workers)  (3-4 escr.)  (2 lect.)    (1 ciclico)    (1 ciclico)
   CPU carga      recurso     resumenes    muestra        depura y
   + GIL          crítico     + deadlock   /proc, ps      eventos
```

### 3.2 Procesos, hilos y responsabilidades

| Proceso hijo | Responsabilidad | Hilos | Recurso que toca |
|---|---|---|---|
| **procesamiento** | Consume tareas de la cola productor–consumidor; ejecuta trabajo **CPU-intensivo** (checksum, multiplicación de matrices); envía resultados a almacenamiento | 3–5 workers | `cola_tareas` (consume) |
| **almacenamiento** | Posee y opera el **registro compartido** (estructura crítica): escribe registros, actualiza contadores, responde consultas | 3–4 hilos escritores | `registro` + `lock_registro` |
| **reportes** | Genera resúmenes leyendo el registro; **escenario del interbloqueo** | 2 hilos | `registro`, `lock_metricas` |
| **monitoreo** | Muestrea CPU, memoria y nº de hilos desde `/proc` y `ps`; publica en `metricas` | 1 (ciclado) | `/proc`, `metricas` |
| **administrativas** | Housekeeping: depura registros antiguos, simula eventos de mantenimiento; **contraparte del interbloqueo** | 1 (ciclado) | `registro`, `eventos` |

**Cumplimiento de requisitos:** #1 (admin), #2 (5 hijos con roles distintos), #3 (hilos en procesamiento, almacenamiento y reportes ≥ 2), #4 (jerarquía padre→hijos reconstruible con `pstree -p` / `ps -eLf`).

### 3.3 Comunicación entre procesos (IPC)

| Mecanismo | Tipo | Uso |
|---|---|---|
| `cola_tareas` | `multiprocessing.Queue` | **Productor–consumidor**: el administrador (o un generador de llegadas) encola tareas; los workers de `procesamiento` las consumen |
| `cola_resultados` | `multiprocessing.Queue` | `procesamiento` → `almacenamiento` (solicitudes de registro) |
| `registro` | Diccionario/lista vía `multiprocessing.Manager()` | **Recurso compartido crítico**: registros de tareas y contadores |
| `metricas` | Dict vía `Manager` | CPU %, memoria RSS, nº hilos por PID; lo llena `monitoreo` |
| `eventos` | Lista vía `Manager` | Log compartido `timestamp \| componente \| evento` (requisito 10) |
| `Lock`s | `multiprocessing.Lock` (compartidos) | Exclusión mutua sobre cada estructura crítica |

**Nota de diseño:** se preferirá `multiprocessing.Lock` real compartido (pasado como argumento a los procesos) sobre `lock` proxy de `Manager`, porque permite demostrar el interbloqueo **entre procesos** (ambos permanecen vivos y bloqueados, observable con `ps`/`pstree`).

---

## 4. Recurso compartido y condición de carrera

### 4.1 El "recurso crítico": el registro

El registro modela el estado del servidor:

```python
# shared/estado.py  (concepto)
class EstadoServidor:
    def __init__(self):
        manager = multiprocessing.Manager()
        self.registro  = manager.dict()      # id_tarea -> {"tipo":..., "estado":..., ...}
        self.contador  = manager.Value('i', 0)  # total de tareas registradas
        self.metricas  = manager.dict()      # {"cpu":..., "rss_kb":..., "hilos": {...}}
        self.eventos   = manager.list()      # log compartido
        self.lock_registro = multiprocessing.Lock()
        self.lock_metricas = multiprocessing.Lock()
```

### 4.2 Generación deliberada de la condición de carrera (requisito 8)

**Escenario:** los hilos escritores de `almacenamiento` hacen **lectura-modificación-escritura** (RMW) sobre el recurso compartido **sin protección**:

```python
# Versión BUGGY (DEMO_RAZA = True)
def registrar(id_tarea, tipo):
    # ---- sin lock ----
    n = contador.value            # 1) leer
    time.sleep(ejecutar_trabajo())# 2) pequeño intervalo (amplía la ventana)
    contador.value = n + 1        # 3) escribir  → actualizaciones perdidas
    registro[id_tarea] = {"tipo": tipo, "estado": "ok"}
```

Con N hilos concurrentes, el contador final es **menor** al esperado y se pierden actualizaciones → *resultados inconsistentes* (el síntoma que menciona el contexto).

**Corrección (versión FIX):** exclusión mutua con `lock_registro` alrededor de la RMW:

```python
def registrar(id_tarea, tipo):
    with lock_registro:                     # exclusión mutua
        contador.value += 1
        registro[id_tarea] = {"tipo": tipo, "estado": "ok"}
```

**Validación antes/después:** ejecutar con N tareas (p. ej. 500) y verificar:
- Buggy: `contador < N`, registros faltantes/repetidos, contadores por tipo inconsistentes.
- Fix: `contador == N`, registro íntegro.

El flag `DEMO_RAZA` permite obtener **ambas versiones del mismo código** (la guía pide conservar una versión funcional y una con el problema).

### 4.3 Sobre el GIL

Python limita el paralelismo real de hilos CPU-bound (GIL). Implicación de diseño:
- El **trabajo CPU-intensivo** se reparte entre los **procesos** (paralelismo real) y los hilos de `procesamiento` demuestran concurrencia de hilos con escrituras cortas al registro.
- Aun con GIL, `top` muestra el núcleo del proceso `procesamiento` al 100% (el fenómeno pedido es *observable* y *explicable*; el GIL es además un buen tema para el informe).

> **Pregunta abierta para validación:** ¿prefieren que la carga de CPU la hagan los hilos de un solo proceso (GIL, ~1 núcleo) o que se reparta entre procesos (varios núcleos)? Se propone la segunda, con el GIL documentado en el informe.

---

## 5. Interbloqueo (requisito 9)

### 5.1 Escenario deliberado

Dos procesos hijos necesitan **dos recursos** (locks) y los adquieren **en orden inverso**:

```python
# reportes.py         → adquiere A luego B
with lock_registro:            # A
    time.sleep(0.5)            # amplía la ventana
    with lock_metricas:        # B
        generar_resumen()

# administrativas.py  → adquiere B luego A
with lock_metricas:            # B
    time.sleep(0.5)
    with lock_registro:        # A
        depurar()
```

Con una intercalación desafortunada (garantizada con los `sleep`), **ninguno avanza**: cada proceso retiene un recurso y espera el otro. Evidencia del OS: ambos PIDs **vivos**, hilos en estado de espera (`ps -eLf`, `/proc/<pid>/status`), consumo de CPU ≈ 0.

### 5.2 Estrategias de corrección (a elegir y justificar)

1. **Ordenamiento uniforme** (recomendado, simple y clásico): todos los procesos adquieren los locks **en el mismo orden** (`lock_registro` → `lock_metricas`). Elimina la condición de espera circular.
2. **Timeouts / try-lock:** `lock.acquire(timeout=...)`; si falla, liberar lo adquirido y reintentar (previene espera indefinida).
3. Opcional para el informe: mostrar **las 4 condiciones de Coffman** presentes en el escenario buggy y cuál se rompe con la corrección.

El flag `DEMO_INTERBLOQUEO=True` alterna entre el orden invertido (buggy) y el orden uniforme (fix).

> **Pregunta abierta para validación:** ¿se prefiere demostrar el interbloqueo **entre procesos** (más fiel al problema, requiere pasar los dos `multiprocessing.Lock` a ambos hijos) o **entre hilos de un proceso** (más simple de hacer determinista)? Se propone **entre procesos**, reforzando la evidencia con `pstree`.

---

## 6. CPU, memoria y monitoreo (requisitos 5, 6 y 11)

| Fenómeno | Cómo se simula | Cómo se observa (evidencia) |
|---|---|---|
| **CPU elevada** | Tareas CPU-intensivas configurables (checksum SHA-256 sobre bloques, multiplicación de matrices) en `procesamiento`; intensidad ajustable por parámetro | `top`/`htop`, `ps -eo pid,pcpu,comm`, `/proc/<pid>/stat` muestreado por `monitoreo` |
| **Crecimiento de memoria (controlado)** | Los workers generan y conservan resultados de tamaño creciente en el registro; `administrativas` depura periódicamente (límite configurable) | `ps -eo pid,rss`, `VmRSS` en `/proc/<pid>/status`; gráfica de tendencia a partir de `metricas` (p. ej. con `matplotlib` o tabla CSV) |
| **Hilos por proceso** | Nº configurable de workers/escritores | `ps -eLf` (columna NLWP), `/proc/<pid>/task/` |
| **Jerarquía** | Padre → 5 hijos | `pstree -p`, `ps -eo pid,ppid,comm` |

`monitoreo` publica muestras periódicas en `metricas` y las deja listas para el informe (**comparación antes/después** en tabla y gráfica).

---

## 7. Registro de eventos (requisito 10)

Formato de cada evento compartido:

```
[2026-09-24 10:00:01.123] [admin]          inicio del servidor (PID=1234)
[2026-09-24 10:00:02.010] [procesamiento]  tarea-42 recibida
[2026-09-24 10:00:02.100] [almacenamiento] tarea-42 registrada (contador=15)
[2026-09-24 10:00:05.000] [monitoreo]      cpu=87% rss=145MB hilos=12
[2026-09-24 10:00:06.700] [admin]          DETECTADO: condición de carrera (contador=14, esperado=16)
```

Sirve tanto para el requisito 10 como para **correlacionar síntomas → causa → corrección** (requisito 12) en el informe.

---

## 8. Estructura del repositorio y herramienta de observación

```
OperativosProyecto/
├── propuesta-proyecto5.md            # este documento
├── README.md                         # instrucciones de ejecución (entregable)
├── requirements.txt                  # Python ≥ 3.10 (sin dependencias externas obligatorias)
├── servidor/
│   ├── main.py                       # proceso administrador (entrypoint)
│   ├── shared/
│   │   ├── estado.py                 # Manager + locks + estructuras compartidas
│   │   ├── registro.py               # operaciones RMW del registro (buggy/fix)
│   │   └── eventos.py                # log compartido
│   ├── componentes/
│   │   ├── procesamiento.py          # workers + cola productor-consumidor + CPU
│   │   ├── almacenamiento.py         # hilos escritores del registro
│   │   ├── reportes.py               # resúmenes + participación en interbloqueo
│   │   ├── monitoreo.py              # muestreo /proc, ps; publica metricas
│   │   └── administrativas.py        # depuración, eventos, contraparte deadlock
│   └── demos/
│       ├── escenario_carrera.py      # ejecuta buggy vs fix y compara
│       └── escenario_interbloqueo.py # ejecuta buggy vs fix y compara
├── herramientas/
│   └── observar.sh                   # captura de ps/pstree/top//proc para evidencias
├── tests/
│   ├── test_registro.py              # invariantes del registro (unit, determinista)
│   ├── test_carrera.py               # buggy < N vs fix == N
│   └── test_interbloqueo.py          # buggy se cuelga (join timeout) vs fix termina
└── docs/evidencias/
    ├── carrera/                      # 8 pasos de la §9.3 — condición de carrera
    │   ├── 01_version_inicial_buggy.txt
    │   ├── 02_ejecucion_controlada.txt
    │   ├── 03_evidencia_comportamiento.png
    │   ├── 04_explicacion_causa.md
    │   ├── 05_modificacion_implementada.patch
    │   ├── 06_nueva_ejecucion.txt
    │   ├── 07_evidencia_correccion.png
    │   └── 08_comparacion_antes_despues.md
    ├── interbloqueo/                 # mismo esquema 01–08 (reportes↔administrativas)
    │   ├── 01_version_inicial_buggy.txt
    │   ├── 02_ejecucion_controlada.txt
    │   ├── 03_evidencia_comportamiento.png
    │   ├── 04_explicacion_causa.md
    │   ├── 05_modificacion_implementada.patch
    │   ├── 06_nueva_ejecucion.txt
    │   ├── 07_evidencia_correccion.png
    │   └── 08_comparacion_antes_despues.md
    └── cpu-memoria/                  # simulación + medición + comparación
        ├── 01_configuracion_carga.txt
        ├── 02_ejecucion_controlada.txt
        ├── 03_evidencia_cpu_memoria.png
        └── 04_comparacion_cpu_memoria.png
```

### 8.1 Convención de evidencias — trazabilidad 1:1 con §9.3 de la guía

La guía (sección 9.3, "Prueba de fallo y corrección") pide **8 pasos concretos**:

| Paso §9.3 | Artefacto | Archivo |
|---|---|---|
| 1. Versión inicial o escenario con el problema | Código/flag que reproduce el problema (`DEMO_RAZA=True`, `DEMO_INTERBLOQUEO=True`) | `01_version_inicial_buggy.txt` |
| 2. Ejecución controlada | Comando exacto + parámetros (N de tareas, intensidad) + salida | `02_ejecucion_controlada.txt` |
| 3. Evidencia del comportamiento | Captura del síntoma (contador ≠ N, procesos vivos, `ps`/`top`/`/proc`) | `03_evidencia_comportamiento.png` |
| 4. Explicación de la causa | Análisis técnico del fenómeno (RMW sin exclusión mutua, espera circular) | `04_explicacion_causa.md` |
| 5. Modificación implementada | Diff/parche de la corrección | `05_modificacion_implementada.patch` |
| 6. Nueva ejecución | La **misma** ejecución controlada del paso 2, con la corrección aplicada | `06_nueva_ejecucion.txt` |
| 7. Evidencia de la corrección | Captura del resultado correcto (contador == N, ambos procesos terminan) | `07_evidencia_correccion.png` |
| 8. Comparación antes/después | Tabla y/o gráficas comparativas | `08_comparacion_antes_despues.md` |

`escenario_carrera.py` y `escenario_interbloqueo.py` **exportan automáticamente** estos artefactos a sus carpetas (escrituras, capturas y diffs), de modo que cada carpeta quede trazable paso a paso con lo que pide el profesor. El patrón `NN_nombre` también ordena cronológicamente las evidencias para el informe y la sustentación.

---

## 9. Estrategia de pruebas (TDD)

| Nivel | Qué se prueba | Tecnica |
|---|---|---|
| **Unitarias (deterministas)** | Funciones puras: checksum/resultado esperado, generación de resúmenes, invariantes del registro (tipos, contadores) | `pytest` sin concurrencia |
| **Escenario — condición de carrera** | Con `DEMO_RAZA=True`: `contador < N` (reproducible). Con fix: `contador == N` | Ejecución controlada con N fijo, múltiples intentos |
| **Escenario — interbloqueo** | Buggy: el proceso no termina en T segundos (`join(timeout)` da timeout). Fix: termina y genera resumen | Timeouts + verificación de salida |
| **Observación del SO** | Presencia/ausencia de procesos e hilos según ejecución | Script `observar.sh` + lectura de `/proc` |

> Nota metodológica: el ciclo red–green–refactor se aplica sobre el código; los "tests" de concurrencia son escenarios no deterministas en la versión buggy (se documenta la probabilidad/condición de reproducción, como pide la guía: "prueba reproducible").

---

## 10. Mapeo a criterios de evaluación

| Criterio | % | Cómo lo cubre esta propuesta |
|---|---|---|
| Diseño de la solución | 10% | Arquitectura documento (§3) + justificación de procesos/hilos |
| Implementación | 20% | Todos los componentes funcionando y requisitos 1–12 cumplidos |
| Concurrencia y sincronización | 20% | Condición de carrera buggy→fix con comparación (§4) |
| Interbloqueos | 15% | Escenario deliberado, condiciones de Coffman, corrección (§5) |
| Procesos, hilos y recursos | 10% | Jerarquía PID/PPID, hilos, recurso compartido (§3) |
| CPU y memoria | 10% | Simulación, medición y análisis (§6) |
| Evidencias | 10% | `ps`, `pstree`, `top`, `/proc` + antes/después (§6, §7) |
| Sustentación | 5% | Relación síntoma→causa→corrección en todo el documento |

---

## 11. Entregables previstos

1. Código fuente completo y organizado (§8).
2. README con instrucciones de ejecución.
3. Diagrama de arquitectura y de procesos (texto → luego diagrama draw.io/Mermaid para el informe).
4. Documento técnico (basado en esta propuesta + mediciones reales).
5. Evidencias de pruebas y del problema antes de la corrección — carpetas `carrera/` e `interbloqueo/`, pasos 01–04 de la tabla §8.1.
6. Evidencia de la solución después de la corrección — mismos pasos 05–07 de la tabla §8.1.
7. Comparación antes/después (tablas + gráficas de CPU/memoria) — paso 08 + carpeta `cpu-memoria/`.
8. Conclusiones técnicas.
9. Demostración funcional.

---

## 12. Preguntas abiertas (a validar con otra IA)

1. **Carga de CPU y GIL:** ¿conviene que la carga CPU-intensiva se reparta entre procesos (paralelismo real) o basta con hilos (limitados por GIL)? Recomendación propuesta: repartir entre procesos y documentar el GIL.
2. **Demo del interbloqueo:** ¿entre procesos compartiendo dos `multiprocessing.Lock` (recomendado, evidencia con `pstree`) o entre hilos del mismo proceso (más determinista)?
3. **Mecanismo de sincronización principal:** ¿`multiprocessing.Lock` (simple, idóneo) o se espera ver también semáforos/canales (`Manager` + `Condition`/`Semaphore`)?
4. **Productor–consumidor:** ¿cola implementada con `multiprocessing.Queue` (recomendado) o conviene una cola propia con `Semaphore`/`Lock` para *script* la sincronización a mano (más educativo)?
5. **Reutilización de la infraestructura en otros proyectos (1–4, 6–7):** la arquitectura es lo bastante genérica como para adaptar el mismo esqueleto a otros proyectos; ¿conviene aterrizarla ya con ese fin en mente (interfaces plugin) o mantener solo el mínimo para el Proyecto 5 (YAGNI)? Recomendación: mínimo para el Proyecto 5.

---

*Documento generado con la skill `brainstorming` (enfoque arquitectónico). Pendiente: validación externa, ajuste de los puntos abiertos, spec final y plan de implementación con `writing-plans`.*