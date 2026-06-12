.PHONY: sync lint fmt test build

sync:
	uv sync

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

test:
	uv run pytest

build:
	uv run python -m blocklist_builder.cli build --no-fetch
