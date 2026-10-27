"""Apuntar los ganadores de verdad, y volcar los aciertos al Sheet.

**Esto no corre en Railway.** Es una herramienta de mano, para el dia de
la gala de los Golden Joystick: se apunta quien gano en cada categoria y
el bot ya calcula los aciertos solo.

    python -m herramientas.ganadores ver
    python -m herramientas.ganadores poner 0:2 5:1
    python -m herramientas.ganadores poner 0:2 5:1 --si
    python -m herramientas.ganadores sheet
    python -m herramientas.ganadores sheet --si
    python -m herramientas.ganadores sorteo

**Los ganadores se eligen por numero, nunca escribiendo el nombre.**
`0:2` quiere decir «en la categoria 0, el nominado 2», y el texto que se
guarda lo saca el propio script de `premios.json`. Escribirlo a mano
seria la forma de que un acento de diferencia dejara de casar con los
votos de la gente, y eso **no da ningun error**: simplemente nadie
acierta esa categoria y nunca se sabe por que.

**Sin `--si` no escribe nada.** Ensena lo que haria y para. Primero se
lee en voz alta, luego se confirma: un ganador mal apuntado se corrige
--se puede volver a poner-- pero mientras tanto la clasificacion que ve
la gente es falsa.

Para `sheet` hacen falta `GOOGLE_SHEETS_ID` y `GOOGLE_SHEETS_CREDENTIALS`
en el entorno, y `gspread`, que no van en el bot: **el bot no habla con
Google**, para no tener la clave de la cuenta de servicio en un servicio
mas de Railway. El vuelco se hace de aqui.

`sorteo` elige al ganador del premio. **Lo normal es que haya empate
arriba**: medido con las 22 categorias de verdad, sale empate mas veces
que no --del 48 al 65% segun cuanto consenso haya-- y en casi la mitad de
los casos son tres o mas. Asi que el desempate no es un caso raro que se
resuelve el dia que pase: es lo que va a pasar.
"""

import asyncio
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from bot import banco, premios  # noqa: E402
from bot.aciertos import SIN_NOMBRE  # noqa: E402
from bot.reloj import ahora, sello  # noqa: E402
from config import ADMIN_ID  # noqa: E402

# La pestaña de los aciertos, en el mismo documento que los votos de
# ofertasXbot y los puntos de Marcy: es la misma cuenta de servicio y ya
# esta compartido, asi que no hay nada que preparar.
PESTANA = "oXJOTYs"
TITULOS = ["usuario", "nombre", "aciertos", "de", "cuando"]
ALCANCE = ["https://www.googleapis.com/auth/spreadsheets"]


# --- ver ---

async def ver() -> None:
    """Las categorias con sus nominados numerados, y lo ya apuntado."""
    puestos = await banco.ganadores()
    for indice in range(premios.cuantas()):
        cat = premios.categoria(indice)
        ganador = puestos.get(indice)
        marca = f"  ← {ganador}" if ganador else ""
        print(f"\n[{indice}] {cat['nombre']}{marca}")
        for cual, nominado in enumerate(cat["nominados"]):
            print(f"     {cual}: {nominado}")
    faltan = [i for i in range(premios.cuantas()) if i not in puestos]
    print(f"\nApuntadas {len(puestos)} de {premios.cuantas()}.")
    if faltan:
        print("Faltan: " + ", ".join(str(i) for i in faltan))


# --- poner ---

def _leer_pares(crudos: list[str]) -> list[tuple[int, int]]:
    """`0:2` -> `(0, 2)`. Revienta a proposito si algo no cuadra.

    Un par mal escrito tiene que parar el script entero y no colarse
    como un ganador de otra categoria.
    """
    pares = []
    for crudo in crudos:
        try:
            cat, cual = crudo.split(":")
            pares.append((int(cat), int(cual)))
        except ValueError:
            raise SystemExit(f"No entiendo {crudo!r}. Se escribe 0:2 "
                             f"(categoría 0, nominado 2).")
    return pares


async def poner(crudos: list[str], de_verdad: bool) -> None:
    pares = _leer_pares(crudos)

    # Se resuelven TODOS antes de escribir ninguno: si el ultimo par
    # apunta a un nominado que no existe, no se queda media gala puesta.
    lista = []
    for indice, cual in pares:
        nombre = premios.nombre_de(indice)
        nominado = premios.nominado(indice, cual)
        if nominado is None:
            raise SystemExit(f"En la categoría {indice} ({nombre}) no hay "
                             f"ningún nominado {cual}.")
        lista.append((indice, nombre, nominado))

    puestos = await banco.ganadores()
    print()
    for indice, nombre, nominado in lista:
        antes = puestos.get(indice)
        cambio = f"   (antes: {antes})" if antes and antes != nominado else ""
        print(f"[{indice}] {nombre}\n     → {nominado}{cambio}")

    if not de_verdad:
        print("\nEn seco. Para escribirlo de verdad, otra vez con --si.")
        return
    for indice, _, nominado in lista:
        await banco.poner_ganador(indice, nominado)
    print(f"\nApuntados {len(lista)}.")


# --- sheet ---

def _abrir_pestana():
    """La pestaña de los aciertos. Importa gspread aqui a proposito:
    `ver` y `poner` no lo necesitan y no se va a pedir instalarlo para
    mirar una lista."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise SystemExit("Para volcar al Sheet hacen falta gspread y "
                         "google-auth:\n"
                         "    pip install -r herramientas/requirements.txt")

    documento = (os.getenv("GOOGLE_SHEETS_ID") or "").strip()
    clave = os.getenv("GOOGLE_SHEETS_CREDENTIALS") or ""
    if not documento or not clave.strip():
        raise SystemExit("Faltan GOOGLE_SHEETS_ID o "
                         "GOOGLE_SHEETS_CREDENTIALS en el entorno.")

    credenciales = Credentials.from_service_account_info(
        json.loads(clave), scopes=ALCANCE)
    cliente = gspread.authorize(credenciales)
    cliente.set_timeout(20)
    libro = cliente.open_by_key(documento)

    quiero = PESTANA.strip().lower()
    for pestana in libro.worksheets():
        if pestana.title.strip().lower() == quiero:
            return pestana
    return libro.add_worksheet(title=PESTANA, rows=500, cols=5)


def _filas(tabla: list[tuple[int, str | None, int]], resueltas: int,
           cuando: str) -> list[list[str]]:
    """La tabla tal como va al Sheet. Todo en texto: lo que se escribe
    sin interpretar es lo que se lee luego igual."""
    return [[str(usuario), (alias or "").strip() or SIN_NOMBRE,
             str(cuantos), str(resueltas), cuando]
            for usuario, alias, cuantos in tabla]


def _volcar(hoja, filas: list[list[str]]) -> None:
    """Escribe la pestaña entera, cabecera incluida.

    **No se machaca una pestaña que no sea la nuestra.** Es el mismo
    documento que los votos de ofertasXbot y los puntos de Marcy: si en
    A1 hay otra cosa, aqui se para en vez de borrarla.

    Y se escribe **de una vez y con el rango puesto**: gspread 6 cambio
    el orden de los argumentos de `update` y, sin nombrarlos, escribe en
    columnas que no son. Ya paso en los otros bots.
    """
    primera = [c.strip().lower() for c in hoja.row_values(1)]
    if primera and primera != TITULOS:
        raise SystemExit(f"La pestaña {hoja.title!r} no es la de los "
                         f"aciertos: en A1 pone {primera}. No la toco.")
    # Se vacia antes de escribir porque la tabla puede venir mas corta
    # que la de la vez anterior --alguien borrado, una prueba-- y si no,
    # abajo se quedarian filas viejas que nadie distingue de las nuevas.
    hoja.clear()
    hoja.update(values=[TITULOS] + filas,
                range_name=f"A1:E{len(filas) + 1}")


async def sheet(de_verdad: bool) -> None:
    puestos = await banco.ganadores()
    if not puestos:
        raise SystemExit("No hay ningún ganador apuntado todavía: lo que se "
                         "volcaría serían ceros.")
    filas = _filas(await banco.clasificacion(), len(puestos), sello())

    print(f"\n{len(filas)} personas, {len(puestos)} categorías resueltas.")
    for fila in filas[:5]:
        print("   " + " | ".join(fila))
    if len(filas) > 5:
        print(f"   ... y {len(filas) - 5} más")

    if not de_verdad:
        print("\nEn seco. Para escribirlo de verdad, otra vez con --si.")
        return

    hoja = _abrir_pestana()
    _volcar(hoja, filas)
    print(f"\nEscritas {len(filas)} filas en la pestaña {hoja.title!r}.")


# --- sorteo ---

def _empatados_arriba(tabla: list[tuple[int, str | None, int]],
                      fuera: tuple[int, ...] = ()
                      ) -> tuple[int, list[tuple[int, str]]]:
    """La mejor nota y quien la tiene, ordenados. `(nota, [(id, nombre)])`.

    **Ordenados por numero de usuario**, no como venga de la base: el
    sorteo tiene que dar el mismo resultado cada vez que se repita con la
    misma semilla, y para eso la lista de partida no puede bailar.
    """
    dentro = [(u, (a or "").strip() or SIN_NOMBRE, c)
              for u, a, c in tabla if u not in fuera]
    if not dentro:
        return 0, []
    mejor = max(c for _, _, c in dentro)
    return mejor, sorted((u, a) for u, a, c in dentro if c == mejor)


def _sortear(empatados: list[tuple[int, str]],
             semilla: str) -> tuple[int, str]:
    """Uno de los empatados, al azar pero **repetible**.

    La gracia de la semilla es que el sorteo se pueda comprobar: con la
    lista y la semilla, cualquiera lo repite y le sale el mismo. Un
    `random.choice` a secas sale igual de limpio y **no hay forma de
    demostrarlo**, que en un premio con dos mil personas delante no es lo
    mismo.
    """
    return random.Random(semilla).choice(empatados)


async def sorteo(semilla: str | None, con_el_dueno: bool) -> None:
    puestos = await banco.ganadores()
    if not puestos:
        raise SystemExit("No hay ningún ganador apuntado: todavía no hay "
                         "nada que sortear.")
    if len(puestos) < premios.cuantas():
        print(f"⚠ Ojo: solo hay {len(puestos)} de {premios.cuantas()} "
              f"categorías resueltas. La nota de todos puede subir aún.\n")

    # **El dueño fuera por defecto.** Sus votos de prueba estan en la
    # tabla como los de cualquiera --voto en privado para probarlo-- y es
    # quien pone el premio.
    fuera = () if con_el_dueno or not ADMIN_ID else (ADMIN_ID,)
    mejor, empatados = _empatados_arriba(await banco.clasificacion(), fuera)
    if not empatados:
        raise SystemExit("No hay nadie en la clasificación.")

    print(f"Mejor nota: {mejor} de {len(puestos)} categorías resueltas.")
    if fuera:
        print("(El dueño queda fuera del sorteo. Con --con-el-dueno entra.)")

    if len(empatados) == 1:
        usuario, nombre = empatados[0]
        print(f"\nNo hay empate. Gana {nombre} ({usuario}).")
        return

    semilla = semilla or f"{ahora():%Y-%m-%d}"
    print(f"\nEmpatados a {mejor}, {len(empatados)}:")
    for usuario, nombre in empatados:
        print(f"  {usuario}  {nombre}")

    usuario, nombre = _sortear(empatados, semilla)
    print(f"\nSemilla: {semilla!r}")
    print(f"GANA: {nombre} ({usuario})")
    print("\nCon esa lista y esa semilla el sorteo se repite igual, asi que "
          "se puede\nenseñar y lo comprueba quien quiera.")


# --- arranque ---

async def main() -> None:
    # **La consola de Windows no escribe en UTF-8.** Sin esto el script
    # se corta por la mitad de la lista con un UnicodeEncodeError en
    # cuanto llega a un nominado con un caracter que su pagina de codigos
    # no tiene --y los hay--. Medido: paraba en la categoria 3.
    for salida in (sys.stdout, sys.stderr):
        if hasattr(salida, "reconfigure"):
            salida.reconfigure(encoding="utf-8", errors="replace")

    # Las marcas fuera y lo demas en orden. **El valor de `--semilla` se
    # coge por posicion**, no quitando de la lista lo que se le parezca:
    # una semilla que se llamara igual que una orden --`--semilla
    # sorteo`-- se llevaria la orden por delante.
    de_verdad = con_el_dueno = False
    semilla = None
    argumentos = []
    toca_la_semilla = False
    for trozo in sys.argv[1:]:
        if toca_la_semilla:
            semilla, toca_la_semilla = trozo, False
        elif trozo == "--semilla":
            toca_la_semilla = True
        elif trozo == "--si":
            de_verdad = True
        elif trozo == "--con-el-dueno":
            con_el_dueno = True
        else:
            argumentos.append(trozo)
    que = argumentos[0] if argumentos else "ver"

    await banco.abrir()
    try:
        if que == "ver":
            await ver()
        elif que == "poner":
            if len(argumentos) < 2:
                raise SystemExit("Dime qué poner: poner 0:2 5:1")
            await poner(argumentos[1:], de_verdad)
        elif que == "sheet":
            await sheet(de_verdad)
        elif que == "sorteo":
            await sorteo(semilla, con_el_dueno)
        else:
            raise SystemExit(__doc__)
    finally:
        await banco.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
