package httpapi_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"extract-md/internal/httpapi"
)

func TestHealthRespondsWithTwoHundred(t *testing.T) {
	response := get(t, httpapi.New(), "/health")

	if response.Code != http.StatusOK {
		t.Errorf("status = %d, quiero %d", response.Code, http.StatusOK)
	}
}

func TestHealthBodyIsJsonWithAnOkStatus(t *testing.T) {
	response := get(t, httpapi.New(), "/health")

	var body struct {
		Status string `json:"status"`
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatalf("el cuerpo %q no es JSON: %v", response.Body.String(), err)
	}
	if body.Status != "ok" {
		t.Errorf("status = %q, quiero %q", body.Status, "ok")
	}
}

func TestHealthDeclaresJsonContentType(t *testing.T) {
	response := get(t, httpapi.New(), "/health")

	if got := response.Header().Get("Content-Type"); got != "application/json" {
		t.Errorf("Content-Type = %q, quiero %q", got, "application/json")
	}
}

func TestHealthRespondsInUnderFiveMilliseconds(t *testing.T) {
	handler := httpapi.New()

	started := time.Now()
	response := get(t, handler, "/health")
	elapsed := time.Since(started)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, quiero %d", response.Code, http.StatusOK)
	}
	if elapsed >= 5*time.Millisecond {
		t.Errorf("/health tardó %s, el criterio es < 5ms", elapsed)
	}
}

func TestUnknownPathRespondsWithNotFound(t *testing.T) {
	response := get(t, httpapi.New(), "/no-existe")

	if response.Code != http.StatusNotFound {
		t.Errorf("status = %d, quiero %d", response.Code, http.StatusNotFound)
	}
}

func TestWrongMethodOnHealthRespondsWithMethodNotAllowed(t *testing.T) {
	request := httptest.NewRequest(http.MethodPost, "/health", nil)
	recorder := httptest.NewRecorder()

	httpapi.New().ServeHTTP(recorder, request)

	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, quiero %d", recorder.Code, http.StatusMethodNotAllowed)
	}
}

func get(t *testing.T, handler http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest(http.MethodGet, path, nil)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, request)

	return recorder
}
