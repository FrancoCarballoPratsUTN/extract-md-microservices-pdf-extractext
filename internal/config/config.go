package config

import (
	"fmt"
	"math"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Port            int64
	MaxBodyBytes    int64
	MaxInflateBytes int64
	MaxInFlight     int64
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
}

const (
	portName            = "PORT"
	maxBodyBytesName    = "MAX_BODY_BYTES"
	maxInflateBytesName = "MAX_INFLATE_BYTES"
	maxInFlightName     = "MAX_INFLIGHT"
	readTimeoutName     = "READ_TIMEOUT"
	writeTimeoutName    = "WRITE_TIMEOUT"
)

const (
	defaultPort            int64 = 8080
	defaultMaxBodyBytes    int64 = 16 * 1024 * 1024
	defaultMaxInflateBytes int64 = 64 * 1024 * 1024
	defaultMaxInFlight     int64 = 1
	defaultReadTimeout           = 30 * time.Second
	defaultWriteTimeout          = 35 * time.Second
)

const (
	minPort        int64 = 1
	maxPort        int64 = 65535
	minBytes       int64 = 1
	minConcurrency int64 = 1
	noLimit        int64 = math.MaxInt64
)

func Load() (Config, error) {
	env := &environment{}

	loaded := Config{
		Port:            env.integer(portName, defaultPort, minPort, maxPort),
		MaxBodyBytes:    env.integer(maxBodyBytesName, defaultMaxBodyBytes, minBytes, noLimit),
		MaxInflateBytes: env.integer(maxInflateBytesName, defaultMaxInflateBytes, minBytes, noLimit),
		MaxInFlight:     env.integer(maxInFlightName, defaultMaxInFlight, minConcurrency, noLimit),
		ReadTimeout:     env.duration(readTimeoutName, defaultReadTimeout),
		WriteTimeout:    env.duration(writeTimeoutName, defaultWriteTimeout),
	}
	if err := env.failure; err != nil {
		return Config{}, err
	}
	return loaded, nil
}

type environment struct {
	failure error
}

func (e *environment) integer(name string, fallback, min, max int64) int64 {
	if e.failure != nil {
		return fallback
	}

	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}

	parsed, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		e.failure = fmt.Errorf("%s=%q no es un entero: %w", name, raw, err)
		return fallback
	}
	if parsed < min {
		e.failure = fmt.Errorf("%s=%d es menor que el mínimo %d", name, parsed, min)
		return fallback
	}
	if parsed > max {
		e.failure = fmt.Errorf("%s=%d excede el máximo %d", name, parsed, max)
		return fallback
	}
	return parsed
}

func (e *environment) duration(name string, fallback time.Duration) time.Duration {
	if e.failure != nil {
		return fallback
	}

	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}

	parsed, err := time.ParseDuration(raw)
	if err != nil {
		e.failure = fmt.Errorf("%s=%q no es una duración (ej: 30s): %w", name, raw, err)
		return fallback
	}
	if parsed <= 0 {
		e.failure = fmt.Errorf("%s=%s debe ser mayor que cero", name, parsed)
		return fallback
	}
	return parsed
}
