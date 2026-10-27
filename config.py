"""Lo que se configura desde fuera. Nada de claves escritas aqui.

En local se leen de un `.env` que no sube a GitHub; en Railway, de sus
variables. `.env.example` dice cuales hacen falta, con los valores
vacios, para que al montarlo en otra maquina no haya que adivinarlas.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

CASA = ZoneInfo("Europe/Madrid")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Donde viven los votos. **Una base propia y no una hoja de calculo**:
# votar las 22 categorias son 22 escrituras por persona, y el cupo de
# Google --300 por minuto-- lo comparten los otros cuatro bots con la
# misma cuenta de servicio. Quince personas votando a la vez se lo comen
# y lo que se rompe es Miss apuntando un aviso, no esto.
DATABASE_URL = os.getenv("DATABASE_URL")


def _entero(nombre: str, defecto: int) -> int:
    """Una variable puesta pero vacia es lo mismo que no tenerla."""
    try:
        return int((os.getenv(nombre) or "").strip() or defecto)
    except ValueError:
        return defecto


ADMIN_ID = _entero("ADMIN_ID", 0)
ADMIN_ID_CRUDO = (os.getenv("ADMIN_ID") or "").strip()


def _grupos(crudo: str) -> list[str]:
    """Los grupos cuyos miembros pueden votar, separados por comas.

    **El numero se queda en texto**, sin pasarlo a entero, para que valga
    tambien un `@alias`. Es la misma forma que `ZELDA_EN` en ofertasXbot
    y `CAZA_GRUPOS` en SrMarcy: `-1002064045581,@otrogrupo`.

    Aqui no hay temas: para preguntar si alguien esta dentro basta el
    grupo, y un tema no cambia la respuesta.
    """
    return [t.strip() for t in (crudo or "").split(",") if t.strip()]


GRUPOS = _grupos(os.getenv("GRUPOS") or "")

# El enlace que se le enseña a quien no esta en ninguno. Si no se pone,
# se le dice que se una sin decirle a donde, que es peor pero no falso.
ENLACE_DEL_GRUPO = (os.getenv("ENLACE_DEL_GRUPO") or "").strip()


def _cuando_cierra(crudo: str) -> datetime | None:
    """La fecha de cierre, en hora de casa: `2026-11-09 23:59`.

    **Con hora, y con la de España.** Railway corre en UTC: sin decirlo,
    una votacion que cierra «el 9 a medianoche» cerraria a las dos de la
    madrugada del 10 para quien vota desde aqui.
    """
    crudo = (crudo or "").strip()
    if not crudo:
        return None
    for forma in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(crudo, forma).replace(tzinfo=CASA)
        except ValueError:
            continue
    return None


CIERRA_EL = _cuando_cierra(os.getenv("CIERRA_EL") or "")
CIERRA_EL_CRUDO = (os.getenv("CIERRA_EL") or "").strip()

# Cuantos nominados por pantalla. Ocho porque la mayoria de categorias
# tienen seis: asi casi todas se resuelven sin pasar pagina, y las de
# diez se quedan en dos. Con cinco eran cuarenta y seis pantallas.
POR_PAGINA = _entero("POR_PAGINA", 8)

# Donde se puede publicar el resultado al cerrar. Sale un boton por cada
# uno, y **no se publica solo**: el resultado se lee antes de salir, por
# si hay que corregir algo o contar algo al lado. Mismo formato que los
# grupos: numeros o alias, separados por comas.
PUBLICAR_EN = _grupos(os.getenv("PUBLICAR_EN") or "")

# Lo que se recuerda que alguien es de un grupo antes de volver a
# preguntarselo a Telegram. Votar son veintiun toques: preguntarlo en
# cada uno es gastar llamadas para oir lo mismo.
MINUTOS_DE_MEMORIA = _entero("MINUTOS_DE_MEMORIA", 30)


def lo_que_falta() -> list[str]:
    """Lo que hay que poner para que esto haga algo.

    Se dice **al arrancar y de una vez**: un bot que arranca y se queda
    mudo se ve igual que uno caido.
    """
    falta = []
    if not TELEGRAM_TOKEN:
        falta.append("TELEGRAM_TOKEN (lo da BotFather)")
    if not DATABASE_URL:
        falta.append("DATABASE_URL (la base de Railway; sin ella no se "
                     "guarda ni un voto)")
    if not ADMIN_ID:
        falta.append("ADMIN_ID"
                     + (f" (esta puesto como {ADMIN_ID_CRUDO!r} y no es un "
                        f"numero)" if ADMIN_ID_CRUDO else ""))
    if not GRUPOS:
        falta.append("GRUPOS (sin esto no puede votar nadie)")
    if CIERRA_EL is None:
        falta.append("CIERRA_EL"
                     + (f" (esta puesto como {CIERRA_EL_CRUDO!r} y no se "
                        f"entiende; se escribe 2026-11-09 23:59)"
                        if CIERRA_EL_CRUDO else " (la fecha de cierre)"))
    return falta
