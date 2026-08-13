# namemask 開発タスク。Linux / macOS / Windows(WSL・Git Bash) で動くこと。

PYTHON ?= python3

.PHONY: help install test test-all eval lint fmt build clean

help:
	@echo "install    開発依存を入れる（editable + dev extra）"
	@echo "test       pytest（NER/LLM 要のテストは skip）"
	@echo "test-all   pytest 全実行（GiNZA / Ollama をローカルに要求）"
	@echo "eval       決定的層の実測 + 層別アブレーション（docs/accuracy.md を更新）"
	@echo "lint       ruff check + format --check"
	@echo "fmt        ruff format（書き換える）"
	@echo "build      sdist + wheel を作る"
	@echo "clean      生成物を消す"

install:
	$(PYTHON) -m pip install -e ".[dev,crypto]"

test:
	$(PYTHON) -m pytest -m "not ner and not llm"

test-all:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) tests/eval.py --address --write-docs

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

fmt:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

build: clean
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*

clean:
	rm -rf build dist *.egg-info src/*.egg-info
	rm -rf .pytest_cache .hypothesis .ruff_cache .mypy_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
