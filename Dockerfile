FROM golang:1.22-alpine AS build

WORKDIR /src

COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal

ENV CGO_ENABLED=0

RUN go build -trimpath -ldflags="-s -w" -o /out/extract-md ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=build /out/extract-md /extract-md

EXPOSE 8080

USER nonroot:nonroot

ENTRYPOINT ["/extract-md"]
