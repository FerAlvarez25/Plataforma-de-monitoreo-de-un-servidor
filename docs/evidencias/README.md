# Evidencias — convención de nombres (trazabilidad §9.3 de la guía)

Cada fenómeno tiene su carpeta y sigue los **8 pasos** de la sección 9.3
("Prueba de fallo y corrección") con prefijos secuenciales:

| Paso | Archivo | Contenido |
|---|---|---|
| 1. Versión inicial / escenario con el problema | `01_version_inicial_buggy.txt` | Código/flag que reproduce el problema |
| 2. Ejecución controlada | `02_ejecucion_controlada.txt` | Comando exacto + parámetros + salida |
| 3. Evidencia del comportamiento | `03_evidencia_comportamiento.png` | Captura del síntoma (salida, `ps`, `top`, `/proc`) |
| 4. Explicación de la causa | `04_explicacion_causa.md` | Análisis técnico del fenómeno |
| 5. Modificación implementada | `05_modificacion_implementada.patch` | Diff de la corrección |
| 6. Nueva ejecución | `06_nueva_ejecucion.txt` | Misma ejecución controlada, con la corrección |
| 7. Evidencia de la corrección | `07_evidencia_correccion.png` | Captura del resultado correcto |
| 8. Comparación antes/después | `08_comparacion_antes_despues.md` | Tabla/gráficas comparativas |

## Carpetas

- `carrera/` — condición de carrera (registro compartido): buggy → fix con exclusión mutua.
- `interbloqueo/` — espera circular (reportes ↔ administrativas): buggy → fix (orden uniforme / timeouts).
- `cpu-memoria/` — simulación, medición y comparación de carga de CPU y memoria.