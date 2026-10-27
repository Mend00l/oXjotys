"""Lo que no puede romperse en la votacion.

Son veintidos categorias y 180 nominados: lo que se comprueba aqui es
que nadie se pierda por el camino --que la paginacion cuadre, que quien
lo deje a medias retome por lo que le falta y que un boton viejo no
cuele un voto que no es--.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from bot import premios, votacion  # noqa: E402


# --- la lista -------------------------------------------------------------

def test_estan_las_veintidos_categorias():
    """Si alguien toca premios.json y se deja media lista, se ve aqui y no
    en mitad de la votacion.

    Eran 21 hasta el 27-oct-2026, cuando se añadio «Juego del Año ·
    Absoluto» --la Ultimate Game of the Year, que alli se anuncia aparte y
    mas tarde-- con sus 12 nominados.
    """
    assert premios.cuantas() == 22
    assert sum(len(c["nominados"]) for c in premios.CATEGORIAS) == 180


def test_la_nueva_va_la_ultima():
    """**El orden es la clave de cada categoria**, y los votos guardados
    apuntan a ese numero. Meter una nueva por el medio --o delante, que es
    donde iria por importancia-- renumeraria las de detras y cada voto ya
    dado pasaria a contar en otra categoria."""
    assert premios.nombre_de(0) == "Juego del Año · PC"
    assert premios.nombre_de(20) == "El más esperado"
    assert premios.nombre_de(21) == "Juego del Año · Absoluto"


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


def test_la_primera_pagina_no_tiene_flecha_atras():
    larga = max(range(premios.cuantas()),
                key=lambda i: len(premios.categoria(i)["nominados"]))
    rotulos = [b.text for fila in votacion._teclado(larga, 0, None).inline_keyboard
               for b in fila]
    assert "›" in rotulos and "‹" not in rotulos


def test_la_ultima_pagina_no_tiene_flecha_adelante():
    larga = max(range(premios.cuantas()),
                key=lambda i: len(premios.categoria(i)["nominados"]))
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
    assert "Golden Joystick Awards" in texto
    assert "hasta que cierre" in texto


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
    """**No una lista de veintitres botones**, que es un muro. Paginadas,
    con la misma forma que los nominados."""
    filas = votacion._teclado_cambiar(_todas(), 0).inline_keyboard

    categorias = [f for f in filas if f[0].callback_data.startswith("c:")]
    assert len(categorias) == 5
    assert [f[0].callback_data for f in categorias] == [f"c:{i}" for i in range(5)]
    assert all(len(f) == 1 for f in categorias), "los nombres son largos"

    paso = filas[-2]
    assert [b.text for b in paso] == ["1/5", "›"], "en la primera no hay ‹"
    assert filas[-1][0].callback_data == "r", "y se vuelve al resumen"


def test_en_la_ultima_pagina_no_sobran_botones():
    """22 categorias en paginas de cinco: la ultima lleva dos."""
    filas = votacion._teclado_cambiar(_todas(), 4).inline_keyboard

    categorias = [f for f in filas if f[0].callback_data.startswith("c:")]
    assert [f[0].callback_data for f in categorias] == ["c:20", "c:21"]
    assert [b.text for b in filas[-2]] == ["‹", "5/5"], "en la ultima no hay ›"


def test_una_pagina_de_mas_no_revienta():
    """El boton puede venir de un mensaje viejo con mas categorias."""
    filas = votacion._teclado_cambiar(_todas(), 99).inline_keyboard

    assert filas[0][0].callback_data == "c:20", "se queda en la ultima"


def test_los_botones_dicen_cual_esta_votada():
    """La marca es la misma que en la lista del resumen, para no mirar en
    dos sitios."""
    filas = votacion._teclado_cambiar({0: "x"}, 0).inline_keyboard

    assert filas[0][0].text.startswith(votacion.MARCA)
    assert filas[1][0].text.startswith("▫️")


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
