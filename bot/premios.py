"""Las categorias y sus nominados, leidos de `premios.json`.

**Van en un fichero y no en una hoja de calculo** porque se cambian una
vez al año: cuando salgan los nominados de la edicion siguiente se
sustituye el fichero entero. Mientras tanto nadie los toca.

El orden del fichero es el orden en que se vota, asi que ahi se decide
por donde empieza la gente. Las mas golosas primero hace que quien
abandone a la mitad haya votado al menos lo que importa.

**La clave de cada categoria es su numero de orden**, no su nombre: el
nombre se puede corregir --una tilde, un acortado-- sin que los votos ya
dados dejen de contar. Reordenar el fichero a mitad de votacion si los
mezclaria, y por eso no se hace.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FICHERO = Path(__file__).resolve().parents[1] / "premios.json"


def _cargar() -> list[dict]:
    try:
        datos = json.loads(FICHERO.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"No se pudo leer {FICHERO.name}: {type(e).__name__}: {e}")
        return []
    categorias = datos.get("categorias") or []
    return [c for c in categorias if c.get("nombre") and c.get("nominados")]


CATEGORIAS = _cargar()


def cuantas() -> int:
    return len(CATEGORIAS)


def categoria(indice: int) -> dict | None:
    """La categoria numero `indice`, contando desde cero."""
    if 0 <= indice < len(CATEGORIAS):
        return CATEGORIAS[indice]
    return None


def nombre_de(indice: int) -> str:
    cat = categoria(indice)
    return cat["nombre"] if cat else "?"


def nominado(indice: int, cual: int) -> str | None:
    """El nominado `cual` de esa categoria. None si no existe.

    Se comprueba porque lo que llega de un boton puede ser de un mensaje
    viejo: si el fichero cambio, ese numero ya no apunta a lo mismo.
    """
    cat = categoria(indice)
    if cat is None:
        return None
    nominados = cat["nominados"]
    return nominados[cual] if 0 <= cual < len(nominados) else None


def lo_que_falta() -> list[str]:
    """Lo que impide votar, para decirlo al arrancar."""
    if not CATEGORIAS:
        return [f"{FICHERO.name} no trae ninguna categoria"]
    return []
