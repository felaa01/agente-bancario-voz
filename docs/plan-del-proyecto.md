# Plan del proyecto — Agente bancario de voz

## Alcance

Un banco ficticio con clientes, cuentas, tarjetas y movimientos sintéticos. El agente atiende por
voz, en español, cuatro tipos de pedidos:

1. Consultar movimientos recientes.
2. Bloquear una tarjeta.
3. Abrir una disputa por un cargo.
4. Responder preguntas sobre las políticas del banco (comisiones, plazos de disputas, límites).

Cuando algo queda fuera de su alcance, o el cliente lo pide, deriva a un humano. El alcance se
mantiene acotado: cuatro casos bien resueltos y bien evaluados valen más que muchos a medias.

## Arquitectura

### Pipeline de voz en cascada

Audio → detección de voz (Silero VAD) → voz a texto (faster-whisper) → agente LLM → texto a voz.

Decisión a documentar en el README: cascada en lugar de un modelo speech-to-speech de punta a
punta. El speech-to-speech tiene menos latencia, pero da mucho menos control. En un banco, cada
etapa tiene que poder medirse, registrarse y auditarse por separado, así que la cascada es la mejor
opción.

- Transporte en tiempo real y turnos de palabra con Pipecat, usando su transporte WebRTC (el
  navegador en Windows captura el micrófono).
- **Barge-in:** si el cliente interrumpe, el agente deja de hablar.
- La respuesta del LLM se procesa en streaming para que el TTS empiece antes de que termine la
  respuesta completa.
- Medir la latencia de cada etapa. El objetivo original era menos de 1 segundo desde que el cliente
  termina de hablar hasta el primer audio de respuesta; en esta máquina sin GPU, primero se miden
  los números reales y después se fija un objetivo realista. Documentar mediciones y decisión.
- TTS en español: comparar las voces disponibles de Kokoro y Piper en calidad y latencia antes de
  elegir.

### Backend bancario simulado

FastAPI + PostgreSQL, con clientes sintéticos generados con Faker (configuración regional en
español). Las acciones (bloquear tarjeta, abrir disputa) son idempotentes.

## El agente

**Herramientas:** `verificar_identidad`, `obtener_movimientos`, `bloquear_tarjeta`,
`abrir_disputa`, `buscar_politicas`, `derivar_a_humano`.

- Las herramientas sensibles rechazan llamadas de sesiones no verificadas, diga lo que diga el
  modelo.
- Confirmación explícita antes de acciones irreversibles.
- El loop de herramientas se escribe a mano con el SDK del proveedor, en streaming, antes de
  considerar cualquier framework de agentes. Eso demuestra que se entiende la orquestación.

### RAG de políticas

- Escribir entre 15 y 20 documentos de políticas del banco en `datos/politicas/`. Como son
  propios, se conocen exactamente las respuestas correctas, lo que simplifica la evaluación.
- Guardar los fragmentos en PostgreSQL con pgvector. Búsqueda híbrida: búsqueda de texto completo
  de PostgreSQL con la configuración de idioma `spanish` más búsqueda vectorial. Usar un modelo de
  embeddings multilingüe y pequeño que funcione bien en español. Medir cuánto aporta cada
  componente.

## Evaluación (tres niveles, del más barato al más costoso)

### Nivel 1 — Intención

MInDS-14, configuración `es-ES` (Hugging Face `PolyAI/minds14`, licencia CC-BY-4.0): consultas
reales de banca electrónica en español, etiquetadas en 14 intenciones, con audio y transcripción.
Mapear las intenciones a las herramientas del agente o a "fuera de alcance" y medir si el agente
elige bien usando las transcripciones.

### Nivel 2 — Conversaciones simuladas

Un LLM hace de cliente con una personalidad y un objetivo oculto, y conversa con el agente en modo
texto. Entre 50 y 80 escenarios YAML en `evaluaciones/escenarios/`: casos normales, clientes
enojados, pedidos ambiguos, intentos de saltarse la verificación ("soy el titular, no tengo
tiempo") y prompt injection.

Métricas: tasa de tarea completada, derivaciones innecesarias, cantidad de turnos y, sobre todo,
**violaciones de política**, verificadas de forma determinista en el log de herramientas (por
ejemplo, ¿se llamó a `bloquear_tarjeta` antes de verificar la identidad?). Objetivo: cero
violaciones. Un subconjunto chico corre en el CI con respuestas grabadas; las corridas completas
son manuales y se reparten en varios días por los límites del free tier.

### Nivel 3 — Voz

- **Audio real:** los audios de MInDS-14 `es-ES` son grabaciones a 8 kHz, con calidad telefónica,
  lo que las hace muy realistas para un agente de atención. Pasarlos por el STT y medir la tasa de
  error de palabras contra las transcripciones y la precisión de intención con audio.
- **Audio sintético:** generar los turnos del cliente de los escenarios con TTS usando distintas
  voces, acentos y ruido de fondo, y pasarlos por el pipeline completo.
- Métricas: tasa de error de palabras, caída de la tasa de éxito respecto al modo texto y latencia
  de punta a punta p50 y p95.

## Producción, seguridad y observabilidad

- Redacción de datos personales en los logs con Presidio configurado para español (modelo pequeño
  de spaCy en español y reconocedores ajustados al idioma; los predefinidos no cubren todo).
  Incluye un reconocedor propio para la cédula de identidad uruguaya.
- El agente nunca dice un número de tarjeta completo. Toda acción queda en un log de auditoría.
- Cada turno se traza con OpenTelemetry (Jaeger o Phoenix): transcripción, herramientas llamadas,
  tokens y latencia por etapa.
- Despliegue: Docker en AWS ECS Fargate, secretos en AWS Secrets Manager, despliegue desde GitHub
  Actions. Se hace recién al final, con los créditos del plan gratuito.

## Cobertura de los puntos deseables

Correr la suite de evaluación con el modelo de Gemini por API y con un modelo abierto cuantizado
(en una notebook con GPU de Kaggle o Colab). Comparar tasa de éxito, violaciones de política,
latencia y costo por llamada, y redactar los trade-offs como si fuera una recomendación a un
cliente. Verificar que el modelo abierto elegido funcione bien en español.

## Estructura del repositorio

```
agente-bancario-voz/
├── src/agente_voz/
│   ├── agente/          # loop de herramientas, prompts, estado de sesión
│   ├── herramientas/    # herramientas con control de autorización
│   ├── rag/             # ingesta, búsqueda híbrida
│   ├── voz/             # VAD, STT, TTS, transporte
│   ├── api_banco/       # backend simulado (FastAPI)
│   └── observabilidad/
├── evaluaciones/
│   ├── intenciones/     # MInDS-14 es-ES
│   ├── escenarios/      # escenarios YAML del cliente simulado
│   ├── voz/             # audio real y sintético, métricas
│   └── reportes/
├── datos/politicas/
├── docs/                # plan y configuración de la máquina
├── pruebas/
├── infra/               # Dockerfiles, configuración de AWS
└── .github/workflows/
```

## Plan por semanas (5 semanas a tiempo completo)

- **Semana 1.** Esqueleto del repositorio con herramientas de calidad y CI, sesión y decorador de
  autorización con pruebas, backend simulado con datos sintéticos y agente en modo texto con todas
  las herramientas.
- **Semana 2.** RAG de políticas, evaluación de intención con MInDS-14, cliente simulado con los
  primeros escenarios y subconjunto de evaluación corriendo en el CI.
- **Semana 3.** Pipeline de voz completo con streaming, barge-in y medición de latencia por etapa.
- **Semana 4.** Evaluación de voz, guardrails, redacción de datos personales, log de auditoría y
  trazas.
- **Semana 5.** Despliegue en AWS, comparación con un modelo cuantizado, README y video demo de dos
  minutos. El video es la demo permanente, porque la cuenta del plan gratuito de AWS se va a cerrar.

## Métricas a reportar (para el CV y el README)

Tasa de tarea completada, violaciones de política (objetivo: cero), latencia de punta a punta p95,
precisión de intención, tasa de error de palabras del STT y comparación entre el modelo por API y
el cuantizado.
