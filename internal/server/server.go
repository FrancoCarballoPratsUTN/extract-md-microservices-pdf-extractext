package server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"time"
)

const shutdownGrace = 10 * time.Second

type Options struct {
	Addr         string
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
}

func New(options Options, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:         options.Addr,
		Handler:      handler,
		ReadTimeout:  options.ReadTimeout,
		WriteTimeout: options.WriteTimeout,
	}
}

func Run(ctx context.Context, httpServer *http.Server) error {
	listener, err := listen(httpServer.Addr)
	if err != nil {
		return err
	}

	served := make(chan error, 1)
	go func() { served <- httpServer.Serve(listener) }()

	select {
	case err := <-served:
		return stopped(httpServer, err)
	case <-ctx.Done():
		return stop(httpServer, shutdownGrace)
	}
}

func listen(address string) (net.Listener, error) {
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return nil, fmt.Errorf("no se pudo escuchar en %s: %w", address, err)
	}
	return listener, nil
}

func stopped(httpServer *http.Server, err error) error {
	if errors.Is(err, http.ErrServerClosed) {
		return nil
	}
	return fmt.Errorf("el servidor dejó de servir en %s: %w", httpServer.Addr, err)
}

func stop(httpServer *http.Server, grace time.Duration) error {
	deadline, cancel := context.WithTimeout(context.Background(), grace)
	defer cancel()

	if err := httpServer.Shutdown(deadline); err != nil {
		_ = httpServer.Close()
		return fmt.Errorf("apagado incompleto de %s: %w", httpServer.Addr, err)
	}
	return nil
}
