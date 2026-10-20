"""Los votos guardados. PostgreSQL, con asyncpg.

**Una base y no una hoja de calculo**: votar las 21 categorias son 21
escrituras por persona, y el cupo de Google --300 por minuto-- lo
comparten los otros cuatro bots con la misma cuenta de servicio. Quince
personas votando a la vez se lo comen, y lo que se rompe entonces no es
la votacion: es Miss apuntando un aviso y el publicador escribiendo en
su cola, con un error que no dice de donde viene.
"""

import logging
from pathlib import Path

import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(__name__)

MIGRACIONES = Path(__file__).resolve().parents[1] / "db" / "migraciones"

_pozo: asyncpg.Pool | None = None


def pozo() -> asyncpg.Pool:
    if _pozo is None:
        raise RuntimeError("la base no esta abierta")
    return _pozo


async def abrir() -> None:
    """Abre la base y aplica lo que falte. Se llama una vez, al arrancar."""
    global _pozo
    _pozo = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pozo.acquire() as con:
        await con.execute(
            "CREATE TABLE IF NOT EXISTS migraciones ("
            "  nombre TEXT PRIMARY KEY,"
            "  puesta TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        puestas = {f["nombre"] for f in
                   await con.fetch("SELECT nombre FROM migraciones")}
        for fichero in sorted(MIGRACIONES.glob("*.sql")):
            if fichero.name in puestas:
                continue
            logger.info(f"Aplicando {fichero.name}")
            await con.execute(fichero.read_text(encoding="utf-8"))
            await con.execute("INSERT INTO migraciones (nombre) VALUES ($1)",
                              fichero.name)


async def cerrar() -> None:
    if _pozo is not None:
        await _pozo.close()


async def guardar(usuario: int, alias: str | None, categoria: int,
                  nominado: str) -> None:
    """Deja el voto de esa persona en esa categoria.

    **Sustituye al anterior**, no suma otro: la clave de la tabla es el
    par persona + categoria. Eso es lo que permite cambiar el voto hasta
    que cierre sin que haya que borrar nada antes.
    """
    async with pozo().acquire() as con:
        await con.execute(
            "INSERT INTO votos (usuario_id, categoria, nominado, alias) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (usuario_id, categoria) DO UPDATE SET "
            "  nominado = EXCLUDED.nominado,"
            "  alias = EXCLUDED.alias,"
            "  votado_en = now()",
            usuario, categoria, nominado, alias,
        )


async def votos_de(usuario: int) -> dict[int, str]:
    """Lo que lleva votado esa persona: categoria -> nominado."""
    async with pozo().acquire() as con:
        filas = await con.fetch(
            "SELECT categoria, nominado FROM votos WHERE usuario_id = $1",
            usuario,
        )
    return {f["categoria"]: f["nominado"] for f in filas}


async def recuento() -> dict[int, list[tuple[str, int]]]:
    """Lo votado en cada categoria, de mas a menos.

    A igualdad, por nombre: **dos empatados tienen que salir siempre en
    el mismo orden**, que si no el recuento baila entre una consulta y la
    siguiente sin que nadie haya votado nada.
    """
    async with pozo().acquire() as con:
        filas = await con.fetch(
            "SELECT categoria, nominado, count(*) AS votos FROM votos "
            "GROUP BY categoria, nominado "
            "ORDER BY categoria, votos DESC, nominado"
        )
    salida: dict[int, list[tuple[str, int]]] = {}
    for f in filas:
        salida.setdefault(f["categoria"], []).append((f["nominado"], f["votos"]))
    return salida


async def cuanta_gente() -> int:
    """Cuantas personas distintas han votado algo."""
    async with pozo().acquire() as con:
        return await con.fetchval(
            "SELECT count(DISTINCT usuario_id) FROM votos") or 0
