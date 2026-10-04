package main

import (
	"context"
	"log"
	"os/signal"
	"strconv"
	"syscall"

	"extract-md/internal/config"
	"extract-md/internal/httpapi"
	"extract-md/internal/server"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("configuración inválida: %v", err)
	}

	httpServer := server.New(server.Options{
		Addr:         ":" + strconv.FormatInt(cfg.Port, 10),
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}, httpapi.New())

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := server.Run(ctx, httpServer); err != nil {
		log.Fatalf("el servidor terminó con error: %v", err)
	}
}
