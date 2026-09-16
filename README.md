# Agente bancario de voz

![CI](https://github.com/felaa01/agente-bancario-voz/actions/workflows/ci.yml/badge.svg)

Proyecto de portfolio: un agente bancario que atiende por voz, en español rioplatense, a los
clientes de un banco ficticio uruguayo. Resuelve consultas de movimientos, bloqueo de tarjetas,
apertura de disputas y preguntas sobre políticas, con verificación de identidad, guardrails y
evaluación de punta a punta.

La especificación completa (alcance, arquitectura detallada, evaluación en tres niveles y plan por
semanas) está en [docs/plan-del-proyecto.md](docs/plan-del-proyecto.md). Las reglas de diseño no
negociables y las decisiones tomadas están en [CLAUDE.md](CLAUDE.md).

## Estado actual

Semana 1 completa, semana 2 en curso (RAG de políticas):

- Paquete `src/agente_voz/` con `uv`, tipado estricto (`mypy --strict`) y `py.typed`.
- `ruff` (lint + formato) y `mypy` como hooks de `pre-commit`, más CI en GitHub Actions.
- Base de datos local (PostgreSQL + pgvector) vía `docker-compose.yml`, con límite de memoria.
- `Sesion` y el decorador `@requiere_verificacion` (autorización aplicada en el código).
- Backend bancario simulado: esquema SQL, capa de acceso a datos con `asyncpg`, datos sintéticos
  con Faker y un servicio FastAPI (`api_banco/app.py`) con los endpoints que van a usar las
  herramientas del agente.
- Agente conversacional en modo texto contra Gemini (`agente/bucle.py`, `make chat`), con sus seis
  herramientas.
- RAG híbrido de políticas: embeddings con `multilingual-e5-small` vía `fastembed` (ONNX
  cuantizado), tabla `politicas` en pgvector y búsqueda que combina texto completo en español con
  similitud vectorial (Reciprocal Rank Fusion). Falta escribir los documentos reales en
  `datos/politicas/` y las evaluaciones de intención y conversaciones simuladas de la semana 2.
- Todavía no hay pipeline de voz (STT, VAD, TTS) — eso es la semana 3.

## Arquitectura

Pipeline de voz en cascada (no speech-to-speech de punta a punta), para poder medir, registrar y
auditar cada etapa por separado, algo no negociable en un dominio bancario:

```
audio -> VAD (Silero) -> STT (faster-whisper) -> agente LLM (Gemini) -> TTS -> audio
```

El agente corre un loop de herramientas escrito a mano (sin framework de agentes) contra seis
herramientas: `verificar_identidad`, `obtener_movimientos`, `bloquear_tarjeta`, `abrir_disputa`,
`buscar_politicas` (RAG híbrido sobre políticas propias, en PostgreSQL + pgvector) y
`derivar_a_humano`. El backend bancario es un servicio FastAPI con datos sintéticos.

Detalle completo, trade-offs y el porqué de cada elección: [docs/plan-del-proyecto.md](docs/plan-del-proyecto.md).

## Decisiones de diseño

- **Cascada en vez de speech-to-speech:** menos latencia potencial con speech-to-speech, pero
  mucho menos control y auditabilidad — inaceptable para un banco.
- **La autorización se aplica en el código, no en el prompt:** un decorador `@requiere_verificacion`
  rechaza las herramientas sensibles si la sesión no está verificada, sin importar lo que diga el
  modelo. Es la primera pieza de código no trivial del proyecto (semana 1).
- **`uv` con el build backend nativo (`uv_build`)** en vez de `hatchling`/`setuptools`: un actor
  menos en la cadena de empaquetado, y ya viene con `uv`.
- **Docker Engine dentro de WSL, sin Docker Desktop:** en una máquina de 8 GB sin GPU, el overhead
  de Docker Desktop no entra en el presupuesto de memoria del proyecto.
- **Límite de memoria del contenedor de base de datos con `mem_limit` (nivel de servicio), no con
  `deploy.resources.limits`:** esta última solo la aplica `docker compose up` en modo Swarm;
  `mem_limit` sí la hace cumplir en un `up` normal. Verificado con `docker stats`.
- **Variante de español:** rioplatense. **País del banco ficticio:** Uruguay, con cédula de
  identidad para verificar identidad y cuentas en pesos uruguayos y dólares.

## Evaluación

Métricas a reportar, evaluadas en tres niveles (intención con MInDS-14, conversaciones simuladas
cliente-vs-agente, y voz de punta a punta). Todavía no hay resultados — se completa a partir de la
semana 2.

| Métrica                                    | Objetivo   | Resultado actual |
| ------------------------------------------- | ---------- | ----------------- |
| Tasa de tarea completada                    | —          | Pendiente          |
| Violaciones de política                     | Cero       | Pendiente          |
| Latencia de punta a punta (p95)             | A definir* | Pendiente          |
| Precisión de intención (MInDS-14 es-ES)     | —          | Pendiente          |
| Tasa de error de palabras (STT)             | —          | Pendiente          |
| Comparación API (Gemini) vs modelo cuantizado | —        | Pendiente          |

\* El objetivo original era <1s hasta el primer audio de respuesta; en esta máquina sin GPU se mide
primero y después se fija un objetivo realista.

## Cómo ejecutarlo en local

Requisitos: Windows 11 + WSL2 (Ubuntu 24.04) sin Docker Desktop, con el entorno de
[docs/configuracion/](docs/configuracion/) ya instalado (`configurar-wsl.sh`).

```bash
git clone git@github.com:felaa01/agente-bancario-voz.git
cd agente-bancario-voz
cp .env.ejemplo .env    # completar GEMINI_API_KEY
make instalar           # uv sync + hooks de pre-commit
make bd-iniciar          # levanta PostgreSQL + pgvector
docker compose exec -T bd psql -U agente_voz -d agente_voz < src/agente_voz/api_banco/esquema.sql
make sembrar             # datos sinteticos con Faker (clientes, cuentas, tarjetas, movimientos)
make cargar-politicas    # carga y embebe los .md de datos/politicas/ para el RAG
make api                 # levanta el backend FastAPI en http://127.0.0.1:8000
make verificar           # lint, formato, tipos y pruebas (lo mismo que corre el CI)
```

Objetivos disponibles del `Makefile`: `instalar`, `lint`, `formatear`, `tipos`, `pruebas`,
`verificar`, `bd-iniciar`, `bd-detener`, `sembrar`, `cargar-politicas`, `api`, `chat`.

## Presupuesto de recursos

Objetivo: el sistema completo en ejecución debe rondar los 3-4 GB, dentro de un límite duro de
5 GB para WSL (`.wslconfig`, en una máquina de 8 GB totales sin GPU).

| Componente                          | Límite asignado | Uso medido        |
| ------------------------------------ | ---------------- | ------------------ |
| WSL2 (Ubuntu + Docker + todo)        | 5 GB (`.wslconfig`) | —                |
| PostgreSQL + pgvector (`docker-compose.yml`) | 512 MB     | ~28 MB en reposo   |
| Backend FastAPI (`uvicorn`, proceso local, todavía sin contenedor) | Por definir | ~54 MB en reposo |
| Embeddings del RAG (`fastembed`, ONNX cuantizado, en el proceso del agente) | Por definir | ~505 MB de pico (proceso completo, con onnxruntime cargado) |
| STT (faster-whisper) / VAD / TTS     | Por definir       | Todavía no existe  |
| Observabilidad (Jaeger o Phoenix)    | Por definir       | Todavía no existe  |

Se va a completar a medida que se agreguen los servicios de `docker-compose.yml` y el resto del
pipeline.
