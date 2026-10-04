# extract-md-microservices-pdf-extractext

Microservicio HTTP que recibe un PDF y devuelve su texto como Markdown, en Go puro:
sin cgo, sin librerías de PDF de terceros, todo en memoria (nada de disco, nada de
subprocess). Corre detrás de Traefik con 5 réplicas de 1 CPU y 512 MB.

El plan de trabajo completo está en `tasks/plan.md` y la lista de tareas en
`tasks/todo.md`.

## Gate de corrección

La regla que ningún commit puede violar: el texto extraído tiene que coincidir con la
salida de `pdftotext` en **≥ 70 % de las palabras**.

```bash
./scripts/gate.sh                        # extrae con bin/extract-md y compara
./scripts/gate.sh mi-salida.txt          # compara un archivo contra el golden
GATE_MINIMUM=0.85 ./scripts/gate.sh      # subir el listón, no bajarlo
```

La coincidencia se cuenta por **multiset** de palabras (minúsculas, sin puntuación,
sin dígitos). El gate es lineal en el volumen extraído: texto al 80 % del golden
→ 80,00 % de coincidencia.

## Fixture de referencia

`testdata/ref.pdf` **es generado**, no es el PDF de la cátedra (que no está disponible).
`tools/fixture/` lo escribe byte a byte replicando las características que definen el
presupuesto de CPU:

| Característica | Cátedra | Fixture |
|---|---|---|
| Páginas | 250 | 250 |
| Bytes en disco | 5.229.573 | 2.462.322 |
| Caracteres de texto | 709.803 | 709.203 |
| Imágenes dibujadas | 5.563 | 5.563 |
| Streams Flate | 1.417 | 1.417 |
| Descomprimido | ~25 MB | 26.827.465 B |

```bash
./scripts/gen-fixture.sh                 # regenera testdata/ref.pdf y el golden
python3 -m unittest discover -s tools -t . -p '*_test.py'
```

El generador es determinista y sus tests comprueban que `pdftotext` recupera el 100 %
del texto que el fixture dice contener.

## Requisitos

| Herramienta | Versión verificada | Para qué |
|---|---|---|
| Go | 1.26.8 (mínimo 1.22) | el servicio |
| `pdftotext` (poppler-utils) | 24.02.0 | el oráculo del gate |
| Docker | 29.8.2 | el compose del paso 10 |
| Python | 3.12.3 | sólo las herramientas de fixture y gate |

`k6` y `vegeta` se necesitan para el Bloque C y todavía no están instalados: sus
versiones quedan registradas acá cuando se midan.