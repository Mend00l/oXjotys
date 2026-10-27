"""Los aciertos: un punto por categoria clavada.

Lo que se vigila aqui:

  - **Sin ganadores apuntados no se contesta nada**, ni los propios ni la
    clasificacion. Un cero antes de la gala no significa «fallaste
    todas», significa «todavia no», y decirlo mal es peor que callarse.
  - **Una categoria sin resolver no es un fallo.** Durante la gala se van
    sabiendo de una en una y el marcador es parcial a proposito.
  - `/puntos` no suelta veintidos lineas en un grupo.

Las consultas se probaron contra un PostgreSQL de verdad el 27-oct-2026
--el ultimo alias gana, el alias vacio va al final, corregir un ganador
recalcula--; aqui se prueba lo que se le dice a la gente.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import aciertos  # noqa: E402


class _Mensaje:
    def __init__(self):
        self.dicho = []

    async def reply_text(self, texto, **k):
        self.dicho.append(texto)


def _update(mensaje, usuario=1, privado=True):
    return type("U", (), {
        "effective_message": mensaje,
        "effective_user": type("Q", (), {"id": usuario})(),
        "effective_chat": type("C", (), {
            "type": "private" if privado else "supergroup"})(),
    })()


# --- la puerta: sin ganadores no se dice nada ---

async def test_sin_ganadores_los_puntos_no_salen(monkeypatch):
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({}))
    mensaje = _Mensaje()
    await aciertos.puntos(_update(mensaje), None)
    assert "Todavía no" in mensaje.dicho[0]


async def test_sin_ganadores_la_clasificacion_no_sale(monkeypatch):
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({}))
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje), None)
    assert "Todavía no" in mensaje.dicho[0]


async def test_los_puntos_en_un_grupo_mandan_a_privado(monkeypatch):
    """Y **sin consultar la base**: en el grupo no se cuenta nada."""
    monkeypatch.setattr(aciertos.banco, "ganadores", _revienta)
    mensaje = _Mensaje()
    await aciertos.puntos(_update(mensaje, privado=False), None)
    assert "privado" in mensaje.dicho[0]


# --- lo que ve cada uno ---

def test_la_categoria_sin_resolver_no_es_un_fallo():
    texto = aciertos._texto_de_los_mios(
        [(0, "Clavada", "Clavada"), (1, "Mi voto", "El que gano"),
         (2, "Sin saber", None)], cuantas_resueltas=2)
    assert "Tus aciertos: 1" in texto
    assert "de 2 categorías" in texto
    assert "Te queda 1 categoría por resolver" in texto
    assert "❌" in texto and "ganó: El que gano" in texto


def test_las_que_faltan_van_juntas_en_una_linea():
    """A mitad de gala faltan casi todas: una linea, no veinte."""
    texto = aciertos._texto_de_los_mios(
        [(0, "Clavada", "Clavada")] + [(i, "X", None) for i in range(1, 20)],
        cuantas_resueltas=1)
    assert "Te quedan 19 categorías por resolver" in texto
    assert texto.count("⏳") == 1


def test_una_sola_categoria_resuelta_se_dice_en_singular():
    texto = aciertos._texto_de_los_mios([(0, "X", "X")], cuantas_resueltas=1)
    assert "de 1 categoría ya resuelta</i>" in texto


def test_el_que_no_ha_votado_no_recibe_un_cero():
    texto = aciertos._texto_de_los_mios([], cuantas_resueltas=22)
    assert "ningún voto tuyo" in texto
    assert "0" not in texto.split("\n")[0]


def test_en_un_acierto_no_se_repite_el_nombre_dos_veces():
    """Lo votado y lo que gano son lo mismo: se escribe una vez."""
    texto = aciertos._texto_de_los_mios([(0, "Zumbido", "Zumbido")],
                                        cuantas_resueltas=1)
    assert texto.count("Zumbido") == 1


# --- la clasificacion ---

def _tabla(cuantos):
    return [(numero, f"gente{numero:03d}", cuantos - numero)
            for numero in range(cuantos)]


def test_las_tres_primeras_llevan_medalla():
    texto = aciertos._texto_de_la_tabla(
        [(1, "edu", 9), (2, "pepe", 8), (3, "ana", 7), (4, "juan", 5)],
        cuantas_resueltas=22, completo=False)
    assert "🥇 edu" in texto and "🥈 pepe" in texto and "🥉 ana" in texto
    assert "4. juan" in texto


def test_quien_no_dejo_nombre_sale_como_alguien():
    texto = aciertos._texto_de_la_tabla([(1, None, 3)],
                                        cuantas_resueltas=5, completo=False)
    assert "Alguien" in texto


def test_la_publica_se_corta_y_dice_cuantos_faltan():
    texto = aciertos._texto_de_la_tabla(_tabla(25), cuantas_resueltas=22,
                                        completo=False)
    assert "y 5 más" in texto
    assert "gente019" in texto      # el vigesimo si sale
    assert "gente020" not in texto  # el vigesimoprimero no


def test_edu_la_ve_entera():
    texto = aciertos._texto_de_la_tabla(_tabla(25), cuantas_resueltas=22,
                                        completo=True)
    assert "más" not in texto
    assert "gente024" in texto


def test_justo_veinte_no_dice_que_falte_nadie():
    texto = aciertos._texto_de_la_tabla(_tabla(20), cuantas_resueltas=22,
                                        completo=False)
    assert "más" not in texto


# --- utilidades de la prueba ---

def _devuelve(valor):
    async def _fingir(*a, **k):
        return valor
    return _fingir


async def _revienta(*a, **k):
    raise AssertionError("no se debe consultar la base para esto")
