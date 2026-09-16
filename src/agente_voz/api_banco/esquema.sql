-- Esquema del banco ficticio (Uruguay: cedula de identidad, cuentas en UYU y USD).
-- gen_random_uuid() es nativo de Postgres desde la version 13, no requiere extension.

CREATE TABLE clientes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_completo text NOT NULL,
    cedula text NOT NULL UNIQUE,
    fecha_nacimiento date NOT NULL,
    email text NOT NULL,
    telefono text NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cuentas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id uuid NOT NULL REFERENCES clientes (id),
    numero_cuenta text NOT NULL UNIQUE,
    moneda text NOT NULL CHECK (moneda IN ('UYU', 'USD')),
    tipo text NOT NULL CHECK (tipo IN ('caja_ahorro', 'cuenta_corriente')),
    saldo numeric(14, 2) NOT NULL DEFAULT 0,
    creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_cuentas_cliente_id ON cuentas (cliente_id);

-- Solo se guardan los ultimos 4 digitos: ninguna herramienta necesita el numero completo,
-- y asi la base ni siquiera puede filtrarlo (minimizacion de datos).
CREATE TABLE tarjetas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_id uuid NOT NULL REFERENCES cuentas (id),
    ultimos_4_digitos char(4) NOT NULL,
    tipo text NOT NULL CHECK (tipo IN ('debito', 'credito')),
    estado text NOT NULL CHECK (estado IN ('activa', 'bloqueada')) DEFAULT 'activa',
    vencimiento date NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tarjetas_cuenta_id ON tarjetas (cuenta_id);

CREATE TABLE movimientos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_id uuid NOT NULL REFERENCES cuentas (id),
    fecha timestamptz NOT NULL DEFAULT now(),
    monto numeric(14, 2) NOT NULL,
    moneda text NOT NULL CHECK (moneda IN ('UYU', 'USD')),
    descripcion text NOT NULL,
    comercio text NOT NULL,
    tipo text NOT NULL CHECK (tipo IN ('debito', 'credito'))
);

CREATE INDEX idx_movimientos_cuenta_id ON movimientos (cuenta_id);

-- movimiento_id es UNIQUE: es lo que permite que abrir_disputa sea idempotente
-- (un reintento hace un upsert que devuelve la disputa existente, no duplica).
CREATE TABLE disputas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    movimiento_id uuid NOT NULL UNIQUE REFERENCES movimientos (id),
    cliente_id uuid NOT NULL REFERENCES clientes (id),
    motivo text NOT NULL,
    estado text NOT NULL CHECK (estado IN ('abierta', 'en_revision', 'resuelta', 'rechazada'))
        DEFAULT 'abierta',
    creado_en timestamptz NOT NULL DEFAULT now(),
    resuelto_en timestamptz
);

CREATE INDEX idx_disputas_cliente_id ON disputas (cliente_id);

-- RAG de politicas: cada fila es un fragmento de un documento de datos/politicas/.
-- embedding usa multilingual-e5-small (384 dimensiones, ver rag/incrustaciones.py).
-- busqueda_texto es una columna generada: Postgres la recalcula sola a partir de contenido,
-- no hace falta mantenerla a mano al insertar o actualizar.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE politicas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    documento text NOT NULL,
    fragmento_indice int NOT NULL,
    contenido text NOT NULL,
    busqueda_texto tsvector GENERATED ALWAYS AS (to_tsvector('spanish', contenido)) STORED,
    embedding vector(384) NOT NULL,
    creado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (documento, fragmento_indice)
);

CREATE INDEX idx_politicas_busqueda_texto ON politicas USING gin (busqueda_texto);

-- HNSW en vez de IVFFlat: no necesita un paso previo de entrenamiento con datos ya
-- cargados, lo que conviene para una tabla chica (15-20 documentos) que se recarga seguido.
CREATE INDEX idx_politicas_embedding ON politicas USING hnsw (embedding vector_cosine_ops);
