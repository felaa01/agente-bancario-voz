.PHONY: instalar lint formatear tipos pruebas verificar bd-iniciar bd-detener

instalar:
	uv sync
	uv run pre-commit install

lint:
	uv run ruff check .

formatear:
	uv run ruff format .

tipos:
	uv run mypy src pruebas

pruebas:
	uv run pytest -m "not en_vivo"

verificar:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src pruebas
	uv run pytest -m "not en_vivo"

bd-iniciar:
	docker compose up -d

bd-detener:
	docker compose down
