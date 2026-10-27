"""Los aciertos: un punto por cada categoria clavada.

Clavada quiere decir que lo votado en nuestra votacion es lo mismo que
gano de verdad en los Golden Joystick. Los ganadores de verdad no los
vota nadie: se apuntan en la tabla `ganadores` con
`herramientas/ganadores.py`, que los coge del propio `premios.json` para
que el texto sea **exactamente** el que tienen los votos.

Dos comandos:

  - `/puntos`, en privado, le dice a cada uno lo suyo: cuantas acerto y
    en que se equivoco. **Solo en privado**, y no por secreto: son
    veintidos lineas sobre una sola persona y en el grupo eso es ruido.
  - `/clasificacion` es para todos y sale donde se pida.

**Las dos cosas estan cerradas hasta que haya ganadores en la base.** La
puerta es esa y no una fecha: si no se sabe quien gano, un cero no
significa «fallaste todas», significa «todavia no». Y una fecha seria un
segundo sitio donde guardar lo mismo, que es un sitio donde equivocarse.

Una categoria sin ganador apuntado **no cuenta como fallo**: durante la
gala se van sabiendo de una en una, y hasta que se sepa la ultima el
marcador es parcial a proposito.
"""

import logging

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from bot import banco, premios
from bot.recuento import en_trozos
from bot.reloj import sello
from config import ADMIN_ID

logger = logging.getLogger(__name__)

MEDALLAS = ["🥇", "🥈", "🥉"]

# Cuantos salen en la clasificacion publica. Edu la ve entera: el resto
# no necesita bajar doscientas lineas para ver que va el decimocuarto.
CUANTOS_SE_VEN = 20

TODAVIA_NO = ("🏆 Ganador no seleccionado.\n\nLos ganadores de cada categoría "
              "se sabrán cuando se entreguen los Golden Joystick Awards.")

# Como se llama a quien voto sin tener alias de Telegram. Sale en la
# clasificacion y en la pestaña del Sheet, y **se escribe una sola vez**:
# con dos copias, el dia que se cambie una la tabla y el documento dejan
# de llamar igual a la misma persona.
SIN_NOMBRE = "Alguien sin @"


def _es_edu(update: Update) -> bool:
    quien = update.effective_user
    return bool(ADMIN_ID) and quien is not None and quien.id == ADMIN_ID


def _nombre(alias: str | None) -> str:
    """Como se le llama en la tabla a quien no dejo nombre."""
    return (alias or "").strip() or SIN_NOMBRE


def _texto_de_los_mios(aciertos: list[tuple[int, str, str | None]],
                       cuantas_resueltas: int) -> str:
    """Lo que ha acertado una persona, categoria por categoria."""
    if not aciertos:
        return ("🎯 No tengo ningún voto tuyo.\n\n"
                "Si votaste con otra cuenta, los aciertos están en esa.")

    clavadas = sum(1 for _, voto, ganador in aciertos if ganador == voto)
    cuantas = ("1 categoría ya resuelta" if cuantas_resueltas == 1
               else f"{cuantas_resueltas} categorías ya resueltas")
    lineas = [f"🎯 <b>Tus aciertos: {clavadas}</b>",
              f"<i>de {cuantas}</i>", ""]
    # **Las que faltan van juntas en una linea al final**, no una cada
    # una: a mitad de gala hay tres resueltas y diecinueve por resolver,
    # y diecinueve lineas diciendo «todavia no» tapan las tres que
    # importan.
    sin_resolver = 0
    for indice, voto, ganador in aciertos:
        nombre = premios.nombre_de(indice)
        if ganador is None:
            sin_resolver += 1
        elif ganador == voto:
            lineas.append(f"✅ <b>{nombre}</b>\n   {voto}")
        else:
            lineas.append(f"❌ <b>{nombre}</b>\n"
                          f"   tú: {voto}\n   ganó: {ganador}")
    if sin_resolver:
        lineas.append(f"\n⏳ <i>Te quedan {sin_resolver} categorías por "
                      f"resolver.</i>" if sin_resolver > 1 else
                      "\n⏳ <i>Te queda 1 categoría por resolver.</i>")
    return "\n".join(lineas)


def _texto_de_la_tabla(tabla: list[tuple[int, str | None, int]],
                       cuantas_resueltas: int, completo: bool) -> str:
    """La clasificacion. `completo` solo para Edu."""
    lineas = [f"🏆 <b>Clasificación</b> · {sello()}",
              f"<i>{cuantas_resueltas} de {premios.cuantas()} categorías "
              f"resueltas</i>", ""]
    for puesto, (_, alias, cuantos) in enumerate(tabla, 1):
        if not completo and puesto > CUANTOS_SE_VEN:
            lineas.append(f"<i>y {len(tabla) - CUANTOS_SE_VEN} más</i>")
            break
        marca = MEDALLAS[puesto - 1] if puesto <= 3 else f"{puesto}."
        lineas.append(f"{marca} {_nombre(alias)} — <b>{cuantos}</b>")
    return "\n".join(lineas)


async def puntos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/puntos`: lo que ha acertado quien lo pide. Solo en privado."""
    mensaje = update.effective_message
    charla = update.effective_chat
    if charla is not None and charla.type != ChatType.PRIVATE:
        await mensaje.reply_text("Escríbeme en privado y lo vemos.")
        return

    ganadores = await banco.ganadores()
    if not ganadores:
        await mensaje.reply_text(TODAVIA_NO)
        return

    quien = update.effective_user
    mios = await banco.aciertos_de(quien.id)
    for trozo in en_trozos(_texto_de_los_mios(mios, len(ganadores))):
        await mensaje.reply_text(trozo, parse_mode=ParseMode.HTML)


async def clasificacion(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/clasificacion`: quien lleva mas aciertos. Para todos."""
    mensaje = update.effective_message
    ganadores = await banco.ganadores()
    if not ganadores:
        await mensaje.reply_text(TODAVIA_NO)
        return

    tabla = await banco.clasificacion()
    texto = _texto_de_la_tabla(tabla, len(ganadores), completo=_es_edu(update))
    for trozo in en_trozos(texto):
        await mensaje.reply_text(trozo, parse_mode=ParseMode.HTML)
