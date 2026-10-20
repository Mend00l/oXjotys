"""La hora de casa, para que todo cuadre con el reloj de España.

**Railway corre en UTC.** Sin esto, una votacion que cierra «el 9 a
medianoche» cerraria a las dos de la madrugada del 10 para quien vota
desde aqui, y el registro contaria las cosas dos horas antes de cuando
pasaron.

Va con `zoneinfo` y el paquete `tzdata`, no con la variable `TZ`: esa
depende de que la imagen traiga los ficheros de zonas del sistema, y si
no los trae **se queda en UTC sin decir nada**.
"""

from datetime import datetime

from config import CASA


def ahora() -> datetime:
    return datetime.now(CASA)


def sello() -> str:
    return ahora().strftime("%d/%m/%Y %H:%M")
