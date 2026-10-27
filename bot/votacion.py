"""La votacion: una categoria cada vez, en privado y a botonazos.

**Se guarda al tocar, no al final.** Son veintidos categorias: quien lo
deje a medias tiene que poder volver y seguir donde estaba, y quien se
equivoque tiene que poder cambiarlo. Las dos cosas salen de lo mismo,
que cada toque escriba ya.

**Se pagina de ocho en ocho.** La mayoria de categorias tienen seis
nominados, asi que casi todas caben en una pantalla; las de diez se
quedan en dos y la de veinte en tres. Con cinco por pagina eran cuarenta
y seis pantallas para votar entero.

Lo que viaja en cada boton va apretado a proposito --Telegram solo
admite 64 caracteres ahi dentro--:

    v:3:0:5   votar el nominado 5 de la categoria 3, estando en la pagina 0
    p:3:1     ir a la pagina 1 de la categoria 3
    s:3       saltarse la categoria 3
    r         ver lo que llevo votado
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot import banco, premios, socios
from config import CIERRA_EL, ENLACE_DEL_GRUPO, POR_PAGINA
from bot.reloj import ahora

logger = logging.getLogger(__name__)

MARCA = "✅"

# Lo que se lee al terminar de votar. **Es de Edu, palabra por palabra**:
# lo del ganador es lo que mas preguntan y asi queda contestado sin que
# nadie tenga que preguntarlo.
DESPEDIDA = ("🏆 <b>¡Gracias por participar en los oXJOTYs!</b>\n"
             "Diremos el ganador tras el recuento de votos de los "
             "Golden Joystick Awards.")


def cerrada() -> bool:
    return CIERRA_EL is not None and ahora() >= CIERRA_EL


# Cuantas categorias se enseñan de golpe al ir a cambiar un voto. Menos
# que nominados a proposito: sus nombres son largos y la lista es para
# buscar una concreta, no para elegir entre todas.
CATEGORIAS_POR_PAGINA = 5


def _paginas(cuantos: int, por_pagina: int = POR_PAGINA) -> int:
    return max(1, -(-cuantos // por_pagina))


def _teclado(indice: int, pagina: int, votado: str | None) -> InlineKeyboardMarkup:
    cat = premios.categoria(indice)
    nominados = cat["nominados"]
    total = _paginas(len(nominados))
    pagina = max(0, min(pagina, total - 1))
    desde = pagina * POR_PAGINA

    filas = []
    for numero in range(desde, min(desde + POR_PAGINA, len(nominados))):
        texto = nominados[numero]
        if votado == texto:
            texto = f"{MARCA} {texto}"
        filas.append([InlineKeyboardButton(
            texto[:60], callback_data=f"v:{indice}:{pagina}:{numero}")])

    if total > 1:
        paso = []
        if pagina > 0:
            paso.append(InlineKeyboardButton(
                "‹", callback_data=f"p:{indice}:{pagina - 1}"))
        paso.append(InlineKeyboardButton(
            f"{pagina + 1}/{total}", callback_data="nada"))
        if pagina < total - 1:
            paso.append(InlineKeyboardButton(
                "›", callback_data=f"p:{indice}:{pagina + 1}"))
        filas.append(paso)

    ultima = []
    if indice + 1 < premios.cuantas():
        ultima.append(InlineKeyboardButton(
            "Saltar ⏭", callback_data=f"s:{indice}"))
    ultima.append(InlineKeyboardButton("Mis votos", callback_data="r"))
    filas.append(ultima)

    return InlineKeyboardMarkup(filas)


def _texto(indice: int, votado: str | None) -> str:
    cabecera = (f"🏆 <b>{premios.nombre_de(indice)}</b>\n"
                f"<i>{indice + 1} de {premios.cuantas()}</i>\n\n")
    if votado:
        return cabecera + f"Votaste <b>{votado}</b>. Puedes cambiarlo."
    return cabecera + "Toca el que quieras. Podrás cambiarlo hasta que cierre."


async def _siguiente_sin_votar(usuario: int, desde: int) -> int | None:
    """La primera categoria sin votar a partir de `desde`, dando la vuelta.

    **Dando la vuelta a proposito**: quien empieza, se cansa y vuelve
    dias despues retoma por lo que le falta y no por donde lo dejo, que
    es lo que acaba en votaciones a medias para siempre.
    """
    puestos = await banco.votos_de(usuario)
    total = premios.cuantas()
    for salto in range(total):
        cual = (desde + salto) % total
        if cual not in puestos:
            return cual
    return None


def _texto_resumen(puestos: dict[int, str]) -> str:
    total = premios.cuantas()
    lineas = [f"🗳 <b>Llevas {len(puestos)} de {total}</b>", ""]
    for indice in range(total):
        nombre = premios.nombre_de(indice)
        elegido = puestos.get(indice)
        lineas.append(f"{MARCA} <b>{nombre}</b>: {elegido}" if elegido
                      else f"▫️ {nombre}")
    if len(puestos) < total:
        lineas += ["", "Toca «Seguir votando» para las que faltan."]
    else:
        lineas += ["", DESPEDIDA, "",
                   "Las tienes todas. Puedes cambiar lo que quieras "
                   "hasta que cierre."]
    return "\n".join(lineas)


def _teclado_resumen(puestos: dict[int, str]) -> InlineKeyboardMarkup:
    """Los botones del resumen: seguir, y cambiar lo ya votado.

    **Antes el resumen era solo texto** y «Seguir votando» no llevaba a
    ningun sitio cuando ya estaban todas: el mensaje decia que se podia
    cambiar el voto hasta el cierre y no habia por donde.

    Las categorias **no** se ponen aqui una a una: serian veintitres
    botones de golpe, un muro. Van detras de «¿Quieres cambiar tu voto?»
    y paginadas, como los nominados.
    """
    filas = []
    if len(puestos) < premios.cuantas():
        filas.append([InlineKeyboardButton("Seguir votando",
                                           callback_data="seguir")])
    if puestos:
        filas.append([InlineKeyboardButton("✏️ ¿Quieres cambiar tu voto?",
                                           callback_data="cam:0")])
    return InlineKeyboardMarkup(filas)


def _teclado_cambiar(puestos: dict[int, str], pagina: int) -> InlineKeyboardMarkup:
    """Las categorias, de cinco en cinco, para volver a cualquiera.

    Misma forma que la de los nominados --‹ 1/5 ›-- para que se maneje
    igual. Una por fila: con dos columnas, «Seguimos jugando · PC y
    consola» se queda en «Seguimos jug...» y hay que adivinar cual es.
    """
    total_cat = premios.cuantas()
    paginas = _paginas(total_cat, CATEGORIAS_POR_PAGINA)
    pagina = max(0, min(pagina, paginas - 1))
    desde = pagina * CATEGORIAS_POR_PAGINA

    filas = []
    for indice in range(desde, min(desde + CATEGORIAS_POR_PAGINA, total_cat)):
        marca = MARCA if puestos.get(indice) else "▫️"
        filas.append([InlineKeyboardButton(
            f"{marca} {premios.nombre_de(indice)}"[:60],
            callback_data=f"c:{indice}")])

    if paginas > 1:
        paso = []
        if pagina > 0:
            paso.append(InlineKeyboardButton("‹", callback_data=f"cam:{pagina - 1}"))
        paso.append(InlineKeyboardButton(f"{pagina + 1}/{paginas}",
                                         callback_data="nada"))
        if pagina < paginas - 1:
            paso.append(InlineKeyboardButton("›", callback_data=f"cam:{pagina + 1}"))
        filas.append(paso)

    filas.append([InlineKeyboardButton("Mis votos", callback_data="r")])
    return InlineKeyboardMarkup(filas)


def _texto_cambiar() -> str:
    return ("✏️ <b>¿Cuál quieres cambiar?</b>\n\n"
            "Toca una categoría y la votas otra vez.")


async def _pantalla_resumen(usuario: int) -> tuple[str, InlineKeyboardMarkup]:
    """El resumen entero con una sola lectura de la base."""
    puestos = await banco.votos_de(usuario)
    return _texto_resumen(puestos), _teclado_resumen(puestos)


async def _dejar_votar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Si esta persona puede votar ahora. Si no, se lo dice y devuelve False."""
    mensaje = update.effective_message
    if cerrada():
        await mensaje.reply_text(
            "La votación ya está cerrada. Gracias por participar.")
        return False
    if not premios.CATEGORIAS:
        await mensaje.reply_text(
            "Todavía no hay nada que votar. Vuelve en un rato.")
        return False
    quien = update.effective_user
    if not await socios.puede_votar(context.bot, quien.id):
        aviso = ("Esta votación es para la gente de los grupos.\n\n"
                 "Únete y vuelve a escribirme.")
        if ENLACE_DEL_GRUPO:
            aviso += f"\n\n{ENLACE_DEL_GRUPO}"
        await mensaje.reply_text(aviso)
        return False
    return True


async def empezar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/votar`, y tambien `/start`."""
    if not await _dejar_votar(update, context):
        return
    quien = update.effective_user
    indice = await _siguiente_sin_votar(quien.id, 0)
    if indice is None:
        texto, teclado = await _pantalla_resumen(quien.id)
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.HTML, reply_markup=teclado)
        return
    puestos = await banco.votos_de(quien.id)
    await update.effective_message.reply_text(
        _texto(indice, puestos.get(indice)), parse_mode=ParseMode.HTML,
        reply_markup=_teclado(indice, 0, puestos.get(indice)))


async def _editar(consulta, texto: str, teclado) -> None:
    """Cambia el mensaje por otro.

    «Message is not modified» pasa al tocar la pagina en la que ya estas.
    No es un fallo y no tiene que ensuciar el registro.
    """
    try:
        await consulta.edit_message_text(texto, parse_mode=ParseMode.HTML,
                                         reply_markup=teclado)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def _repintar(consulta, indice: int, pagina: int, usuario: int) -> None:
    puestos = await banco.votos_de(usuario)
    votado = puestos.get(indice)
    await _editar(consulta, _texto(indice, votado),
                  _teclado(indice, pagina, votado))


async def pulsado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Todos los botones de la votacion."""
    consulta = update.callback_query
    datos = consulta.data or ""
    quien = update.effective_user

    if datos == "nada":
        await consulta.answer()
        return

    if cerrada():
        await consulta.answer("La votación ya está cerrada.", show_alert=True)
        return

    if not await socios.puede_votar(context.bot, quien.id):
        await consulta.answer(
            "Esta votación es para la gente de los grupos.", show_alert=True)
        return

    if datos == "r":
        await consulta.answer()
        texto, teclado = await _pantalla_resumen(quien.id)
        await consulta.edit_message_text(
            texto, parse_mode=ParseMode.HTML, reply_markup=teclado)
        return

    # La lista de categorias, para cambiar un voto ya puesto.
    if datos.startswith("cam:"):
        await consulta.answer()
        puestos = await banco.votos_de(quien.id)
        await _editar(consulta, _texto_cambiar(),
                      _teclado_cambiar(puestos, int(datos.split(":")[1])))
        return

    # Y volver a una de ellas.
    if datos.startswith("c:"):
        await consulta.answer()
        await _repintar(consulta, int(datos.split(":")[1]), 0, quien.id)
        return

    if datos == "seguir":
        siguiente = await _siguiente_sin_votar(quien.id, 0)
        await consulta.answer()
        if siguiente is None:
            return
        await _repintar(consulta, siguiente, 0, quien.id)
        return

    partes = datos.split(":")
    accion = partes[0]

    if accion == "p" and len(partes) == 3:
        await consulta.answer()
        await _repintar(consulta, int(partes[1]), int(partes[2]), quien.id)
        return

    if accion == "s" and len(partes) == 2:
        indice = int(partes[1])
        siguiente = await _siguiente_sin_votar(quien.id, indice + 1)
        await consulta.answer("Saltada")
        if siguiente is None:
            texto, teclado = await _pantalla_resumen(quien.id)
            await consulta.edit_message_text(
                texto, parse_mode=ParseMode.HTML, reply_markup=teclado)
            return
        await _repintar(consulta, siguiente, 0, quien.id)
        return

    if accion == "v" and len(partes) == 4:
        indice, _, cual = int(partes[1]), int(partes[2]), int(partes[3])
        elegido = premios.nominado(indice, cual)
        if elegido is None:
            # El boton viene de un mensaje viejo y la lista ha cambiado.
            await consulta.answer(
                "Ese botón ya no vale. Escríbeme /votar y lo retomamos.",
                show_alert=True)
            return
        await banco.guardar(quien.id, quien.username or quien.full_name,
                            indice, elegido)
        await consulta.answer(f"Votado: {elegido}"[:200])
        siguiente = await _siguiente_sin_votar(quien.id, indice + 1)
        if siguiente is None:
            texto, teclado = await _pantalla_resumen(quien.id)
            await consulta.edit_message_text(
                texto, parse_mode=ParseMode.HTML, reply_markup=teclado)
            return
        await _repintar(consulta, siguiente, 0, quien.id)
        return

    await consulta.answer()
