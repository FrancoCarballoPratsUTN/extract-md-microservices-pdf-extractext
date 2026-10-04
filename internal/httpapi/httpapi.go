package httpapi

import (
	"encoding/json"
	"net/http"
)

type healthBody struct {
	Status string `json:"status"`
}

func New() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", health)
	return mux
}

func health(writer http.ResponseWriter, _ *http.Request) {
	writer.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(writer).Encode(healthBody{Status: "ok"})
}
