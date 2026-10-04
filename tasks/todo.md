# TODO — microservicio de extracción de texto de PDF (Go puro)

Plan completo y decisiones en `tasks/plan.md`. Este archivo es la lista de tareas
ejecutable: un paso por vez, un commit por paso, gate de ≥ 70 % en todos.

## Cómo se ejecuta esta lista

- Un paso por vez. No arrancar el N+1 hasta que el N esté verificado y commiteado.
- Commit por paso, formato `operacion(scope): descripcion.#(Nro)`.
- Antes de commitear: correr la verificación del paso. Si el gate baja de 70 %, no se
  commitea: se arregla o se revierte.
- Si el paso no mejora la métrica que decía mejorar, se revierte (regla 5).
- Al terminar cada paso, completar la fila del log de medición en `tasks/plan.md`.

## Comandos de referencia

```bash
# build / análisis / tests
CGO_ENABLED=0 go build ./...
go vet ./...
go test ./...
go test -race ./...

# benchmark (GOMAXPROCS=1: replica una réplica, que tiene 1 CPU)
GOMAXPROCS=1 go test -bench=Extract -benchmem -benchtime=5x -run='^$' ./internal/pdf/...

# perfil (sólo cuando el número está fuera de objetivo)
GOMAXPROCS=1 go test -bench=Extract -benchtime=20x -run='^$' \
  -cpuprofile=/tmp/cpu.out -o /tmp/pdf.test ./internal/pdf/...
go tool pprof -top -nodecount=20 /tmp/pdf.test /tmp/cpu.out

# gate de corrección (el mismo en los 14 pasos)
./scripts/gate.sh                       # falla si la coincidencia < 70 %
./scripts/gate.sh otra-salida.txt       # compara un archivo contra el golden

# tests del harness de fixture y gate (Python, stdlib, cero dependencias)
python3 -m unittest discover -s tools -t . -p '*_test.py'

# regenerar el fixture y su golden (determinista)
./scripts/gen-fixture.sh
```

---

## Paso 0: fixture de referencia, oráculo y gate — HECHO

**Descripción:** Hoy el repo no tiene ningún PDF, así que la regla 4 ("gate de
corrección en todos los pasos") no es verificable y el paso 6 no tiene con qué medir.
Este paso trae el PDF de referencia, genera el texto del oráculo con `pdftotext` y
escribe el script que toda la proyecto va a correr en cada commit.

> **Decisión:** el PDF de la cátedra no está disponible, así que el fixture se **genera**
> byte a byte con `tools/fixture/`, con las características que definen el presupuesto de
> CPU (250 páginas · 5.563 imágenes · 1.417 streams Flate · 26,8 MB descomprimidos).
> Con el fixture sintético el gate es verificable desde el primer commit. Cuando aparezca
> el PDF real, hay que regenerar el golden y volver a medir el paso 6.

**Acceptance criteria:**
- [x] El PDF de referencia está en `testdata/ref.pdf` con 250 páginas y 2.462.322 B
- [x] `pdftotext -layout` produce `testdata/ref.txt` (778.614 B) con 709.203 caracteres
- [x] El perfil se cumple: 1.417 streams Flate, 5.563 dibujos de imagen, 26.827.465 B descomprimidos
- [x] `scripts/gate.sh` extrae con el binario actual, compara palabra por palabra contra
      el golden e imprime el porcentaje
- [x] El script sale con código distinto de 0 si la coincidencia < 70 % (verificado: 60 % → exit 1)
- [x] El gate es lineal en el volumen extraído: 100 %→100,00 · 90 %→90,00 · 80 %→80,00 · 60 %→60,00
- [x] La verdad de referencia contra `pdftotext` da 1,0000: el fixture no pierde nada
- [x] El script es idempotente y funciona con `set -euo pipefail`

**Verificación:**
- [x] Tests pass: `python3 -m unittest discover -s tools -t . -p '*_test.py'` → **88 tests, OK**
- [x] Build succeeds: `python3 -m compileall -q tools` sin errores (el harness es Python;
      `go build` todavía no existe, es del paso 1)
- [x] Manual check: `pdftotext -v` → **24.02.0**, anotada en el `README` porque el gate es
      sensible a la tokenización del oráculo

**Dependencies:** None

**Files likely touched** (más de los 3 estimados: el harness de test es la parte de TDD):
- `testdata/ref.pdf` (2,5 MB, generado, no editado a mano)
- `testdata/ref.txt` (golden de `pdftotext`)
- `scripts/gen-fixture.sh`, `scripts/gate.sh`
- `tools/fixture/objects.py`, `writer.py`, `cmap.py`, `page.py`, `text.py`, `document.py`, `cli.py`
- `tools/gate/wordmatch.py`
- `tools/fixture/*_test.py`, `tools/gate/wordmatch_test.py` (88 tests)
- `.gitignore` (`__pycache__/`, `bin/`)

**Estimated scope:** Medium: 7 archivos de código + 6 de test

**Commit:** `operacion(fixture): pdf de referencia, golden de pdftotext y gate de 70%.#(0)`

**Lo que se aprendió midiendo (no se adivinó):**
1. Con un vocabulario de 120 palabras, truncar el 50 % del texto seguía dando **100 %**
   de coincidencia: el gate no gateaba nada. El vocabulario pasó a ~49.000 palabras.
2. Comparar **conjuntos** de palabras satura en cualquier documento largo. El gate
   pasó a **multiset**, y quedó lineal en el volumen extraído.
3. Elkerning de un `TJ` tiene que partir **dentro** de una palabra, no en el espacio:
   si se parte en el espacio, `pdftotext` fusiona las dos palabras y se pierden.

---

## Paso 1: andamiaje

**Descripción:** `go.mod` con Go ≥ 1.22 y `CGO_ENABLED=0`, endpoint `GET /health`,
configuración por variables de entorno, y Dockerfile multi-etapa que corre como usuario
no-root. Es el cimiento del que cuelgan todos los pasos siguientes: Go no compila sin
esto.

**Acceptance criteria:**
- [ ] `go.mod` declara `go 1.22` (o superior) y el árbol compila con `CGO_ENABLED=0`
- [ ] `GET /health` devuelve `200` con un JSON mínimo y responde en < 5 ms
- [ ] Config por env: `PORT`, `MAX_BODY_BYTES`, `MAX_INFLIGHT`, `MAX_INFLATE_BYTES`,
      `READ_TIMEOUT`, `WRITE_TIMEOUT` — con defaults sensatos y sin variablesREQUIRED
- [ ] Dockerfile multi-etapa: build con toolchain, runtime sin toolchain, `USER`
      no-root, y la imagen final no contiene el código fuente
- [ ] `go vet ./...` limpio

**Verificación:**
- [ ] Tests pass: `go test ./...`
- [ ] Build succeeds: `CGO_ENABLED=0 go build ./... && go vet ./...`
- [ ] Manual check: `go run ./cmd/server &` + `curl -w '%{time_total}' localhost:PORT/health`
      < 5 ms; `docker build .` y `docker run` devuelven 200 desde el healthcheck

**Dependencies:** None (desbloquea todo lo demás)

**Files likely touched:**
- `go.mod`
- `cmd/server/main.go`
- `internal/config/config.go`
- `internal/httpapi/health.go`
- `Dockerfile`
- `.dockerignore`

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(andamiaje): go.mod, health, config por env y dockerfile no-root.#(1)`

---

## Paso 2: capa de objetos PDF

**Descripción:** Lector del archivo: lexador de bajo nivel → `xref` → `trailer` → `Root`
→ page tree. Cada objeto se lee por offset con seek+read, nunca cargando el archivo
entero: esto es lo que sostiene el techo de 512 MB con varios requests en vuelo.

**Acceptance criteria:**
- [ ] Se localiza la tabla `xref` (y la variante `/XRefStm` de PDF 1.5) y se construyen
      los offsets de todos los objetos
- [ ] `trailer` → `Root` → `Pages` → recorrido completo del page tree, heredando
      `Resources` y contando páginas
- [ ] Abrir el PDF de referencia devuelve exactamente **250** páginas
- [ ] Cada objeto se resuelve por offset: no hay `os.ReadFile` del PDF completo ni
      buffer del tamaño del archivo
- [ ] PDFs con `xref` dañado ⇒ warning y reconstrucción por scan, sin panic

**Verificación:**
- [ ] Tests pass: `go test ./...` — test que abre el fixture y encuentra 250 páginas
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: el test imprime `pages=250`; un PDF truncado devuelve error, no panic

**Dependencies:** Paso 1

**Files likely touched:**
- `internal/pdf/lexer.go`
- `internal/pdf/xref.go`
- `internal/pdf/object.go`
- `internal/pdf/page.go`
- `internal/pdf/pdf_test.go`

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(pdf): lexer, xref, trailer y page tree por offset.#(2)`

---

## Paso 3: tokenizador del content stream

**Descripción:** Inflate con `compress/flate` y escaneo de operadores y operandos. Este
es el paso que decide el proyecto: la implementación anterior perdió aquí el 29 % del
CPU y el 31 % de las asignaciones por dos errores de dos líneas. Los números de abajo
son la definición de "hecho" de este paso.

**Acceptance criteria:**
- [ ] El tipo de token se decide **por el byte inicial**, con un `default` que
      clasifica como operador. **Prohibido** construir un `fmt.Errorf` para detectar
      "esto no es un valor" y reintentar como operador
- [ ] Los tokens se devuelven **por valor** (`token`, nunca `*token` al heap). Prohibido
      `return &n`
- [ ] Los enteros se parsean a mano, sin `string()` y sin `strconv.ParseFloat`
- [ ] `numberOrRef` decide en **una sola pasada** (acumula el valor y detecta `n g R` al
      final). No parsea dos veces ni rebobina
- [ ] Los XObject de imagen se **saltan**: `/Subtype /Image` avanza el `stream` sin
      decodificarlo (5.563 imágenes, 709 KB de texto: no vale la pena)
- [ ] `BenchmarkTokenize` reporta **< 1 M allocs/op** en este paso
- [ ] Un test demuestra que los operadores se reconocen **sin** construir errores
      (assert sobre `allocs` o sobre un contador de errores, no sobre el texto)

**Verificación:**
- [ ] Tests pass: `go test ./...` y `go test -bench=Tokenize -benchmem ./internal/pdf/...`
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: `grep -rn "fmt.Errorf" internal/pdf/` no devuelve coincidencias
      dentro de la ruta de tokenización; `grep -rn "return &" internal/pdf/` sin resultados
      en el tokenizer

**Dependencies:** Paso 2

**Files likely touched:**
- `internal/pdf/content/lexer.go`
- `internal/pdf/content/token.go`
- `internal/pdf/content/number.go`
- `internal/pdf/content/inflate.go`
- `internal/pdf/content/lexer_test.go`

**Estimated scope:** Large: 5-8 files — **partir en tres sub-tareas si no entra en una
sesión**: (3a) lexer de bytes + clasificación por byte inicial; (3b) parser de números
enteros a mano + `numberOrRef` de una pasada; (3c) operador vs operando + salto de
XObjects de imagen

**Commit:** `operacion(tokenizador): tokenizacion por byte inicial sin errores ni heap.#(3)`

---

## Paso 4: fuentes y CMaps

**Descripción:** Page resources → fuentes → `ToUnicode` CMap, con cache por referencia de
objeto (el PDF reusa la misma fuente en cientos de páginas; parsear el CMap por
página sería el segundo error más caro después del tokenizador).

**Acceptance criteria:**
- [ ] Se resuelven `Resources → Font → {BaseFont, Encoding, ToUnicode}` heredando a
      través del page tree
- [ ] Los CMaps más comunes están soportados: `Identity-H`, y los rangos `beginbfrange`
      / `beginbfchar` / `begincidrange` / `begincidchar` de `ToUnicode`
- [ ] El cache está indexado por **referencia de objeto**, no por nombre de fuente
- [ ] La salida es UTF-8 correcto (acentos, eñes, ñ, símbolos) — verificable con el golden
- [ ] Gate ≥ 70 % de coincidencia de palabras

**Verificación:**
- [ ] Tests pass: `go test ./...` + `./scripts/gate.sh` (≥ 70 %)
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: comparar el texto extraído con `pdftotext` en una página con acentos
      y caracteres acentuados; completar el log de medición con el % de coincidencia

**Dependencies:** Paso 3

**Files likely touched:**
- `internal/pdf/font.go`
- `internal/pdf/cmap.go`
- `internal/pdf/cmapcache.go`
- `internal/pdf/font_test.go`

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(cmap): fuentes, ToUnicode y cache por referencia de objeto.#(4)`

---

## Paso 5: ensamblado de texto

**Descripción:** Ensamblar `Tj` / `TJ` / `'` / `"` respetando la posición en la línea, y
exponer el contrato que consumen el markdown (paso 7) y el HTTP (pasos 8-9):
`Extract(ctx, []byte) (content string, pageCount int, err error)`. Devuelve
`page_count`, aborta con `ctx.Done()` a mitad del documento y tiene techo de tamaño
descomprimido.

**Acceptance criteria:**
- [ ] `Tj`, `TJ`, `'` y `"` se ensamblan respetando la posición horizontal y el salto
      de línea explícito e implícito
- [ ] `Extract` devuelve `pageCount == 250` para el fixture
- [ ] `ctx.Done()` a mitad del documento devuelve error de cancelación y no estado
      corrupto (test con un contexto que cancela tras N páginas)
- [ ] Superar el techo de tamaño descomprimido devuelve error explícito. **Nunca OOM**
- [ ] Cero escrituras a disco y cero subprocess (test + `strace`)

**Verificación:**
- [ ] Tests pass: `go test ./...` (incluye test de cancelación) + `./scripts/gate.sh` (≥ 70 %)
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: `strace -f -e trace=openat,write,openat2 ./bin/server` durante una
      extracción ⇒ sin escrituras (sólo los logs a stdout)

**Dependencies:** Paso 4

**Files likely touched:**
- `internal/pdf/text.go`
- `internal/pdf/extract.go`
- `internal/pdf/limits.go`
- `internal/pdf/text_test.go`
- `internal/pdf/extract_test.go`

**Estimated scope:** Large: 5-8 files — **partir si no entra en una sesión**: (5a)
ensamblado de operadores de texto + positioning; (5b) `Extract` de punta a punta +
`page_count`; (5c) cancelación, techo de inflate y test de no-escritura

**Commit:** `operacion(texto): ensamblado de Tj/TJ, page_count, cancelacion y techo.#(5)`

---

## Checkpoint A: Extractor

- [ ] Gate ≥ 70 % de coincidencia de palabras contra `pdftotext`
- [ ] `page_count == 250`
- [ ] `strace` sin escrituras a disco
- [ ] `go build ./...`, `go vet ./...`, `go test ./...`, `go test -race ./...` limpios
- [ ] Sin sub-tareas pendientes de los pasos 3 y 5
- [ ] Revisión humana antes de seguir al Bloque B

---

## Paso 6: gate de performance ← stopping point

**Descripción:** La medición que decide si el resto del proyecto es viable. Corre el
benchmark con `GOMAXPROCS=1` (una réplica tiene 1 CPU) sobre el fixture y compara con la
referencia de Rust (~91 ms de CPU de extracción) y con la implementación previa (1.450
ms/op, 15,6 M allocs/op). El objetivo operativo es **≤ 197 ms/op**, que es lo que
produce los 25,35 req/s con 5 réplicas.

**Acceptance criteria:**
- [ ] `GOMAXPROCS=1 go test -bench=Extract -benchmem` da un número medido, anotado en
      el log de medición de `tasks/plan.md`
- [ ] El número está anotado **con** su desglose: total, y el costo del inflate aislado
- [ ] Si el total > 197 ms ⇒ existe un `-cpuprofile` con los 20 nodos más caros
      identificados y escritos en el log. **No se optimiza sin perfil**
- [ ] Comparación explícita contra 91 ms (Rust) y 1.450 ms (impl. previa)
- [ ] Sólo si el perfil muestra que el inflate domina: evaluar
      `github.com/klauspost/compress/flate` y medir el delta. Sin perfil, no se agrega
- [ ] El gate de 70 % sigue en verde después de cualquier cambio de performance

**Verificación:**
- [ ] Tests pass: `./scripts/gate.sh` (≥ 70 %)
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: el número está en `tasks/plan.md`; si falta closeness, hay cpuprofile

**Dependencies:** Paso 5

**Files likely touched:**
- `internal/pdf/bench_test.go`
- `tasks/plan.md` (log de medición)
- `README.md` (números de performance)

**Estimated scope:** Small: 1-2 files

**Commit:** `operacion(perf): gate de performance con GOMAXPROCS=1 y perfil si hace falta.#(6)`

**Nota:** si el número está lejos del objetivo, **parar y perfilar**. Los sospechosos ya
están identificados y son medibles: clasificación de token por excepción (29 % CPU),
`&n` en el return (31 % alloc), doble parse de `numberOrRef`, y decode de los 5.563
XObjects de imagen.

---

## Paso 7: Markdown

**Descripción:** `content` devuelve encabezados y párrafos. El PDF codifica la jerarquía
por **tamaño relativo de fuente**, no por estilos: los encabezados salen de comparar el
tamaño actual contra la mediana de los tamaños de la página, y los párrafos de la
separación vertical y la sangría. **Sin detección de columnas**: fuera de alcance.

**Acceptance criteria:**
- [ ] El markdown usa headings ATX bien formados (`#` a `######`), sin sintaxis rota
- [ ] La jerarquía sale de comparar el tamaño de fuente contra la mediana de la página
- [ ] Los párrafos se segmentan por separación vertical y sangría
- [ ] **No** hay detección de columnas
- [ ] Un test valida **sintaxis Markdown real** (parsear la salida y verificar la
      estructura del árbol de nodos), no que la salida "contenga" ciertas cadenas

**Verificación:**
- [ ] Tests pass: `go test ./...` + `./scripts/gate.sh` (≥ 70 %)
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: el markdown de las primeras 3 páginas del fixture se lee bien a ojo

**Dependencies:** Paso 5 (contrato `Extract` congelado)

**Files likely touched:**
- `internal/markdown/markdown.go`
- `internal/markdown/markdown_test.go`
- `internal/pdf/text.go` (exposición de tamaños de fuente y posiciones)

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(markdown): headings por mediana de fuente y parrafos por gap y sangria.#(7)`

---

## Paso 8: contrato HTTP

**Descripción:** `POST /extract` acepta PDF crudo (`application/pdf`) y
`multipart/form-data`, y responde `{"content": ..., "page_count": N}` con
`Content-Type: application/json`. Los errores van en `application/problem+json`
(RFC 9457) con `type`, `title`, `status`, `detail`, `instance`, `code`.

**Acceptance criteria:**
- [ ] PDF crudo (`application/pdf`) → 200 + `{"content": ..., "page_count": N}`
- [ ] `multipart/form-data` → 200 + el mismo shape de respuesta
- [ ] Body sobre el límite → **413** (no 400, no OOM)
- [ ] Media type incorrecto → **415**
- [ ] Errores de extracción → `application/problem+json` con los 6 campos, y `code`
      estable por tipo de error
- [ ] Cliente aborta a mitad del body → el handler deja de trabajar y libera recursos
      (esto es lo que `fasthttp` no hacía y costaba el 33 % de timeouts)

**Verificación:**
- [ ] Tests pass: `go test ./...` — tests de crudo, multipart, tipo incorrecto,
      sobredimensionado y abort, todos en verde
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: `curl -H 'Content-Type: application/pdf' --data-binary @testdata/ref.pdf
      localhost:PORT/extract | jq '.page_count'` → 250; y un `curl` con `text/plain`
      → 415 con `problem+json`

**Dependencies:** Paso 5

**Files likely touched:**
- `internal/httpapi/extract.go`
- `internal/httpapi/problem.go`
- `internal/httpapi/server.go`
- `internal/httpapi/extract_test.go`
- `internal/httpapi/problem_test.go`

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(http): endpoint extract con raw, multipart, 413, 415 y problem+json.#(8)`

**Nota:** definir aquí el límite de body (pregunta abierta 4: propongo 16 MB, 3× el
fixture) y el timeout del server (pregunta abierta 6).

---

## Paso 9: admission control y worker pool

**Descripción:** El semáforo se toma **antes de leer un byte del body**. Con 100 VUs ×
5,2 MB son 520 MB de cuerpos: eso OOMea un contenedor de 512 MB antes de extraer una
sola palabra. Sobre capacidad → `503` inmediato, nunca encolar sin límite. El token se
libera en todos los caminos, incluido panic y cancelación.

**Acceptance criteria:**
- [ ] El token de admission se toma **antes** de cualquier lectura del body
- [ ] Sobre capacidad → **503** inmediato (no encolado, no espera)
- [ ] El token se libera en todos los caminos: éxito, error, panic y cancelación
- [ ] Worker pool acotado: nunca más de `MAX_INFLIGHT` extracciones simultáneas
- [ ] `go test -race ./...` limpio
- [ ] Con `maxInFlight=1` y 10 requests concurrentes, el 9º y el 10º se rechazan en
      **< 10 ms** y el RSS queda bajo el techo de 512 MB

**Verificación:**
- [ ] Tests pass: `go test -race ./...` + test de concurrencia con 10 requests
- [ ] Build succeeds: `go build ./... && go vet ./...`
- [ ] Manual check: 10 `curl` concurrentes con el fixture ⇒ 1×200, 9×503, el 9º+ en
      < 10 ms; `docker stats` confirma el RSS bajo 512 MB

**Dependencies:** Paso 8

**Files likely touched:**
- `internal/extract/pool.go`
- `internal/extract/semaphore.go`
- `internal/httpapi/handler.go` (integración)
- `internal/extract/pool_test.go`

**Estimated scope:** Medium: 3-5 files

**Commit:** `operacion(pool): semaphore antes del body, 503 sin encolado y liberacion total.#(9)`

---

## Paso 10: docker-compose

**Descripción:** `deploy.replicas: 5`, `cpus: '1.0'`, `memory: 512M`, y
**`GOMAXPROCS` pineado a 1**: dentro de un contenedor con `cpus: '1.0'` el runtime
reporta 6, y seis Ps compitiendo por un core causa thrash. Se adhiere al stack Traefik
existente (`mired`) por `networks.external` + labels, con Host header. **El puerto 80 ya
está ocupado: no se levanta un Traefik propio.**

**Acceptance criteria:**
- [ ] `deploy.replicas: 5`, `cpus: '1.0'`, `memory: 512M`
- [ ] `GOMAXPROCS=1` en el `environment` del servicio
- [ ] Se adhiere a la red externa de Traefik por labels; **ningún** servicio Traefik
      propio en este compose
- [ ] Host header y rule del router correctos para el stack existente
- [ ] Healthcheck del contenedor configurado contra `/health`

**Verificación:**
- [ ] Tests pass: n/a (infraestructura)
- [ ] Build succeeds: `docker compose config` sin errores; `docker compose up -d`
- [ ] Manual check: `docker compose ps` muestra 5 réplicas; `docker inspect` confirma
      `NanoCpus=1000000000` y `Memory=536870912`; `docker exec` confirma `GOMAXPROCS=1`;
      request con el Host header responde 200

**Dependencies:** Pasos 8 y 9

**Files likely touched:**
- `docker-compose.yml`
- `.env.example`
- `Dockerfile` (ajustes finales)

**Estimated scope:** Small: 1-2 files

**Commit:** `operacion(compose): 5 replicas, 1 CPU, 512MB, GOMAXPROCS=1 y labels traefik.#(10)`

**Nota:** resolver antes las preguntas abiertas 2 (nombre de la red `mired` y regla de
labels) y 5 (`maxInFlight` default = 1 por réplica).

---

## Checkpoint B: Servicio

- [ ] Tests de crudo, multipart, tipo incorrecto, sobredimensionado y abort en verde
- [ ] `go test -race ./...` limpio
- [ ] Con `maxInFlight=1` y 10 concurrentes: 9º+ rechazado en < 10 ms, RSS bajo el techo
- [ ] `docker compose ps` muestra 5 réplicas; `NanoCpus=1000000000` y `Memory=536870912`
- [ ] Revisión humana antes de medir

---

## Paso 11: k6

**Descripción:** Ramp 10 s → 100 VUs, hold 20 s, down 10 s, con el PDF binario crudo como
body. Reportar `http_req_duration` p50/p95/p99, request rate y error rate.

**Acceptance criteria:**
- [ ] `scripts/k6.js` con la curva exacta: 10 s ramp a 100 VUs, 20 s hold, 10 s down
- [ ] Body = PDF binario crudo, `Content-Type: application/pdf`
- [ ] Reportados `http_req_duration` p50/p95/p99, `http_reqs` por segundo y error rate
- [ ] Corrida completa archivada (salida + JSON de métricas) con la fecha y el commit

**Verificación:**
- [ ] Tests pass: n/a (medición)
- [ ] Build succeeds: n/a
- [ ] Manual check: `k6 run scripts/k6.js` termina sin errores; métricas archivadas
      en `tasks/results/` (crear el directorio; el `.gitignore` no lo excluye)

**Dependencies:** Paso 10

**Files likely touched:**
- `scripts/k6.js`
- `tasks/results/k6-<fecha>-<commit>.json`

**Estimated scope:** Small: 1-2 files

**Commit:** `operacion(perf): corrida k6 ramp 100 VUs archivada con metricas.#(11)`

**Nota:** `k6` no está instalado en esta máquina. Instalar y registrar la versión en el
`README` junto al comando exacto.

---

## Paso 12: Vegeta

**Descripción:** `-rate 50 -duration 30s -timeout 30s`. Reportar success rate,
throughput, p50/p95/p99, no-2xx y timeouts.

**Acceptance criteria:**
- [ ] Corrida exacta: `vegeta attack -rate=50 -duration=30s -timeout=30s` con el
      `Host` header correcto y el PDF crudo
- [ ] Reportados success rate, throughput, p50/p95/p99, conteo de no-2xx y de timeouts
- [ ] Corrida archivada junto con la salida de `vegeta report`
- [ ] Versión de `vegeta` registrada

**Verificación:**
- [ ] Tests pass: n/a (medición)
- [ ] Build succeeds: n/a
- [ ] Manual check: los timeouts se atribuyen al servicio y no al cliente (el timeout
      del server, pregunta abierta 6, debe ser > 30 s o igual)

**Dependencies:** Paso 10

**Files likely touched:**
- `scripts/vegeta-target.txt`
- `scripts/run-vegeta.sh`
- `tasks/results/vegeta-<fecha>-<commit>.txt`

**Estimated scope:** Extra small: 1 file

**Commit:** `operacion(perf): corrida vegeta 50 rps 30s archivada con metricas.#(12)`

---

## Paso 13: comparación y reporte

**Descripción:** Tabla contra los cuatro números de la cátedra, diciendo **plainly qué se
cumple y qué no**. Verificar con `docker compose down -v` y reconstrucción desde cero, y
repetir las corridas 3 veces reportando varianza.

**Acceptance criteria:**
- [ ] `README.md` tiene una tabla con k6 (25,35 req/s · p50 1,88 s · p95 8,80 s · 0,00 %
      errores) y Vegeta (66,53 % éxito · 16,65 req/s · p50 14,89 s · 33,40 % timeouts)
      contra lo medido
- [ ] El reporte dice explícitamente **qué se cumplió y qué no**. Sin eufemismos: si
      no se llega a 25,35 req/s, está escrito
- [ ] Se documenta por qué 40-45 req/s es inalcanzable (`5 / S_cpu`; el inflate de
      94 ms es el piso)
- [ ] Comandos exactos de reproducción, copiables, para build, compose, k6 y vegeta
- [ ] `docker compose down -v` + reconstrucción desde cero, con las corridas repetidas
      3 veces y la varianza reportada (min/med/max)
- [ ] Versiones registradas: Go, Docker, k6, vegeta, `pdftotext`

**Verificación:**
- [ ] Tests pass: `./scripts/gate.sh` (≥ 70 %)
- [ ] Build succeeds: `docker compose down -v && docker compose up -d --build` desde cero
- [ ] Manual check: los comandos del `README` se ejecutan de corrido en una sesión limpia

**Dependencies:** Pasos 11 y 12

**Files likely touched:**
- `README.md`
- `tasks/plan.md` (log de medición final)
- `tasks/results/` (las 3 corridas)

**Estimated scope:** Small: 1-2 files

**Commit:** `operacion(reporte): comparacion contra la catedra, varianza de 3 corridas y comandos.#(13)`

---

## Checkpoint C: Entrega

- [ ] Las 4 métricas de la cátedra están en el `README` con comandos de reproducción exactos
- [ ] El reporte dice plainly qué se cumplió y qué no
- [ ] 3 corridas con varianza, desde `docker compose down -v`
- [ ] Gate ≥ 70 % en el commit final
- [ ] Listo para revisión

---

## Preguntas abiertas (bloqueantes)

| # | Pregunta | Bloquea |
|---|---|---|
| 1 | ~~¿De dónde sale el PDF de referencia?~~ **Resuelto:** fixture sintético en el Paso 0. Queda pendiente cargar el PDF real de la cátedra y regenerar el golden | — (resuelto) |
| 2 | ¿Nombre exacto de la red externa de Traefik (`mired`) y qué regla de labels usa? | Paso 10 |
| 3 | ¿Se permite `github.com/klauspost/compress` (sólo para inflate) o stdlib estricto? | Paso 6 |
| 4 | ¿Límite de tamaño de body para el 413? Propongo 16 MB | Paso 8 |
| 5 | ¿`maxInFlight=1` por réplica como default? | Pasos 9, 10 |
| 6 | ¿Timeout del server > 30 s para no atribuirle al servicio los timeouts de Vegeta? | Paso 8 |
| 7 | ~~¿Versión de `pdftotext`?~~ Registrada: **24.02.0** | — (resuelto) |