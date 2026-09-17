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
- Esqueleto del repositorio completo: paquete `src/agente_voz/` con `uv` (build backend nativo),
  `ruff`, `mypy --strict` y `pytest` (con marcador `en_vivo`); `pre-commit` con hooks básicos +
  ruff + mypy; `Makefile` con los objetivos en español; `docker-compose.yml` con PostgreSQL +
  pgvector (512 MB, verificado con `docker stats`); CI en GitHub Actions (`uv sync --locked`,
  lint, formato, tipos, pruebas); README con arquitectura, decisiones, evaluación (pendiente de
  resultados), cómo correrlo local y presupuesto de recursos. Repo conectado y pusheado en
  [github.com/felaa01/agente-bancario-voz](https://github.com/felaa01/agente-bancario-voz)
  (público), acceso por SSH desde WSL.

- `Sesion` y el decorador `@requiere_verificacion` con pruebas (autorización en el código, no en
  el prompt). Backend bancario simulado completo: esquema SQL (`clientes`, `cuentas`, `tarjetas`,
  `tarjetas` con solo los últimos 4 dígitos, `movimientos`, `disputas`), capa de acceso a datos
  tipada con `asyncpg` (`bloquear_tarjeta` y `crear_disputa` idempotentes), datos sintéticos con
  Faker (`es_AR`, el locale más cercano a Uruguay que existe) y servicio FastAPI con los
  endpoints que van a usar las herramientas del agente.
- Cliente HTTP del agente hacia esa API (`herramientas/cliente_banco.py`, con `httpx2`) y las seis
  herramientas (`herramientas/herramientas.py`): `verificar_identidad` (cédula + fecha de
  nacimiento, sin decorador porque es la que verifica), `obtener_movimientos`, `bloquear_tarjeta`
  y `abrir_disputa` (con `@requiere_verificacion`, y estas dos últimas piden un `confirmado: bool`
  explícito antes de ejecutar — no alcanza con que el prompt lo pida), `buscar_politicas` (todavía
  sin RAG: responde honestamente que no tiene la base cargada) y `derivar_a_humano` (funciona
  incluso con la sesión bloqueada).
- Loop del agente escrito a mano contra el SDK `google-genai` (`agente/bucle.py`, clase `Agente`),
  con las seis herramientas declaradas como `FunctionDeclaration` y un CLI para chatear
  (`make chat`, necesita `GEMINI_API_KEY` en `.env`). Persona: "Banco Río de la Plata", español
  rioplatense. Modelo por defecto `gemini-3.6-flash` (`gemini-2.5-flash` quedó deprecado para
  cuentas nuevas; el 404 real de la API el 2026-09-16 recomendó este reemplazo, confirmado en
  free tier — revisar aistudio.google.com si aparece uno más nuevo).
- Con esto, la **semana 1 queda cerrada** (esqueleto, autorización, backend, agente en modo
  texto). 61 pruebas no-`en_vivo` pasando más las 2 `en_vivo` de `prueba_bucle_en_vivo.py`, ya
  corridas con éxito contra Gemini real (2026-09-16). Cambio de modelo mergeado en
  [PR #1](https://github.com/felaa01/agente-bancario-voz/pull/1).

- **Semana 2, RAG de políticas: completo y validado de punta a punta.** Tabla
  `politicas` en pgvector (embedding vector(384) + columna generada `tsvector` en configuración
  `spanish`, índices HNSW y GIN). Embeddings con `multilingual-e5-small` corridos con `fastembed`
  (ONNX Runtime, sin PyTorch): el modelo no viene soportado nativamente en fastembed, así que se
  registra a mano contra la conversión ONNX cuantizada (int8) de la comunidad en
  `Xenova/multilingual-e5-small` (`rag/incrustaciones.py`). Búsqueda híbrida (texto completo +
  vectorial) combinada con Reciprocal Rank Fusion en `rag/repositorio.py`. `rag/cargador.py`
  (`make cargar-politicas`) lee los `.md` de `datos/politicas/`, los divide por párrafo y los
  carga. `buscar_politicas` ya usa esto de verdad (antes era un stub que siempre decía que no
  tenía la base conectada); si no hay pool o no aparece nada relevante, lo sigue diciendo en vez
  de inventar. Pico de RAM medido del modelo de embeddings: ~505 MB de proceso completo (ver
  README, sección de presupuesto de recursos).
  - Los 17 documentos de `datos/politicas/` los redactó una IA externa (no Claude) a partir de un
    prompt armado con el contexto del banco ficticio y la restricción de chunking por párrafo
    autocontenido. Revisados a mano: consistencia numérica entre archivos (60 días de plazo de
    disputa, costos de reposición), formato, y cobertura de casos "trampa" (inversiones, préstamos,
    apertura de cuentas) para que el agente diga que no sabe en vez de inventar. Se encontró y
    corrigió una inconsistencia real antes de cargar: tres archivos hablaban de "saldo disponible"
    vs. "saldo contable", pero el esquema real (`cuentas`) y `consultar_saldo` solo manejan un
    único campo `saldo`; se simplificó la política a un solo "saldo" para no prometer una
    distinción que el backend no puede dar.
  - Validado con el agente real (`make chat`, 2026-09-17) con 4 preguntas que cubren los casos
    típicos y las trampas: plazo de disputa, un pedido de consejo de inversión (debe derivar sin
    opinar), una pregunta fuera de alcance (debe reconocer que no tiene con qué responder en vez
    de forzar una respuesta con los fragmentos más cercanos que le trajo la búsqueda vectorial,
    que no tiene umbral de relevancia) y reposición de tarjeta combinando dos políticas (plazos +
    costo en dólares). Las 4 respuestas quedaron bien respaldadas en los documentos, sin
    inventar nada.
  - **Bug de robustez encontrado y arreglado durante esa validación:** `Agente.enviar()` en
    `bucle.py` no tenía reintentos propios alrededor de `self._chat.send_message`; a diferencia de
    `ejecutar_intenciones.py`, un 429 o un 5xx transitorio de Gemini (pasó en vivo: dos 503
    seguidos por sobrecarga del lado de Google) tiraba abajo `make chat` entero, perdiendo sesión e
    historial. Fix: helper `_enviar_con_reintentos` con backoff exponencial (mismo criterio que la
    evaluación de intención: reintenta 429/500/502/503/504, no reintenta el resto), envolviendo
    las dos llamadas a `send_message` del loop. 3 pruebas nuevas con un doble de prueba
    (`_ChatFalso`, sin red real).
- Agregada una séptima herramienta, `consultar_saldo` (con `@requiere_verificacion`, usa
  `ClienteBanco.obtener_cuentas` que ya traía el saldo, sin tocar el backend). Surgió al preparar
  la evaluación de intención con MInDS-14: "balance" es el intent más frecuente del dataset y no
  teníamos ninguna herramienta que lo resolviera.
- **Bug real encontrado y arreglado en `agente/bucle.py`:** `google.genai.Client.__del__` cierra
  el cliente HTTP interno cuando el objeto se recolecta como basura. `Agente.__init__` guardaba
  `self._chat` pero no una referencia al `Client` en sí, así que se recolectaba apenas terminaba
  el constructor y rompía la conversación en la segunda llamada (`send_message` con el resultado
  de una herramienta) en adelante. Ninguna prueba en vivo anterior lo agarraba porque ninguna
  completaba una llamada real a herramienta de punta a punta. Fix: `self._cliente = genai.Client(...)`.
  Prueba de regresión: `prueba_el_agente_completa_una_llamada_a_herramienta_de_punta_a_punta`.
- **Evaluación de intención (nivel 1) con MInDS-14 `es-ES`** (`src/agente_voz/evaluaciones/`):
  - `dataset_intenciones.py` descarga (transcripción, intención) vía la API REST de
    `datasets-server` de HuggingFace en vez de la librería `datasets` (evita pyarrow y compañía
    solo para leer texto). Cacheado en `evaluaciones/intenciones/minds14_es.json` (486 filas).
  - `mapeo_intenciones.py`: mapeo a mano de las 14 intenciones a las siete herramientas o a
    `fuera_de_alcance` (revisado contra ejemplos reales de cada clase, no una traducción literal).
  - **Hallazgo importante:** el free tier de `gemini-3.6-flash` da **20 llamadas por día**, no por
    minuto (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). Evaluar las 486 filas completas
    hubiera tomado ~25 días. Decisión: muestra estratificada de 3 ejemplos por intención (42 en
    total, `muestrear_estratificado`, semilla fija) en `evaluaciones/intenciones/muestra_es.json`,
    consistente con que esto es un proyecto de portfolio, no busca cobertura exhaustiva.
  - Marcar `Sesion.verificada` a mano no alcanza para que el modelo llame a las herramientas que
    requieren verificación: el modelo no ve el estado interno de la sesión, solo la conversación.
    Se sembró el historial del chat con un intercambio sintético de `verificar_identidad` ya
    resuelto (`construir_historial_verificado` en `bucle.py`), sin gastar una llamada real en
    repetir la verificación en cada uno de los 42 ejemplos.
  - `ejecutar_intenciones.py` (`make evaluar-intenciones`): reanudable (guarda resultados en JSONL
    a medida que corre), reintentos con backoff exponencial para 429/5xx transitorios, y corte
    limpio (sin traceback) si la cuota diaria se agota, conservando lo ya procesado.
  - Caveat documentado: `bloquear_tarjeta` (intención `freeze`) requiere `ultimos_4_digitos`, que
    las transcripciones nunca mencionan. El agente correctamente pide ese dato en texto en vez de
    llamar a la herramienta sin él, lo que hace bajar la métrica cruda para esa categoría sin que
    sea un error real de intención.

Próximo paso inmediato:
- Correr `make evaluar-intenciones` día a día (20 llamadas de cuota por día) hasta completar los
  42 ejemplos de la muestra, y volcar los resultados en la tabla de evaluación del README.

Después de eso, sigue el resto de la semana 2: cliente simulado con los primeros escenarios y un
subconjunto de evaluación corriendo en el CI — ver docs/plan-del-proyecto.md.

Actualizá esta sección cada vez que se complete un hito.
