"""El recuento, y el cierre.

Dos cosas, y las dos solo para Edu:

  - `/recuento` dice como va en cualquier momento. **Solo a el y solo en
    privado**: enseñar el marcador a mitad de votacion arrastra el voto,
    que la gente vota a lo que va ganando.
  - Al cerrar, el bot le manda el resultado y le ofrece publicarlo donde
    quiera con un boton. No se publica solo a proposito: el resultado se
    lee antes de salir, por si hay que contar algo o corregir algo.

**Las categorias «nuestras» las elige Edu**, asi que el bot no las vota
ni las cuenta: se escriben en el mensaje al publicarlo.
"""

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot import banco, premios
from bot.reloj import sello
from bot.votacion import cerrada
from config import ADMIN_ID, PUBLICAR_EN

logger = logging.getLogger(__name__)

MEDALLAS = ["🥇", "🥈", "🥉"]

# Cuantos se enseñan de cada categoria en el mensaje publicado. El resto
# queda en el recuento de Edu: un mensaje con los 168 no lo lee nadie.
CUANTOS_SE_PUBLICAN = 3


def _es_edu(update: Update) -> bool:
    quien = update.effective_user
    return bool(ADMIN_ID) and quien is not None and quien.id == ADMIN_ID


async def _texto_del_recuento(completo: bool) -> str:
    cuentas = await banco.recuento()
    gente = await banco.cuanta_gente()
    lineas = [f"🗳 <b>Recuento</b> · {sello()}",
              f"<i>{gente} personas han votado</i>", ""]
    for indice in range(premios.cuantas()):
        lineas.append(f"<b>{premios.nombre_de(indice)}</b>")
        reparto = cuentas.get(indice) or []
        if not reparto:
            lineas.append("  <i>sin votos</i>")
        for puesto, (nominado, votos) in enumerate(reparto, 1):
            if not completo and puesto > CUANTOS_SE_PUBLICAN:
                break
            marca = MEDALLAS[puesto - 1] if puesto <= 3 else f"{puesto}."
            lineas.append(f"  {marca} {nominado} — <b>{votos}</b>")
        lineas.append("")
    return "\n".join(lineas)


def _teclado_publicar() -> InlineKeyboardMarkup | None:
    """Un boton por sitio donde se puede publicar. None si no hay ninguno."""
    if not PUBLICAR_EN:
        return None
    filas = [[InlineKeyboardButton(f"Publicar en {donde}",
                                   callback_data=f"pub:{numero}")]
             for numero, donde in enumerate(PUBLICAR_EN)]
    return InlineKeyboardMarkup(filas)


async def recuento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/recuento`. Solo Edu, y en privado."""
    if not _es_edu(update):
        return
    texto = await _texto_del_recuento(completo=True)
    # Telegram corta en 4096: si no cabe, se parte por categorias.
    for trozo in _en_trozos(texto):
        await update.effective_message.reply_text(
            trozo, parse_mode=ParseMode.HTML)


def _en_trozos(texto: str, tope: int = 3500) -> list[str]:
    """Parte por lineas, sin cortar una categoria por la mitad."""
    trozos, actual = [], ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 > tope:
            trozos.append(actual)
            actual = ""
        actual += linea + "\n"
    if actual.strip():
        trozos.append(actual)
    return trozos


async def avisar_del_cierre(bot: Bot) -> None:
    """Se llama cuando llega la fecha. Le manda el resultado a Edu."""
    if not ADMIN_ID:
        logger.warning("La votacion ha cerrado y no hay ADMIN_ID a quien "
                       "contarselo")
        return
    cabecera = ("🔒 <b>La votación ha cerrado.</b>\n"
                "Esto es lo que ha salido. Si quieres publicarlo, dale al "
                "botón; si no, aquí se queda.\n\n")
    texto = cabecera + await _texto_del_recuento(completo=False)
    trozos = _en_trozos(texto)
    for numero, trozo in enumerate(trozos):
        ultimo = numero == len(trozos) - 1
        await bot.send_message(
            ADMIN_ID, trozo, parse_mode=ParseMode.HTML,
            reply_markup=_teclado_publicar() if ultimo else None)


async def publicar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """El boton de publicar el resultado."""
    consulta = update.callback_query
    if not _es_edu(update):
        await consulta.answer()
        return
    try:
        cual = int((consulta.data or "pub:").split(":")[1])
        donde = PUBLICAR_EN[cual]
    except (ValueError, IndexError):
        await consulta.answer("Ese sitio ya no está puesto.", show_alert=True)
        return

    texto = await _texto_del_recuento(completo=False)
    try:
        for trozo in _en_trozos(texto):
            await context.bot.send_message(donde, trozo,
                                           parse_mode=ParseMode.HTML)
    except Exception as e:
        await consulta.answer(f"No pude: {type(e).__name__}", show_alert=True)
        logger.warning(f"No se pudo publicar en {donde}: "
                       f"{type(e).__name__}: {e}")
        return
    await consulta.answer("Publicado")
    await consulta.edit_message_reply_markup(reply_markup=None)


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/estado`: si esta abierta y cuanta gente ha votado. Solo Edu."""
    if not _es_edu(update):
        return
    gente = await banco.cuanta_gente()
    await update.effective_message.reply_text(
        ("🔒 Cerrada." if cerrada() else "🟢 Abierta.")
        + f"\n{gente} personas han votado.\n"
        f"{premios.cuantas()} categorías.")
