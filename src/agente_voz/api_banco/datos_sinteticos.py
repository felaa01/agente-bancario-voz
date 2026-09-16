from __future__ import annotations

import asyncio
import random
from decimal import Decimal

from faker import Faker

from agente_voz.api_banco.conexion import crear_pool

# Faker no tiene locale es_UY: es_AR (espanol rioplatense) es el mas cercano disponible.
_faker = Faker("es_AR")

CANTIDAD_CLIENTES = 20
TABLAS = "disputas, movimientos, tarjetas, cuentas, clientes"


def _generar_cedula() -> str:
    """Formato de cedula uruguaya (X.XXX.XXX-D). El digito verificador es aleatorio,
    no el algoritmo real: alcanza para datos de demo, no para validarlo de verdad.
    """
    numero = f"{random.randint(0, 9_999_999):07d}"
    digito_verificador = random.randint(0, 9)
    return f"{numero[0]}.{numero[1:4]}.{numero[4:]}-{digito_verificador}"


async def sembrar() -> None:
    pool = await crear_pool()
    async with pool.acquire() as conexion:
        await conexion.execute(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE")

        for _ in range(CANTIDAD_CLIENTES):
            cliente_id = await conexion.fetchval(
                """
                INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                _faker.name(),
                _generar_cedula(),
                _faker.date_of_birth(minimum_age=18, maximum_age=90),
                _faker.email(),
                _faker.phone_number(),
            )

            for _ in range(random.randint(1, 2)):
                moneda = random.choice(["UYU", "USD"])
                cuenta_id = await conexion.fetchval(
                    """
                    INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    cliente_id,
                    _faker.unique.numerify("###-######"),
                    moneda,
                    random.choice(["caja_ahorro", "cuenta_corriente"]),
                    Decimal(random.randrange(0, 500_000)) / 100,
                )

                await conexion.execute(
                    """
                    INSERT INTO tarjetas (cuenta_id, ultimos_4_digitos, tipo, vencimiento)
                    VALUES ($1, $2, $3, $4)
                    """,
                    cuenta_id,
                    f"{random.randint(0, 9999):04d}",
                    random.choice(["debito", "credito"]),
                    _faker.future_date(end_date="+5y"),
                )

                for _ in range(random.randint(3, 8)):
                    await conexion.execute(
                        """
                        INSERT INTO movimientos
                            (cuenta_id, monto, moneda, descripcion, comercio, tipo)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        cuenta_id,
                        Decimal(random.randrange(100, 50_000)) / 100,
                        moneda,
                        _faker.sentence(nb_words=4),
                        _faker.company(),
                        random.choice(["debito", "credito"]),
                    )

    await pool.close()
    print(f"Sembrados {CANTIDAD_CLIENTES} clientes con cuentas, tarjetas y movimientos.")


def main() -> None:
    asyncio.run(sembrar())


if __name__ == "__main__":
    main()
