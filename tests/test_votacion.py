"""Lo que no puede romperse en la votacion.

Son veintinueve categorias y 148 nominados --los GOTY 2026, desde el
17-nov-2026; antes eran los Golden Joystick, 22 y 180--: lo que se
comprueba aqui es que nadie se pierda por el camino --que la paginacion
cuadre, que quien lo deje a medias retome por lo que le falta y que un
boton viejo no cuele un voto que no es--.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from bot import premios, votacion  # noqa: E402


# --- la lista -------------------------------------------------------------

def test_estan_las_veintinueve_categorias():
    """Si alguien toca premios.json y se deja media lista, se ve aqui y no
    en mitad de la votacion.

    **Los GOTY 2026 desde el 17-nov-2026**: 29 categorias y 148 nominados,
    sacados de la lista de Meristation. Antes eran los Golden Joystick, con
    22 y 180.
    """
    assert premios.cuantas() == 29
    assert sum(len(c["nominados"]) for c in premios.CATEGORIAS) == 148


def test_la_nueva_va_la_ultima():
    """**El orden es la clave de cada categoria**, y los votos guardados
    apuntan a ese numero. Meter una nueva por el medio --o delante, que es
    donde iria por importancia-- renumeraria las de detras y cada voto ya
    dado pasaria a contar en otra categoria."""
    assert premios.nombre_de(0) == "Juego del Año"
    assert premios.nombre_de(28) == "Creador de Contenido del Año"


def test_ninguna_categoria_se_queda_sin_nominados():
    for indice in range(premios.cuantas()):
        assert premios.categoria(indice)["nominados"], premios.nombre_de(indice)


def test_un_nominado_que_no_existe_no_se_inventa():
    """El boton puede venir de un mensaje viejo: si la lista cambio, ese
    numero ya no apunta a lo mismo y hay que decirlo, no votar otra cosa."""
    assert premios.nominado(0, 999) is None
    assert premios.nominado(999, 0) is None


# --- la paginacion --------------------------------------------------------

def test_la_mayoria_de_categorias_caben_en_una_pantalla():
    """**El motivo de los ocho por pagina.** Casi todas tienen seis
    nominados: con cinco habia que pasar pagina en todas."""
    de_una = sum(1 for c in premios.CATEGORIAS
                 if len(c["nominados"]) <= config.POR_PAGINA)
    assert de_una >= 12, "con este tamaño de pagina se pasa pagina de mas"


def test_la_mas_larga_no_pasa_de_tres_paginas():
    mayor = max(len(c["nominados"]) for c in premios.CATEGORIAS)
    assert votacion._paginas(mayor) <= 3


def test_una_sola_pagina_no_lleva_flechas():
    """Unas flechas que no llevan a ningun sitio confunden."""
    corta = next(i for i, c in enumerate(premios.CATEGORIAS)
                 if len(c["nominados"]) <= config.POR_PAGINA)
    filas = votacion._teclado(corta, 0, None).inline_keyboard
    rotulos = [b.text for fila in filas for b in fila]
    assert not any(r in ("‹", "›") for r in rotulos)


# **Las dos de las flechas se prueban con una categoria inventada.**
# Hasta el 17-nov-2026 cogian la mas larga de `premios.json` y daba igual,
# porque los Golden Joystick tenian categorias de 10, 12 y 20 nominados. Los
# GOTY 2026 no pasan de 6 y `POR_PAGINA` son 8: **ninguna categoria pagina**,
# asi que buscando la mas larga ya no se probaba nada --las dos se pusieron
# rojas pidiendo una flecha que no tenia por que salir--.
#
# Con una de mentira se prueba el mecanismo y no los nominados de este año,
# que es lo que tiene que seguir funcionando el dia que vuelva a haber una
# categoria de veinte.
def _con_una_larga(monkeypatch, cuantos=20):
    """Deja una categoria de `cuantos` nominados y devuelve su indice."""
    larga = {"nombre": "De mentira", "nominados": [f"n{i}" for i in range(cuantos)]}
    monkeypatch.setattr(premios, "CATEGORIAS", list(premios.CATEGORIAS) + [larga])
    return premios.cuantas() - 1


def test_la_primera_pagina_no_tiene_flecha_atras(monkeypatch):
    larga = _con_una_larga(monkeypatch)
    rotulos = [b.text for fila in votacion._teclado(larga, 0, None).inline_keyboard
               for b in fila]
    assert "›" in rotulos and "‹" not in rotulos


def test_la_ultima_pagina_no_tiene_flecha_adelante(monkeypatch):
    larga = _con_una_larga(monkeypatch)
    ultima = votacion._paginas(len(premios.categoria(larga)["nominados"])) - 1
    rotulos = [b.text for fila in votacion._teclado(larga, ultima, None).inline_keyboard
               for b in fila]
    assert "‹" in rotulos and "›" not in rotulos


def test_todos_los_nominados_salen_en_alguna_pagina():
    """Si la cuenta de paginas y el corte no cuadran, hay nominados a los
    que no se puede votar y nadie se entera."""
    for indice, cat in enumerate(premios.CATEGORIAS):
        vistos = []
        for pagina in range(votacion._paginas(len(cat["nominados"]))):
            for fila in votacion._teclado(indice, pagina, None).inline_keyboard:
                for boton in fila:
                    if (boton.callback_data or "").startswith("v:"):
                        vistos.append(int(boton.callback_data.split(":")[3]))
        assert sorted(vistos) == list(range(len(cat["nominados"]))), \
            premios.nombre_de(indice)


def test_lo_votado_sale_marcado():
    elegido = premios.categoria(0)["nominados"][0]
    filas = votacion._teclado(0, 0, elegido).inline_keyboard
    rotulos = [b.text for fila in filas for b in fila]
    assert any(r.startswith(votacion.MARCA) for r in rotulos)


def test_lo_que_viaja_en_un_boton_cabe_en_telegram():
    """Telegram solo admite 64 caracteres en el dato de un boton."""
    for indice in range(premios.cuantas()):
        for pagina in range(votacion._paginas(
                len(premios.categoria(indice)["nominados"]))):
            for fila in votacion._teclado(indice, pagina, None).inline_keyboard:
                for boton in fila:
                    assert len(boton.callback_data.encode()) <= 64


# --- por donde se sigue ----------------------------------------------------

async def test_se_retoma_por_lo_que_falta_y_no_por_donde_se_dejo(monkeypatch):
    """Quien vota tres, se cansa y vuelve dias despues tiene que caer en la
    cuarta. Y si dejo huecos atras, se vuelve a ellos dando la vuelta: si
    no, esa votacion se queda a medias para siempre."""
    async def _votos(usuario):
        return {0: "a", 2: "b"}

    monkeypatch.setattr(votacion.banco, "votos_de", _votos)
    assert await votacion._siguiente_sin_votar(1, 0) == 1
    assert await votacion._siguiente_sin_votar(1, 3) == 3
    # Desde la ultima, da la vuelta y vuelve al hueco de atras.
    assert await votacion._siguiente_sin_votar(1, 20) == 20


async def test_cuando_estan_todas_no_hay_siguiente(monkeypatch):
    async def _votos(usuario):
        return {i: "x" for i in range(premios.cuantas())}

    monkeypatch.setattr(votacion.banco, "votos_de", _votos)
    assert await votacion._siguiente_sin_votar(1, 0) is None


def _todas():
    return {i: "x" for i in range(premios.cuantas())}


def test_al_terminar_se_da_las_gracias():
    """Lo que se lee tras el ultimo voto. **Contesta de paso lo que mas se
    pregunta**: cuando se sabe el ganador."""
    texto = votacion._texto_resumen(_todas())

    assert "¡Gracias por participar en los oXJOTYs!" in texto
    assert "The Game Awards" in texto
    assert "finalice el plazo" in texto


def test_la_fecha_de_los_textos_sale_de_la_configuracion(monkeypatch):
    """**No se escribe a mano.** Un «9/11» puesto a dedo sigue ahi el año
    que la fecha cambie, y nadie lo nota: el texto no falla, miente."""
    monkeypatch.setattr(votacion, "EL_PLAZO", "9 de Noviembre")
    monkeypatch.setattr(votacion, "HASTA_EL_DIA", "hasta el día 9/11")

    assert "9 de Noviembre" in votacion._texto_resumen(_todas())
    assert "hasta el día 9/11" in votacion._texto(0, "Lo que voto")


def test_a_medias_no_se_despide():
    """Despedirse de quien va por la tercera sonaria a que ya ha acabado."""
    texto = votacion._texto_resumen({0: "x", 1: "y"})

    assert "Gracias por participar" not in texto
    assert "Seguir votando" in texto


# --- volver a una categoria ya votada --------------------------------------

def test_con_todas_puestas_solo_queda_el_de_cambiar():
    """**El mensaje decia que se podia cambiar el voto y no habia por
    donde**: el resumen era solo texto y «Seguir votando» busca la primera
    SIN votar, asi que con todas puestas no llevaba a ningun sitio."""
    filas = votacion._teclado_resumen(_todas()).inline_keyboard

    assert len(filas) == 1
    assert filas[0][0].callback_data == "cam:0"


def test_a_medias_estan_los_dos():
    filas = votacion._teclado_resumen({0: "x"}).inline_keyboard

    assert [f[0].callback_data for f in filas] == ["seguir", "cam:0"]


def test_sin_votar_nada_no_hay_nada_que_cambiar():
    filas = votacion._teclado_resumen({}).inline_keyboard

    assert [f[0].callback_data for f in filas] == ["seguir"]


def test_las_categorias_salen_de_cinco_en_cinco():
    """**No una lista de veintinueve botones**, que es un muro. Paginadas,
    con la misma forma que los nominados."""
    filas = votacion._teclado_cambiar(_todas(), 0).inline_keyboard

    categorias = [f for f in filas if f[0].callback_data.startswith("c:")]
    assert len(categorias) == 5
    assert [f[0].callback_data for f in categorias] == [f"c:{i}" for i in range(5)]
    assert all(len(f) == 1 for f in categorias), "los nombres son largos"

    paso = filas[-2]
    assert [b.text for b in paso] == ["1/6", "›"], "en la primera no hay ‹"
    assert filas[-1][0].callback_data == "r", "y se vuelve al resumen"


def test_en_la_ultima_pagina_no_sobran_botones():
    """29 categorias en paginas de cinco: la ultima lleva cuatro."""
    filas = votacion._teclado_cambiar(_todas(), 5).inline_keyboard

    categorias = [f for f in filas if f[0].callback_data.startswith("c:")]
    assert [f[0].callback_data for f in categorias] == [
        "c:25", "c:26", "c:27", "c:28"]
    assert [b.text for b in filas[-2]] == ["‹", "6/6"], "en la ultima no hay ›"


def test_una_pagina_de_mas_no_revienta():
    """El boton puede venir de un mensaje viejo con mas categorias."""
    filas = votacion._teclado_cambiar(_todas(), 99).inline_keyboard

    assert filas[0][0].callback_data == "c:25", "se queda en la ultima"


def test_los_botones_dicen_cual_esta_votada():
    """La marca es la misma que en la lista del resumen, para no mirar en
    dos sitios."""
    filas = votacion._teclado_cambiar({0: "x"}, 0).inline_keyboard

    assert filas[0][0].text.startswith(votacion.MARCA)
    assert filas[1][0].text.startswith("▫️")


def test_viniendo_a_cambiar_los_botones_lo_llevan_escrito():
    """**No se guarda en ningun sitio de donde vienes**: viaja pegado al
    boton. Lo guardado se pierde en cuanto el bot se reinicia, y entonces
    el siguiente toque te manda a otra parte sin saber por que."""
    filas = votacion._teclado(0, 0, None, cambiando=True).inline_keyboard
    nominados = [f for f in filas if f[0].callback_data.startswith("v:")]

    assert all(f[0].callback_data.endswith(":c") for f in nominados)
    paso = [b for f in filas for b in f if b.callback_data.startswith("p:")]
    assert all(b.callback_data.endswith(":c") for b in paso)


def test_viniendo_a_cambiar_no_se_ofrece_saltar():
    """Saltar no pinta nada en una que ya votaste: lo que hace falta es
    poder irse sin tocarla."""
    filas = votacion._teclado(5, 0, "x", cambiando=True).inline_keyboard
    ultima = filas[-1]

    assert [b.text for b in ultima] == ["↩ Volver", "Mis votos"]
    assert ultima[0].callback_data == "cam:1", "la pagina donde esta la 5"


def test_votando_normal_no_cambia_nada():
    """La vuelta de siempre --votar del tiron-- se queda igual."""
    filas = votacion._teclado(0, 0, None).inline_keyboard
    nominados = [f for f in filas if f[0].callback_data.startswith("v:")]

    assert not any(f[0].callback_data.endswith(":c") for f in nominados)
    assert filas[-1][0].text == "Saltar ⏭"


# --- el cierre -------------------------------------------------------------

def test_antes_de_la_fecha_esta_abierta(monkeypatch):
    monkeypatch.setattr(votacion, "CIERRA_EL",
                        votacion.ahora() + timedelta(days=1))
    assert votacion.cerrada() is False


def test_pasada_la_fecha_esta_cerrada(monkeypatch):
    monkeypatch.setattr(votacion, "CIERRA_EL",
                        votacion.ahora() - timedelta(minutes=1))
    assert votacion.cerrada() is True


def test_sin_fecha_no_cierra_sola(monkeypatch):
    monkeypatch.setattr(votacion, "CIERRA_EL", None)
    assert votacion.cerrada() is False


def test_la_fecha_se_lee_en_hora_de_casa():
    """Railway corre en UTC: sin zona, «el 9 a medianoche» cerraria a las
    dos de la madrugada del 10 para quien vota desde España."""
    leida = config._cuando_cierra("2026-11-09 23:59")
    assert leida == datetime(2026, 11, 9, 23, 59, tzinfo=config.CASA)
    assert config._cuando_cierra("2026-11-09").hour == 0
    assert config._cuando_cierra("lo que sea") is None
    assert config._cuando_cierra("") is None


def test_los_grupos_se_leen_como_los_de_los_otros_bots():
    assert config._grupos("-1002064045581, @otro") == ["-1002064045581", "@otro"]
    assert config._grupos("") == []
