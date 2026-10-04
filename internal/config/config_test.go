package config_test

import (
	"strings"
	"testing"
	"time"

	"extract-md/internal/config"
)

func TestUsesTheDocumentedDefaultsWhenEveryVariableIsEmpty(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.Port != 8080 {
		t.Errorf("Port = %d, quiero 8080", loaded.Port)
	}
	if loaded.MaxBodyBytes != 16*1024*1024 {
		t.Errorf("MaxBodyBytes = %d, quiero %d", loaded.MaxBodyBytes, 16*1024*1024)
	}
	if loaded.MaxInflateBytes != 64*1024*1024 {
		t.Errorf("MaxInflateBytes = %d, quiero %d", loaded.MaxInflateBytes, 64*1024*1024)
	}
	if loaded.MaxInFlight != 1 {
		t.Errorf("MaxInFlight = %d, quiero 1", loaded.MaxInFlight)
	}
	if loaded.ReadTimeout != 30*time.Second {
		t.Errorf("ReadTimeout = %s, quiero 30s", loaded.ReadTimeout)
	}
	if loaded.WriteTimeout != 35*time.Second {
		t.Errorf("WriteTimeout = %s, quiero 35s", loaded.WriteTimeout)
	}
}

func TestReadsThePortFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"PORT": "9090"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.Port != 9090 {
		t.Errorf("Port = %d, quiero 9090", loaded.Port)
	}
}

func TestReadsTheBodyLimitFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"MAX_BODY_BYTES": "1024"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.MaxBodyBytes != 1024 {
		t.Errorf("MaxBodyBytes = %d, quiero 1024", loaded.MaxBodyBytes)
	}
}

func TestReadsTheInflateLimitFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"MAX_INFLATE_BYTES": "2048"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.MaxInflateBytes != 2048 {
		t.Errorf("MaxInflateBytes = %d, quiero 2048", loaded.MaxInflateBytes)
	}
}

func TestReadsTheConcurrencyLimitFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"MAX_INFLIGHT": "4"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.MaxInFlight != 4 {
		t.Errorf("MaxInFlight = %d, quiero 4", loaded.MaxInFlight)
	}
}

func TestReadsTheReadTimeoutFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"READ_TIMEOUT": "5s"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.ReadTimeout != 5*time.Second {
		t.Errorf("ReadTimeout = %s, quiero 5s", loaded.ReadTimeout)
	}
}

func TestReadsTheWriteTimeoutFromTheEnvironment(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"WRITE_TIMEOUT": "45s"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.WriteTimeout != 45*time.Second {
		t.Errorf("WriteTimeout = %s, quiero 45s", loaded.WriteTimeout)
	}
}

func TestIgnoresVariablesItDoesNotKnowAbout(t *testing.T) {
	loaded, err := loadWith(t, map[string]string{"PATH": "/usr/bin", "TZ": "UTC"})

	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if loaded.Port != 8080 {
		t.Errorf("Port = %d, quiero el default 8080", loaded.Port)
	}
}

func TestReportsTheVariableNameWhenANumberCannotBeParsed(t *testing.T) {
	_, err := loadWith(t, map[string]string{"MAX_BODY_BYTES": "muchos"})

	if err == nil {
		t.Fatal("Load no falló con MAX_BODY_BYTES=muchos")
	}
	if !strings.Contains(err.Error(), "MAX_BODY_BYTES") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestReportsTheVariableNameWhenADurationCannotBeParsed(t *testing.T) {
	_, err := loadWith(t, map[string]string{"READ_TIMEOUT": "pronto"})

	if err == nil {
		t.Fatal("Load no falló con READ_TIMEOUT=pronto")
	}
	if !strings.Contains(err.Error(), "READ_TIMEOUT") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestRejectsAPortOutsideTheValidRange(t *testing.T) {
	_, err := loadWith(t, map[string]string{"PORT": "70000"})

	if err == nil {
		t.Fatal("Load aceptó PORT=70000")
	}
	if !strings.Contains(err.Error(), "PORT") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestRejectsAPortOfZero(t *testing.T) {
	if _, err := loadWith(t, map[string]string{"PORT": "0"}); err == nil {
		t.Error("Load aceptó PORT=0")
	}
}

func TestRejectsAConcurrencyLimitOfZero(t *testing.T) {
	_, err := loadWith(t, map[string]string{"MAX_INFLIGHT": "0"})

	if err == nil {
		t.Fatal("Load aceptó MAX_INFLIGHT=0, que rechazaría todo request en silencio")
	}
	if !strings.Contains(err.Error(), "MAX_INFLIGHT") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestRejectsANegativeBodyLimit(t *testing.T) {
	_, err := loadWith(t, map[string]string{"MAX_BODY_BYTES": "-1"})

	if err == nil {
		t.Fatal("Load aceptó MAX_BODY_BYTES=-1")
	}
	if !strings.Contains(err.Error(), "MAX_BODY_BYTES") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestRejectsAReadTimeoutOfZero(t *testing.T) {
	_, err := loadWith(t, map[string]string{"READ_TIMEOUT": "0s"})

	if err == nil {
		t.Fatal("Load aceptó READ_TIMEOUT=0s")
	}
	if !strings.Contains(err.Error(), "READ_TIMEOUT") {
		t.Errorf("el error %q no nombra la variable", err)
	}
}

func TestNamesTheFirstInvalidVariableWhenSeveralAreWrong(t *testing.T) {
	_, err := loadWith(t, map[string]string{
		"PORT":         "ochenta",
		"MAX_INFLIGHT": "0",
		"READ_TIMEOUT": "pronto",
	})

	if err == nil {
		t.Fatal("Load aceptó tres variables inválidas")
	}
	if !strings.Contains(err.Error(), "PORT") {
		t.Errorf("el error %q no nombra la primera variable inválida", err)
	}
}

func TestSaysWhichMinimumAppliesWithoutLeakingInternalConstants(t *testing.T) {
	_, err := loadWith(t, map[string]string{"MAX_INFLIGHT": "0"})

	if err == nil {
		t.Fatal("Load aceptó MAX_INFLIGHT=0")
	}
	if !strings.Contains(err.Error(), "mínimo 1") {
		t.Errorf("el error %q no dice cuál es el mínimo", err)
	}
	if strings.Contains(err.Error(), "9223372036854775807") {
		t.Errorf("el error %q filtra una constante interna", err)
	}
}

func TestSaysWhichMaximumAppliesToThePort(t *testing.T) {
	_, err := loadWith(t, map[string]string{"PORT": "70000"})

	if err == nil {
		t.Fatal("Load aceptó PORT=70000")
	}
	if !strings.Contains(err.Error(), "máximo 65535") {
		t.Errorf("el error %q no dice cuál es el puerto máximo", err)
	}
}

func loadWith(t *testing.T, overrides map[string]string) (config.Config, error) {
	t.Helper()
	for _, name := range []string{
		"PORT",
		"MAX_BODY_BYTES",
		"MAX_INFLATE_BYTES",
		"MAX_INFLIGHT",
		"READ_TIMEOUT",
		"WRITE_TIMEOUT",
	} {
		t.Setenv(name, overrides[name])
	}
	return config.Load()
}
