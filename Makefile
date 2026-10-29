SHELL := /bin/bash

VENV   := .venv
PY     := $(VENV)/bin/python
UV     := uv
# Optionally pin the interpreter:  make setup PYTHON=3.13
PYTHON ?=

.PHONY: help setup ingest ingest-rebuild parse ask probe dev server ui test clean

help:
	@echo "make setup           create .venv, install rag/agent/server, npm install in ui/"
	@echo "make ingest          ONE-TIME: download + parse the herbal, embed, persist Chroma"
	@echo "make ingest-rebuild  rebuild Chroma from data/processed/herbs.jsonl (no re-parse)"
	@echo "make parse           re-parse data/raw into herbs.jsonl + parse_report.json (no Ollama)"
	@echo "make ask Q=\"...\"     ask the ghost from the terminal"
	@echo "make probe Q=\"...\"   show retrieval scores (to calibrate GRADE_LOW/GRADE_HIGH)"
	@echo "make dev             start Flask API and Vite UI together"
	@echo "make test            run the Python test suites"
	@echo "make clean           remove venv, node_modules and the vector db"

setup:
	$(UV) venv $(VENV) $(if $(PYTHON),--python $(PYTHON),)
	$(UV) pip install --python $(PY) -e rag -e agent -e server
	npm --prefix ui install

ingest:
	$(PY) -m rag.ingest

ingest-rebuild:
	$(PY) -m rag.ingest --rebuild

# Re-parse data/raw and rewrite herbs.jsonl + parse_report.json. Fast, needs no Ollama.
parse:
	$(PY) -m rag.ingest --reparse --parse-only

server:
	$(PY) -m server

ui:
	npm --prefix ui run dev

dev:
	@trap 'kill 0' INT TERM EXIT; \
	$(PY) -m server & \
	npm --prefix ui run dev & \
	wait

test:
	$(PY) -m pytest rag/tests agent/tests server/tests -q

# Talk to the ghost from the terminal:  make ask Q="Something for a sleepless night?"
ask:
	$(PY) -m agent "$(Q)"

# Print retrieval scores to calibrate GRADE_LOW / GRADE_HIGH:  make probe Q="sleep"
probe:
	$(PY) -m agent --probe "$(Q)"

clean:
	rm -rf $(VENV) ui/node_modules ui/dist data/chroma
