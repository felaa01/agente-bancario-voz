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

sembrar:
	uv run python -m agente_voz.api_banco.datos_sinteticos

cargar-politicas:
	uv run python -m agente_voz.rag.cargador

evaluar-intenciones:
	uv run --env-file .env python -m agente_voz.evaluaciones.ejecutar_intenciones

api:
	uv run uvicorn agente_voz.api_banco.app:app --reload

chat:
	uv run --env-file .env python -m agente_voz.agente.cli
