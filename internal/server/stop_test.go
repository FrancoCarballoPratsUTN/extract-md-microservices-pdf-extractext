package server

import (
	"io"
	"net"
	"net/http"
	"testing"
	"time"
)

func TestStopClosesPendingRequestsWhenTheGraceExpires(t *testing.T) {
	service, requestDone := servingRequestThatNeverFinishes(t)

	err := stop(service, 50*time.Millisecond)

	if err == nil {
		t.Fatal("stop no reportó que el apagado quedó incompleto")
	}

	select {
	case err := <-requestDone:
		if err == nil {
			t.Error("la conexión del cliente sigue viva después del apagado forzado")
		}
	case <-time.After(2 * time.Second):
		t.Error("la conexión del cliente quedó colgada: stop no la cerró a la fuerza")
	}
}

func servingRequestThatNeverFinishes(t *testing.T) (*http.Server, chan error) {
	t.Helper()

	release := make(chan struct{})
	entered := make(chan struct{}, 1)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Listen: %v", err)
	}

	service := New(Options{Addr: listener.Addr().String()}, http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		entered <- struct{}{}
		<-release
	}))
	go func() { _ = service.Serve(listener) }()
	t.Cleanup(func() {
		close(release)
		_ = service.Close()
	})

	requestDone := make(chan error, 1)
	go func() {
		response, err := http.Get("http://" + listener.Addr().String() + "/")
		if err == nil {
			_, _ = io.Copy(io.Discard, response.Body)
			_ = response.Body.Close()
		}
		requestDone <- err
	}()

	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("el request nunca llegó al handler")
	}

	return service, requestDone
}
