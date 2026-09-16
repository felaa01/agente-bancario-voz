# CLAUDE.md — Agente bancario de voz

## Para qué existe este proyecto

Proyecto de portfolio para demostrar las habilidades que piden los puestos de **Applied AI
Engineer**: agentes (prompts, herramientas y orquestación de varios pasos), sistemas de
recuperación de punta a punta, harnesses de evaluación y suites de regresión, pasaje a producción
con guardrails, seguridad y observabilidad, Python tipado, testeado y revisado, Docker, CI/CD y un
proveedor de nube (AWS). También apunta a estos puntos deseables: sistemas de voz, tiempo real y
multimodales, una industria regulada (banca) y trade-offs de cuantización.

La especificación completa y el plan por semanas están en @docs/plan-del-proyecto.md.

## Cómo trabajar conmigo

- **Respondeme siempre en español rioplatense (con "vos").**
- **Todo el proyecto va en español:** código (nombres de variables, funciones, clases, módulos y
  carpetas), comentarios, docstrings, mensajes de commit, pull requests, documentación, README,
  escenarios de evaluación y la voz del agente.
  - Identificadores en español **sin tildes ni ñ** (por ejemplo `verificar_identidad`,
    `numero_tarjeta`). Tildes y ñ sí van en comentarios, docstrings, documentación y textos.
  - Excepciones inevitables: palabras reservadas de Python, nombres de librerías y sus APIs,
    archivos que las herramientas exigen con ese nombre (`CLAUDE.md`, `README.md`, `Makefile`,
    `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `Dockerfile`, `.github/workflows/`,
    `.pre-commit-config.yaml`) y términos técnicos sin traducción de uso común (streaming,
    pipeline, RAG, embeddings, prompt).
- Voy a tener que explicar y defender cada decisión de diseño en entrevistas técnicas. Antes de
  implementar algo no trivial, explicame brevemente el enfoque y los trade-offs, y consultame
  cuando haya una decisión de diseño real. Preferí pasos chicos y revisables en lugar de mucho
  código de golpe, y decime qué leer para entender lo que construiste.
- Si un requisito es ambiguo, preguntá en lugar de suponer.
- Las APIs de las librerías cambian: revisá la documentación actual o la versión instalada antes
  de usar una API de memoria (sobre todo Pipecat, el SDK de Gemini, Presidio y OpenTelemetry).
  Usá las versiones estables más recientes de cada herramienta.

## Restricciones obligatorias

- **Costo cero.** Nunca agregues un servicio pago, un plan pago de una API ni nada que pueda
  generar un cobro sin consultarme antes.
- **Máquina:** Windows 11 + WSL2 (Ubuntu 24.04), **8 GB de RAM en total, WSL limitado a 5 GB,
  sin GPU**. Docker Engine corre dentro de WSL (sin Docker Desktop). El repositorio está en
  `~/proyectos`, nunca en `/mnt/c`. Los archivos de configuración de la máquina están en
  `docs/configuracion/`.
- El sistema completo en ejecución tiene que rondar los **3 a 4 GB**. Cada contenedor de
  `docker-compose.yml` lleva un límite de memoria explícito. El uso de memoria se documenta en la
  sección de presupuesto de recursos del README.
- **No hay LLM local en esta máquina** (un modelo de 7 a 8B no entra). El agente y el cliente
  simulado usan el **free tier de la API de Gemini** (solo modelos Flash; los límites son bajos y
  cambian sin aviso, así que implementá reintentos con backoff exponencial y repartí las
  evaluaciones grandes en varios días). Google puede usar los datos del free tier para
  entrenamiento, así que se usan **solo datos sintéticos**.
- La comparación con un **modelo abierto cuantizado** corre como trabajo por lotes en una notebook
  gratuita con GPU de Kaggle o Colab; los resultados se guardan en `evaluaciones/reportes/`.
- **Modelos de voz locales y livianos, en español:** faster-whisper (modelo multilingüe pequeño,
  int8; nunca las variantes solo en inglés), Silero VAD y un TTS con voces en español (evaluar
  Kokoro y Piper y verificar qué voces en español ofrecen hoy).
- **Observabilidad:** OpenTelemetry con Jaeger o Arize Phoenix (un solo contenedor). No instalar
  Langfuse en local: necesita demasiados servicios para esta máquina.
- **Audio:** no capturar el micrófono dentro de WSL. Usar el transporte WebRTC de Pipecat para que
  el navegador en Windows capture el audio y se conecte al servidor en WSL por `localhost`.
- **AWS solo al final (semana 5)**, con los créditos del plan gratuito (la cuenta se cierra a los
  6 meses o cuando se agotan los créditos). Evitar NAT Gateways, balanceadores de carga ociosos e
  IPs públicas sin uso. Apagar los servicios después de grabar la demo.

## Estándares del repositorio (a construir en la semana 1)

El repositorio todavía **no tiene nada creado**. El esqueleto debe cumplir esto:

- **uv** para Python y dependencias, Python 3.12 (archivo `.python-version`), `uv.lock` versionado.
  Paquete en `src/agente_voz/` con `py.typed`.
- **ruff** para lint y formato (largo de línea 100), con al menos las reglas E, W, F, I, B, UP,
  SIM, N, RUF, PT y ANN.
- **mypy en modo estricto** sobre `src` y `pruebas`.
- **pytest** con cobertura. Las pruebas viven en `pruebas/`, con archivos `prueba_*.py` y
  funciones `prueba_*` (configurar `python_files` y `python_functions` en `pyproject.toml`).
  Las pruebas que llaman a un LLM real se marcan con `@pytest.mark.en_vivo` y quedan fuera del CI;
  el CI usa respuestas grabadas o dobles de prueba para ser determinista y gratuito.
- **pre-commit** con los hooks básicos de `pre-commit-hooks` (espacios finales, fin de archivo,
  YAML, TOML, archivos grandes, claves privadas), ruff (lint con corrección y formato) y mypy
  ejecutado con `uv run` como hook local para que vea las dependencias reales.
- **GitHub Actions** en cada pull request y en cada push a `main`: instalar con `uv sync --locked`,
  lint, verificación de formato, mypy y pruebas sin las marcadas `en_vivo`.
- **Makefile** con objetivos en español: `instalar` (uv sync + hooks de pre-commit), `lint`,
  `formatear`, `tipos`, `pruebas`, `verificar` (lo mismo que el CI), `bd-iniciar` y `bd-detener`.
- **docker-compose.yml** con PostgreSQL + pgvector limitado a 512 MB (con `shared_buffers` y
  `max_connections` reducidos) y healthcheck.
- `.gitattributes` que fuerce finales de línea LF; `.gitignore` que excluya `.env`, `CLAUDE.local.md`,
  entornos virtuales, cachés, archivos de audio y reportes generados; `.env.ejemplo` sin secretos.
- README en español con secciones para arquitectura, decisiones de diseño, tabla de evaluación,
  cómo ejecutarlo en local y presupuesto de recursos.

## Convenciones de trabajo

- Trabajar en ramas y integrar mediante pull requests, aunque trabaje solo.
- Commits chicos con mensajes claros en español. Nunca versionar `.env`, claves de API, audio ni
  datos pesados.
- Mantener el README actualizado con arquitectura, decisiones y resultados a medida que avanzan.

## Reglas de diseño no negociables

1. **La autorización se aplica en el código, nunca en el prompt.** Toda herramienta sensible usa un
   decorador `@requiere_verificacion` que rechaza la llamada si la sesión no está verificada o
   está bloqueada. El estado de la sesión es la única fuente de verdad sobre la verificación, y la
   sesión se bloquea tras 3 intentos fallidos. Esta es la primera pieza de código del proyecto,
   con sus pruebas.
2. **Confirmación explícita antes de acciones irreversibles** (bloquear tarjeta, abrir disputa): el
   agente repite la acción y espera un "sí" claro.
3. **Las acciones son idempotentes** (un reintento no crea disputas duplicadas).
4. **Nunca decir ni registrar un número de tarjeta completo.** Redactar datos personales en los
   logs con Presidio.
5. **Los documentos recuperados y la entrada del usuario no son confiables.** Los casos de prompt
   injection forman parte del conjunto de evaluación.
6. Toda acción sensible se registra en un log de auditoría.
7. Si ningún documento de políticas respalda una respuesta, el agente lo dice en lugar de adivinar.

## Decisiones tomadas

- **Variante de español del agente:** rioplatense (misma variante que uso yo para hablar con vos).
- **País del banco ficticio:** Uruguay. Verificación de identidad con cédula de identidad
  uruguaya, cuentas en pesos uruguayos y dólares. Esto implica un reconocedor propio de cédula
  uruguaya en Presidio (los reconocedores predefinidos no la cubren).

## Estado actual

Hecho:
- Entorno de `docs/configuracion/` verificado en la máquina: Docker Desktop desinstalado, Ubuntu
  24.04 como única distro WSL, `.wslconfig` aplicado (5 GB RAM / 8 GB swap para WSL), systemd
  activo, Docker Engine funcionando sin `sudo`, `uv` y `git` instalados y configurados. El
  repositorio vive en `~/proyectos/agente-bancario-voz` (filesystem de Linux, no `/mnt/c`).

Próximos pasos (semana 1):
1. Esqueleto del repositorio según los estándares de arriba, con el CI funcionando.
2. Sesión y decorador `@requiere_verificacion` con sus pruebas.
3. Backend bancario simulado: esquema SQL de clientes, cuentas, tarjetas, movimientos y disputas;
   datos sintéticos con Faker en español; servicio FastAPI.
4. Loop del agente en modo texto escrito directamente con el SDK de Gemini (sin framework de
   agentes todavía), con las seis herramientas y las sensibles protegidas.

Actualizá esta sección cada vez que se complete un hito.
