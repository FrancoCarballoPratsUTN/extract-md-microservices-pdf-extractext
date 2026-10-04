package server_test

import (
	"context"
	"io"
	"net"
	"net/http"
	"runtime"
	"strings"
	"testing"
	"time"

	"extract-md/internal/httpapi"
	"extract-md/internal/server"
)

func TestAppliesTheAddressFromTheOptions(t *testing.T) {
	built := server.New(server.Options{Addr: ":8080"}, httpapi.New())

	if built.Addr != ":8080" {
		t.Errorf("Addr = %q, quiero %q", built.Addr, ":8080")
	}
}

func TestAppliesTheReadTimeoutFromTheOptions(t *testing.T) {
	built := server.New(server.Options{ReadTimeout: 7 * time.Second}, httpapi.New())

	if built.ReadTimeout != 7*time.Second {
		t.Errorf("ReadTimeout = %s, quiero 7s", built.ReadTimeout)
	}
}

func TestAppliesTheWriteTimeoutFromTheOptions(t *testing.T) {
	built := server.New(server.Options{WriteTimeout: 11 * time.Second}, httpapi.New())

	if built.WriteTimeout != 11*time.Second {
		t.Errorf("WriteTimeout = %s, quiero 11s", built.WriteTimeout)
	}
}

func TestServesHealthOverARealListener(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Listen: %v", err)
	}
	built := server.New(server.Options{}, httpapi.New())
	go func() { _ = built.Serve(listener) }()
	t.Cleanup(func() { _ = built.Close() })

	body, status := get(t, "http://"+listener.Addr().String()+"/health")

	if status != http.StatusOK {
		t.Errorf("status = %d, quiero %d", status, http.StatusOK)
	}
	if !strings.Contains(body, `"ok"`) {
		t.Errorf("cuerpo = %q, quiero que contenga \"ok\"", body)
	}
}

func TestRunReturnsWhenTheContextIsCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	finished := make(chan error, 1)
	go func() { finished <- server.Run(ctx, server.New(server.Options{Addr: freeAddr(t)}, httpapi.New())) }()
	cancel()

	select {
	case err := <-finished:
		if err != nil {
			t.Errorf("Run = %v, quiero nil tras cancelar", err)
		}
	case <-time.After(2 * time.Second):
		t.Error("Run no volvió tras cancelar el contexto")
	}
}

func TestRunReportsAnAddressThatCannotBeListenedOn(t *testing.T) {
	occupied, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Listen: %v", err)
	}
	defer func() { _ = occupied.Close() }()

	err = server.Run(context.Background(), server.New(server.Options{Addr: occupied.Addr().String()}, httpapi.New()))

	if err == nil {
		t.Fatal("Run no falló con una dirección ya ocupada")
	}
	if !strings.Contains(err.Error(), occupied.Addr().String()) {
		t.Errorf("el error %q no nombra la dirección", err)
	}
}

func TestRunStopsAcceptingConnectionsAfterShutdown(t *testing.T) {
	address := freeAddr(t)
	ctx, cancel := context.WithCancel(context.Background())
	finished := make(chan error, 1)
	built := server.New(server.Options{Addr: address}, httpapi.New())

	go func() { finished <- server.Run(ctx, built) }()
	waitUntilHealthy(t, address)

	cancel()
	select {
	case <-finished:
	case <-time.After(2 * time.Second):
		t.Fatal("Run no volvió tras cancelar el contexto")
	}

	if _, err := net.DialTimeout("tcp", address, 500*time.Millisecond); err == nil {
		t.Error("el servidor sigue aceptando conexiones después de apagar")
	}
}

func TestRepeatedRunsDoNotLeakGoroutines(t *testing.T) {
	startAndStop(t)
	settle(t)
	before := runtime.NumGoroutine()

	for range 25 {
		startAndStop(t)
	}

	settle(t)
	after := runtime.NumGoroutine()
	if after > before {
		t.Errorf("goroutines %d -> %d tras 25 arranques: se filtraron %d", before, after, after-before)
	}
}

func TestForgetsTheGoroutineOfAnUnreadShutdownResult(t *testing.T) {
	settle(t)
	before := runtime.NumGoroutine()

	for range 25 {
		ctx, cancel := context.WithCancel(context.Background())
		finished := make(chan error, 1)
		go func() { finished <- server.Run(ctx, server.New(server.Options{Addr: freeAddr(t)}, httpapi.New())) }()
		cancel()
		<-finished
	}

	settle(t)
	after := runtime.NumGoroutine()
	if after > before {
		t.Errorf("goroutines %d -> %d tras 25 ciclos: se filtraron %d", before, after, after-before)
	}
}

func startAndStop(t *testing.T) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	finished := make(chan error, 1)

	go func() {
		finished <- server.Run(ctx, server.New(server.Options{Addr: freeAddr(t)}, httpapi.New()))
	}()
	cancel()

	if err := <-finished; err != nil {
		t.Fatalf("Run: %v", err)
	}
}

func settle(t *testing.T) {
	t.Helper()
	for range 10 {
		runtime.GC()
		time.Sleep(10 * time.Millisecond)
	}
}

func freeAddr(t *testing.T) string {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Listen: %v", err)
	}
	address := listener.Addr().String()
	if err := listener.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}
	return address
}

func waitUntilHealthy(t *testing.T, address string) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		response, err := http.Get("http://" + address + "/health")
		if err == nil {
			_ = response.Body.Close()
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("el servidor en %s nunca respondió /health", address)
}

func get(t *testing.T, url string) (string, int) {
	t.Helper()
	response, err := http.Get(url)
	if err != nil {
		t.Fatalf("GET %s: %v", url, err)
	}
	defer func() { _ = response.Body.Close() }()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("ReadAll: %v", err)
	}
	return string(body), response.StatusCode
}
