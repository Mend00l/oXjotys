"""Quien puede votar: los que estan en alguno de los grupos de Edu.

Se le pregunta a Telegram con `get_chat_member`, que contesta en que
estado esta esa persona en ese grupo. **Para poder preguntarlo, el bot
tiene que estar metido en el grupo** --y en un canal, ademas, como
administrador--.

Lo que esto consigue y lo que no:

  - **Sube mucho el coste de hacer trampas.** Para votar mil veces hay
    que meter mil cuentas en el grupo, y eso se ve.
  - **No lo hace imposible**: quien tenga tres cuentas vota tres veces.
    Eso no lo arregla nadie, tampoco los premios de verdad.
  - Quien quiera votar y no este, se une. La votacion trae gente.

**Se comprueba al votar, no al contar.** Quien vote y luego se vaya del
grupo conserva su voto: quitarselo despues seria cambiar un resultado ya
dado por una cosa que paso fuera de la votacion.
"""

import logging
import time

from telegram import Bot

from config import ADMIN_ID, GRUPOS, MINUTOS_DE_MEMORIA

logger = logging.getLogger(__name__)

# Los estados que cuentan como estar dentro. `restricted` entra a
# proposito: a alguien silenciado en el grupo se le puede haber callado
# por hablar de mas, y eso no quita el derecho a votar. `left` y
# `kicked` quedan fuera, que es lo que significan.
DENTRO = {"creator", "administrator", "member", "restricted"}

# telegram_id -> (si pasa, cuando se pregunto)
_memoria: dict[int, tuple[bool, float]] = {}


def _reciente(usuario: int) -> bool | None:
    """Lo que se contesto hace poco, o None si toca volver a preguntar."""
    guardado = _memoria.get(usuario)
    if guardado is None:
        return None
    pasa, cuando = guardado
    if time.monotonic() - cuando > MINUTOS_DE_MEMORIA * 60:
        return None
    return pasa


def olvidar(usuario: int) -> None:
    """Para cuando alguien acaba de unirse y no quiere esperar media hora."""
    _memoria.pop(usuario, None)


async def puede_votar(bot: Bot, usuario: int) -> bool:
    """Si esa persona esta en alguno de los grupos.

    **Basta con uno.** Se pregunta por orden y se corta en el primero que
    diga que si, que es lo normal: el de la comunidad.

    Un grupo que no conteste --el bot ya no esta dentro, el numero esta
    mal-- se salta y se deja dicho en el registro. Dar por buena a una
    persona porque Telegram no contesta seria abrir la votacion entera
    por un grupo mal escrito.
    """
    # **Edu vota siempre, sin mirar grupos.** Tiene que poder probar la
    # votacion entera en privado antes de meter el bot en la comunidad, y
    # para preguntar por alguien el bot tiene que estar YA dentro del
    # grupo: sin esto, probar obliga a abrirlo antes de tiempo. Es un solo
    # numero, asi que no deja entrar a nadie mas y no hay nada que
    # acordarse de quitar despues.
    if ADMIN_ID and usuario == ADMIN_ID:
        return True

    recordado = _reciente(usuario)
    if recordado is not None:
        return recordado

    pasa = False
    for grupo in GRUPOS:
        try:
            quien = await bot.get_chat_member(chat_id=grupo, user_id=usuario)
        except Exception as e:
            # Lo normal aqui es «user not found», que significa que no
            # esta: no es una averia y no se grita. Lo que si se cuenta es
            # cualquier otra cosa, porque suele ser el bot fuera del grupo.
            if "not found" not in str(e).lower():
                logger.warning(f"No pude preguntar por {usuario} en {grupo}: "
                               f"{type(e).__name__}: {e}")
            continue
        if quien.status in DENTRO:
            pasa = True
            break

    _memoria[usuario] = (pasa, time.monotonic())
    return pasa
