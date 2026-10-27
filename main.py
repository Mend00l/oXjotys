"""El arranque de la votacion.

Se vota **en privado**, una categoria cada vez, y solo la gente que esta
en los grupos de Edu. Lo que hace cada pieza:

    bot/premios.py   las categorias y nominados, de premios.json
    bot/socios.py    quien puede votar
    bot/votacion.py  el paso a paso y los botones
    bot/banco.py     donde se guardan los votos
    bot/recuento.py  el recuento y el cierre, solo para Edu
"""

import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from telegram.error import Conflict
from telegram.ext import (Application, CallbackQueryHandler, ChatMemberHandler,
                          CommandHandler)

from bot import banco, premios, recuento, reloj, socios, votacion
from config import (CASA, CIERRA_EL, DATABASE_URL, TELEGRAM_TOKEN,
                    lo_que_falta)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
# **Railway corre en UTC.** Sin esto, cada linea del registro sale dos
# horas antes de cuando paso. Ver `bot/reloj.py`.
logging.Formatter.converter = lambda *_: reloj.ahora().timetuple()
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# APScheduler descarta una cita con un segundo de retraso: ese es su
# valor de fabrica. La del cierre es una sola y llega una vez, asi que se
# le da una hora de cortesia para que no se pierda por estar el bucle
# ocupado justo en ese segundo.
GRACIA = {"misfire_grace_time": 3600}


# Cada cuanto se mira que el bot siga escuchando.
VIGILA = 60


async def se_rompio(update, context) -> None:
    """Lo que falle, apuntado en una linea, y el bot sigue vivo.

    Sin esto, python-telegram-bot vuelca la traza entera por cada intento
    y entre cuarenta lineas no se ve lo unico que importa: que ha pasado.

    `Conflict` tiene mensaje propio porque su texto en ingles no dice como
    se arregla: significa que hay dos procesos con el mismo token, y
    Telegram solo admite uno.
    """
    error = context.error
    if isinstance(error, Conflict):
        logger.error("Hay otro bot escuchando con este mismo token —puede "
                     "ser uno en local, o un despliegue viejo que no se "
                     "apago—. Telegram solo admite uno: apaga el otro.")
        return
    logger.error(f"{type(error).__name__}: {error}", exc_info=error)


async def _vigilar(app) -> None:
    """Esperar, pero mirando que el bot siga escuchando.

    **Aqui habia un `asyncio.Event().wait()`**, que no se cumple nunca y
    tampoco se entera de nada. El que recoge los mensajes es otra tarea:
    si se muere, el proceso sigue vivo, Railway lo ve verde y el bot se
    queda sordo **sin una sola linea en el registro**.

    Paso el 26-oct-2026: dos `Conflict` al desplegar, silencio durante 24
    horas y nadie pudo votar. Se descubrio porque Telegram dejo leer sus
    mensajes a otro, que es lo que solo pasa cuando no hay nadie
    recogiendolos.

    Cerrarse con error es a proposito: asi Railway lo levanta otra vez.
    """
    while app.updater.running:
        await asyncio.sleep(VIGILA)
    raise SystemExit("El bot ha dejado de escuchar. Me cierro para que me "
                     "vuelvan a levantar.")


def _planificar_cierre(app) -> None:
    """La cita del cierre, si hay fecha y no ha pasado ya."""
    if CIERRA_EL is None:
        return
    if reloj.ahora() >= CIERRA_EL:
        logger.warning("La fecha de cierre ya pasó: la votación nace cerrada")
        return

    async def _cerrar():
        logger.info("Cierra la votacion")
        await recuento.avisar_del_cierre(app.bot)

    planificador = AsyncIOScheduler(timezone=CASA, job_defaults=GRACIA)
    # **La zona va en el disparador y no solo en el planificador.** Un
    # disparador construido a mano no la hereda: coge la de la maquina,
    # que en casa es Madrid y en Railway UTC. Sale bien al probarlo y dos
    # horas tarde en produccion; costo una tarde en ofertasXbot.
    planificador.add_job(_cerrar, DateTrigger(run_date=CIERRA_EL, timezone=CASA),
                         id="cierre")
    planificador.start()
    logger.info(f"La votacion cierra el {CIERRA_EL:%d/%m/%Y a las %H:%M} "
                f"(hora de España)")


async def main() -> None:
    falta = lo_que_falta() + premios.lo_que_falta()
    if falta:
        logger.warning("Falta por configurar: " + ", ".join(falta))
    if not TELEGRAM_TOKEN:
        raise SystemExit("Sin TELEGRAM_TOKEN no hay bot. Se pone en Railway.")
    # Sin direccion, asyncpg prueba la base de esta misma maquina y suelta
    # cuarenta lineas de traza sobre 127.0.0.1:5432 que no dicen que falta
    # una variable. Mejor pararse aqui y decirlo en una linea.
    if not DATABASE_URL:
        raise SystemExit(
            "Sin DATABASE_URL no hay donde guardar los votos. En Railway no "
            "la hereda el bot al crear la base: se pone a mano en sus "
            "variables, como ${{Postgres.DATABASE_URL}}.")

    await banco.abrir()
    logger.info(f"{premios.cuantas()} categorías, "
                f"{sum(len(c['nominados']) for c in premios.CATEGORIAS)} "
                f"nominados")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", votacion.empezar))
    app.add_handler(CommandHandler("votar", votacion.empezar))
    app.add_handler(CommandHandler("recuento", recuento.recuento))
    app.add_handler(CommandHandler("estado", recuento.estado))
    app.add_handler(CallbackQueryHandler(recuento.publicar, pattern=r"^pub:"))
    app.add_handler(CallbackQueryHandler(votacion.pulsado))
    # **`MY_CHAT_MEMBER` y no `CHAT_MEMBER`**: el primero es el bot
    # entrando o saliendo de un grupo, y Telegram lo manda de serie. El
    # segundo son los demas yendo y viniendo, que no se piden --ni se
    # reciben sin decirlo-- y aqui no hacen falta.
    app.add_handler(ChatMemberHandler(socios.me_han_metido,
                                      ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(se_rompio)

    _planificar_cierre(app)

    logger.info("Votacion en marcha.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        try:
            await _vigilar(app)
        finally:
            await app.updater.stop()
            await app.stop()
            await banco.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
