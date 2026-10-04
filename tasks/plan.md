# Implementation Plan: microservicio de extracción de texto de PDF (Go puro, sin cgo)

## Overview

Servicio HTTP que recibe un PDF crudo o por `multipart/form-data` y devuelve su texto
como Markdown en JSON (`{"content": ..., "page_count": N}`). Todo el procesamiento es
en memoria: Go estándar únicamente, sin cgo, sin librerías de PDF de terceros, sin
escrituras a disco y sin subprocess. Se despliega como 5 réplicas detrás del Traefik
existente (`mired`), 1 CPU y 512 MB cada una.

El servicio NO es el objeto de la carrera: el extractor de PDF lo es. La diferencia
entre 25,35 req/s y 16,65 req/s está dentro del PDF parser, no en la capa HTTP.

## Estado del repo al momento de planificar

Verificado con inspección:

| Hallazgo | Implicación |
|---|---|
| El repo tiene sólo `README.md` (vacío), `LICENSE`, `.gitignore` | Todo el código, el compose y los scripts son nuevos |
| **No hay ningún PDF en el repo ni en el padre** | Resuelto en el Paso 0 con un **fixture sintético** de perfil equivalente. Sigue abierta la carga del PDF real de la cátedra |
| `pdftotext` **sí** está instalado (`/usr/bin/pdftotext`, versión 24.02.0) | El oráculo del gate de corrección está disponible |
| `go1.26.8`, `docker 29.8.2`, `strace` presentes | Cumple los requisitos de los pasos 1, 5, 10 |
| **`k6` y `vegeta` NO están instalados** | Hay que instalarlos en el Bloque C (registrar versiones) |
| **No hay stack Traefik en este repo** | El paso 10 se adhiere a una red externa; el nombre de la red es una pregunta abierta |
| No hay harness de test en el repo | El Paso 0 lo crea con `unittest` de la stdlib: cero dependencias, `python3 -m unittest discover -s tools -t . -p '*_test.py'` |

Por eso el plan agrega un **Paso 0** de prerrequisitos antes del Paso 1 del enunciado.
Los 13 pasos originales conservan su numeración.

## Presupuesto de CPU: por qué 25,35 req/s es el número, no 45

Con 5 réplicas × 1,0 CPU el servicio tiene **5 CPUs en total**. El throughput
asintótico es `5 / S_cpu`:

| S_cpu por request | Throughput techo | ¿Alcanzable? |
|---|---|---|
| 1.450 ms (implementación previa) | 3,4 req/s | — (18× peor que Rust) |
| 350 ms | 14,3 req/s | ⛔ bajo el objetivo |
| 197 ms | **25,4 req/s** | ← **objetivo de la cátedra** |
| 125 ms | 40 req/s | requiere ~4,3 CPUs adicionales |
| 94 ms | 53,2 req/s | **techo absoluto**: el inflate y nada más |

El techo físico son los **~25 MB descomprimidos** del PDF a ~266 MB/s ≈ **94 ms**. O
sea: incluso con un extractor infinitamente barato en todo lo demás, 45 req/s es
imposible con 5 CPUs. A 197 ms de CPU el presupuesto queda así:

| Componente | Presupuesto |
|---|---|
| Inflate (piso físico) | 94 ms — no negociable sin `klauspost/compress` |
| Lexer + `xref` + page tree | ~20 ms |
| Tokenizado de content stream | ~30 ms |
| CMaps / `ToUnicode` | ~25 ms |
| Ensamblado de texto + HTTP + JSON | ~28 ms |
| **Total** | **197 ms** |

Si el perfil muestra que el inflate se lleva más de 94 ms, se evalúa
`github.com/klauspost/compress/flate` (única dependencia externa candidata, y sólo para
inflate). Nada más se agrega.

**Punto de decisión del Paso 6:** el número se mide, no se estima. Si queda lejos de
197 ms se para y se perfila con `-cpuprofile`. No se adivina dónde está el costo.

## Grafo de dependencias

```
                  Paso 0  fixture + oráculo pdftotext + gate.sh
                            (todo lo demás depende del gate)
                                   │
        ┌──────────────────────────┼───────────────────────────┐
        │                          │                           │
   Paso 1  andamiaje         Paso 2  objetos PDF          (medición: T0/T1)
  go.mod · /health          lexer · xref · trailer             │
   · config · Dockerfile    · Root · page tree                   │
        │                          │                           │
        │                     Paso 3  tokenizador  ◄── stopping point técnico
        │                     inflate · operandos · ops       │
        │                          │  (decide el proyecto)     │
        │                     Paso 4  fuentes + CMaps          │
        │                          │  (cache por obj ref)      │
        │                     Paso 5  ensamblado de texto       │
        │                          │  page_count · ctx · techo │
        │                     Paso 6  GATE DE PERFORMANCE ◄── stopping point
        │                          │  GOMAXPROCS=1 · cpuprofile │
        │                     Paso 7  markdown                 │
        │                          │  jerarquía por font size   │
        │                     Paso 8  contrato HTTP            │
        │                          │  raw · multipart · 413    │
        │                          │  415 · problem+json        │
        │                     Paso 9  admission control        │
        │                          │  semáforo ANTES del body   │
        │                     Paso 10 compose · Traefik        │
        │                     Paso 11 k6                       │
        │                     Paso 12 vegeta                   │
        └──────────────────────► Paso 13 reporte + varianza ◄──┘
```

El orden es bottom-up por dependencia dura (Go no compila sin `go.mod`; no hay texto
sin tokenizador; no hay tokenizador sin inflate; no hay medición sin compose).

## Architecture Decisions

1. **Tokens por valor, nunca `*T` al heap.** En la implementación anterior
   `return &n` fue el **31 % de las asignaciones**. `type token struct{ ... }` con
   métodos por valor.
2. **Tipo de token decidido por el byte inicial**, nunca por excepción + reintento.
   En la implementación anterior, construir un `fmt.Errorf` para detectar "esto no es
   un valor" consumió el **29 % del CPU**. Un `switch tok[0]` con un `default` que
   devuelve `tokOperador` es O(1) y no aloca.
3. **Enteros parseados a mano** (`for i < len(s) { ... }`), sin `string()` ni
   `strconv.ParseFloat`. Los números de un content stream son casi todos enteros
   chicos y la conversión float→string aloca.
4. **`numberOrRef` decide en una sola pasada.** No parsea, no rebobina, no re-parsea:
   una pasada que acumula el valor y detecta si vino `n g R` al final.
5. **Los XObject de imagen se saltan.** El PDF de referencia tiene 5.563 imágenes en
   5,2 MB pero sólo 709.803 chars de texto. Ninguna librería generalista lo hace; es la
   razón de que este extractor sea artesanal. Al encontrar `/Subtype /Image` se avanza
   el `stream` sin decodificarlo.
6. **Lectura por offset, nunca `os.ReadFile` del PDF entero.** El `xref` da las
   posiciones; cada objeto se abre por seek+read. Esto sostiene el techo de 512 MB con
   varios requests en vuelo.
7. **El semáforo de admission se toma antes de leer un byte del body.** Con 100 VUs ×
   5,2 MB son 520 MB de cuerpos: encolar sin límite OOMea el contenedor antes de
   extraer nada. Sobre capacidad → `503` inmediato.
8. **`net/http` de la stdlib, no `fasthttp`.** Medido: 19 % más rápido y 5,2× menos
   alocaciones que `fasthttp`, y además `fasthttp` nunca observa la desconexión del
   cliente (los timeouts de Vegeta del 33,40 % son exactamente esa clase de bug).
9. **`GOMAXPROCS=1` pineado en el compose.** Dentro de un contenedor con
   `cpus: '1.0'` el runtime reporta 6; seis Ps compitiendo por un core hace thrash y
   destruye el p95.
10. **Techo de tamaño descomprimido con error explícito.** Si un stream declara
   descomprimido mayor al tope, se devuelve error. Nunca OOM.
11. **Errores en `application/problem+json` (RFC 9457)** con `type`, `title`, `status`,
    `detail`, `instance`, `code`. El `code` es estable y legible por máquina; el
    `detail` es para humanos.
12. **Markdown derivado del tamaño relativo de fuente**, no de estilos: el PDF no los
    tiene. Los headings salen comparando el tamaño actual contra la mediana de la
    página; los párrafos, de la separación vertical y la sangría. **Sin detección de
    columnas** (no está en el alcance y no es needed para el objetivo).

## Task List

Tasks detalladas (descripción, criterios de aceptación, verificación, dependencias,
archivos, tamaño) en **`tasks/todo.md`**. Checklist de avance y checkpoints abajo.

### Fase 0 — Prerrequisitos

- [x] Paso 0: fixture de referencia + oráculo `pdftotext` + `scripts/gate.sh`

### Checkpoint: Prerrequisitos

- [x] `scripts/gate.sh` corre sobre el fixture y devuelve un porcentaje
- [x] El gate es ejecutable por el mismo comando en los 13 pasos siguientes

**Decisión del Paso 0 — el fixture es sintético, y es lo correcto por ahora.** El PDF de
la cátedra no está disponible, así que `tools/fixture/` lo genera byte a byte con las
características que definen el presupuesto de CPU. Medido contra el perfil:

| Característica | Cátedra | Fixture medido | Desvío |
|---|---|---|---|
| Páginas | 250 | 250 | 0 |
| Bytes en disco | 5.229.573 | 2.462.322 | −53 % |
| Caracteres de texto | 709.803 | 709.203 | −0,08 % |
| Imágenes dibujadas | 5.563 | 5.563 | 0 |
| Streams Flate | 1.417 | 1.417 | 0 |
| Descomprimido | ~25 MB | 26.827.465 B | +7,3 % |
| XObjects de imagen distintos | — | 1.166 | reutilizados entre páginas |

El descomprimido es el número que fija el piso del inflate, así que el presupuesto de
CPU del paso 6 es medible con este fixture. El tamaño en disco es 53 % menor: afecta el
costo de `read`, no el del inflate.

Dos propiedades del fixture que hacen que el gate tenga poder, descubiertas midiendo:

1. **El vocabulario tiene ~49.000 palabras distintas**, no 120. Con 120 palabras, truncar
   el 50 % del texto seguía dando 100 % de coincidencia: el gate saturaba y no gatesaba
   nada.
2. **La coincidencia es por multiset, no por conjunto.** Comparar conjuntos de palabras
   satura en cualquier documento largo (una palabra repetida 3 veces sólo cuenta una).
   El multiset hace que el gate sea lineal en el volumen extraído, medido: texto al 100 %
   → 100,00 %, al 90 % → 90,00 %, al 80 % → 80,00 %, al 60 % → 60,00 % (rechaza).

Verificación de que el fixture no pierde nada: la verdad de referencia
(`expected_text()`) contra `pdftotext` da **1,0000**.

### Fase 1 — Bloque A: el extractor

- [x] Paso 1: andamiaje (`go.mod`, `CGO_ENABLED=0`, `/health`, config por env, Dockerfile multi-etapa no-root)
- [ ] Paso 2: capa de objetos PDF (lexer → `xref` → `trailer` → `Root` → page tree)
- [ ] Paso 3: tokenizador del content stream — **stopping point técnico**
- [ ] Paso 4: fuentes y CMaps (`ToUnicode`, cache por referencia de objeto)
- [ ] Paso 5: ensamblado de texto (`Tj`/`TJ`/`'`/`"`, `page_count`, `ctx`, techo)
- [ ] Paso 6: gate de performance — **stopping point del proyecto**

### Checkpoint A: Extractor

- [ ] Gate ≥ 70 % de coincidencia de palabras contra `pdftotext`
- [ ] `page_count == 250`
- [ ] `strace` sin escrituras a disco
- [ ] Benchmark con `GOMAXPROCS=1` medido y anotado en el log de medición
- [ ] `go build ./...`, `go vet ./...`, `go test ./...` limpios

### Fase 2 — Bloque B: el servicio

- [ ] Paso 7: Markdown (headings por mediana de tamaño de fuente, párrafos por separación/sangría)
- [ ] Paso 8: contrato HTTP (raw + multipart, `413`, `415`, `problem+json`, abort)
- [ ] Paso 9: admission control y worker pool (semáforo antes del body, `503`, token liberado en todos los caminos)
- [ ] Paso 10: `docker-compose` (5 réplicas, 1 CPU, 512 MB, `GOMAXPROCS=1`, labels Traefik)

### Checkpoint B: Servicio

- [ ] Tests de crudo, multipart, tipo incorrecto, sobredimensionado y abort en verde
- [ ] `go test -race ./...` limpio
- [ ] Con `maxInFlight=1` y 10 requests concurrentes, el 9º+ se rechaza en < 10 ms y el RSS queda bajo el techo
- [ ] `docker compose ps` muestra 5 réplicas; `docker inspect` confirma `NanoCpus=1000000000` y `Memory=536870912`

### Fase 3 — Bloque C: la medición

- [ ] Paso 11: k6 (ramp 10 s → 100 VUs, hold 20 s, down 10 s; p50/p95/p99, request rate, error rate)
- [ ] Paso 12: Vegeta (`-rate 50 -duration 30s -timeout 30s`; success rate, throughput, p50/p95/p99, no-2xx, timeouts)
- [ ] Paso 13: comparación y reporte (tabla contra los 4 números de la cátedra, 3 corridas con varianza, teardown limpio)

### Checkpoint C: Entrega

- [ ] Las 4 métricas de la cátedra están en `README.md` con los comandos exactos de reproducción
- [ ] El reporte dice **plainly** qué se cumplió y qué no
- [ ] `docker compose down -v` + reconstrucción desde cero + 3 corridas repetidas

## Log de medición

Se completa en cada paso. Todo delta va acá antes del commit (regla de trabajo 3).

| Paso | Métrica | Antes | Después | Delta | Gate ≥ 70 % |
|---|---|---|---|---|---|
| 0 | fixture: páginas · streams Flate · descomprimido | — | 250 · 1.417 · 26,8 MB | — | **100,00 %** (pdftotext vs verdad de referencia) |
| 0 | sensibilidad del gate | — | lineal: 90 %→90,00 · 80 %→80,00 · 60 %→60,00 | — | — |
| 1 | `/health` latencia (binario real, 10 llamadas) | — | **0,32–0,96 ms** | — | n/a |
| 1 | RSS del contenedor | — | **1,5 MiB** (tope 512 MB) | — | n/a |
| 1 | imagen final | — | **13,3 MB** · `nonroot` · **0** archivos `.go` | — | n/a |
| 2 | `BenchmarkExtract` ms/op · allocs/op | — | — | — | — |
| 3 | `BenchmarkExtract` ms/op · allocs/op | — | — | — | — |
| 4 | palabras coincidentes % | — | — | — | — |
| 5 | ms/op · allocs/op · RSS | — | — | — | — |
| 6 | **ms/op con `GOMAXPROCS=1`** | 1.450 (impl. previa) | — | — | — |
| 9 | RSS con 100 VUs | — | — | — | — |
| 11 | k6 p50 / p95 / req/s / % err | — | — | — | — |
| 12 | vegeta success / p50 / % timeouts | — | — | — | — |

Referencias contra las que comparar (cátedra / implementación previa):

| Escenario | req/s | p50 | p95 | Errores |
|---|---|---|---|---|
| k6 (cátedra) | 25,35 | 1,88 s | 8,80 s | 0,00 % |
| k6 (impl. previa) | 16,65 | 14,89 s | — | 33,40 % timeouts |
| Vegeta (impl. previa) | 16,65 | 14,89 s | — | 66,53 % éxito |

## Risks and Mitigations

| Riesgo | Impacto | Mitigación |
|---|---|---|
| S_cpu queda > 197 ms → no se llega a 25,35 req/s | **High** | El paso 6 es stopping point: `-cpuprofile` antes de optimizar a ciegas. Los sospechosos ya están identificados: tipo de token por excepción (29 % CPU), `&n` (31 % alloc), doble parse de `numberOrRef`, decode de XObjects de imagen |
| Regresión silenciosa del gate de 70 % debajo de una micro-optimización | **High** | `scripts/gate.sh` en el mismo comando de verificación de los 13 pasos; el número de gate va en el log de medición de cada commit |
| OOM del contenedor de 512 MB con 100 VUs × 5,2 MB | **High** | Semáforo tomado antes de leer el body (paso 9) + `MaxBytesReader` → 413 (paso 8) + RSS verificado con 100 VUs |
| El PDF de referencia no está en el repo | **High** | Paso 0 lo resuelve antes de que cualquier paso dependa del gate. Pregunta abierta: ¿se versiona el binario o se descarga? |
| Thrash por `GOMAXPROCS` reportando 6 dentro de `cpus: '1.0'` | **Med** | `GOMAXPROCS=1` pineado en el environment del compose (paso 10) |
| `fasthttp` u otra librería HTTP reintroducidas | **Med** | La decisión está escrita arriba con los números que la justifican; `net/http` es la stdlib |
| Stream declarado de tamaño enorme → OOM | **Med** | Techo de tamaño descomprimido con error explícito (paso 5) |
| Deriva del gate por versión distinta de `pdftotext` | **Med** | Fijar la versión en el `README` y regenerar el golden sólo a propósito |
| El stack Traefik `mired` no está en este repo | **Med** | El compose se adhiere por `networks.external` + labels; **pregunta abierta**: nombre exacto de red y regla de labels |
| `klauspost/compress` se mete "para optimizar" sin medir | **Low** | Sólo se evalúa en el paso 6, y sólo para inflate, replacing `compress/flate`. Registrado como pregunta abierta |
| Detección de columnas se cuela en el markdown | **Low** | Fuera de alcance explícito; el criterio del paso 7 no la menciona |
| El body del benchmark se recalcula y mete ruido | **Low** | `b.ReportAllocs()`, `b.ResetTimer()` fuera del setup, y el PDF cargado una vez |
| Timestamps de compose horneados | **Low** | Reproducibilidad: `docker compose down -v` + build limpio en el paso 13 |

## Open Questions

1. ~~¿De dónde sale el PDF de referencia?~~ **Resuelto en el Paso 0 con fixture sintético.**
   Queda pendiente si más adelante se carga el PDF real de la cátedra: si aparece, hay que
   regenerar el golden y volver a correr el gate. Hasta entonces, el número de CPU del
   paso 6 se midió contra un PDF de 26,8 MB descomprimidos, no contra el original.
2. **¿Cuál es el nombre exacto de la red externa de Traefik (`mired`) y qué regla de
   labels usa el stack?** Hace falta para el `networks.external` y el `Host` header del
   compose del paso 10.
3. **¿Se permite `github.com/klauspost/compress` como dependencia?** El enunciado dice
   "Go puro, sin librerías de PDF de terceros". Mi lectura: `klauspost/compress` no es
   una librería de PDF, así que entraría en el paso 6 si el perfil lo justifica. ¿Se
   acepta o el proyecto exige stdlib estricto?
4. **~~¿Límite de tamaño de body para el 413?~~ Fijado en 16 MiB** (`MAX_BODY_BYTES`)
   en el paso 1: el fixture pesa 2,5 MB y el PDF de la cátedra 5,2 MB. Sigue siendo un
   default: se cambia por env sin recompilar.
5. **~~¿`maxInFlight` por réplica?~~ Fijado en `1`** (`MAX_INFLIGHT`): con 1 CPU por
   réplica, más de 1 request en vuelo sólo agrega latencia de cola y presión de memoria
   (5 réplicas ⇒ 5 en vuelo en total).
6. **Parcialmente resuelto en el paso 1:** `WRITE_TIMEOUT=35s` es **mayor** que el
   `-timeout 30s` de Vegeta, que era la preocupación real — así un timeout del cliente
   nunca se cuenta como fallo del servidor. `READ_TIMEOUT=30s` sigue provisional hasta
   que Vegeta esté instalado y el paso 12 lo pueda medir.
7. **~~¿Versión de `pdftotext` de referencia?~~ Registrada: 24.02.0.** Si cambia, hay que
   regenerar `testdata/ref.txt`.

## Parallelization Opportunities

**Secuencial obligatorio (no paralelizar):** los pasos 1→2→3→4→5→6. Go no compila sin
`go.mod`; no hay `xref` sin lexer; no hay tokens sin inflate; no hay texto sin CMaps; no
hay medición sin gate. Los pasos 7, 8 y 9 dependen del mismo contrato de
`Extract(ctx, []byte) (text string, pages int, err error)`, que se congela al cerrar el
paso 5.

**Paralelizable una vez congelado el contrato del paso 5:**

| Trabajo | Tareas | Por qué es seguro |
|---|---|---|
| Tests del extractor contra el fixture | 7, 8, 9 | Sólo leen `Extract()`; no tocan el mismo archivo |
| `Dockerfile` final + `.dockerignore` | 10 | Toca sólo build |
| Scripts de medición k6 / Vegeta | 11, 12 | Leen el contrato HTTP, no la implementación |
| Sección de performance del `README` | 13 | Escritura, no código |

**Necesita coordinación:** el compose del paso 10 depende de la respuesta HTTP del paso
8 (path, puerto, healthcheck) y de `maxInFlight` del paso 9. Definir esos dos valores
antes de arrancar el 10 evita retrabajo.

## Reglas de trabajo (aplican a los 14 pasos)

1. **Un paso por vez.** No arrancar el paso N+1 hasta que el N esté verificado y
   commiteado.
2. **Un commit por paso**, formato `operacion(scope): descripcion.#(Nro)`.
3. **Medir antes y después** de cada paso de performance, y anotar el delta en el log
   de medición de arriba.
4. **Gate de corrección en todos los pasos**: el texto extraído debe coincidir con la
   salida de `pdftotext` en ≥ 70 % de las palabras. Ningún commit puede bajarlo.
5. **Si un paso no mejora la métrica que decía mejorar, revertirlo.**