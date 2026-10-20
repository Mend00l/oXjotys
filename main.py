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
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler)

from bot import banco, premios, recuento, reloj, votacion
from config import CASA, CIERRA_EL, TELEGRAM_TOKEN, lo_que_falta

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

    _planificar_cierre(app)

    logger.info("Votacion en marcha.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()
            await banco.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
