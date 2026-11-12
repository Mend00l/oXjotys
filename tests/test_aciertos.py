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

# Un ADMIN_ID de mentira. `_es_edu` lee el global del modulo en cada
# llamada, asi que se puede sustituir con monkeypatch.
DUENO = 4242


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
    assert mensaje.dicho[0] == aciertos.TODAVIA_NO


async def test_sin_ganadores_la_clasificacion_no_sale(monkeypatch):
    """**Al dueño**, que desde el 12-nov-2026 es el unico que la pide."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({}))
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO), None)
    assert mensaje.dicho[0] == aciertos.TODAVIA_NO


# --- la clasificacion es solo del dueño (12-nov-2026) ---
#
# El alias que se guarda es `username or full_name`: para quien tiene
# nombre de usuario en Telegram, la tabla ES una lista de handles con los
# que escribirse. Edu la cerro por eso.

async def test_la_clasificacion_no_se_la_doy_a_cualquiera(monkeypatch):
    """**Y sin tocar la base**: a quien no es el dueño no se le cuenta nada."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    monkeypatch.setattr(aciertos.banco, "ganadores", _revienta)
    monkeypatch.setattr(aciertos.banco, "clasificacion", _revienta)
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO + 1), None)
    assert mensaje.dicho[0] == aciertos.SOLO_EL_DUENO


async def test_al_que_no_es_el_dueno_le_contesta_igual_haya_ganadores(monkeypatch):
    """**La respuesta no puede delatar si ya se apuntaron.** Por eso la
    puerta del dueño va antes que la de los ganadores."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({0: "Algo"}))
    monkeypatch.setattr(aciertos.banco, "clasificacion", _revienta)
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO + 1), None)
    assert mensaje.dicho[0] == aciertos.SOLO_EL_DUENO


async def test_la_clasificacion_manda_a_puntos(monkeypatch):
    """Que no se quede en un «no» seco: hay algo que si puede ver."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO + 1), None)
    assert "/puntos" in mensaje.dicho[0]


async def test_ningun_alias_se_escapa_al_que_no_es_el_dueno(monkeypatch):
    """Lo que de verdad se cerro. Si alguna vez vuelve a filtrarse un
    alias por aqui, esta es la que lo caza."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({0: "Algo"}))
    monkeypatch.setattr(aciertos.banco, "clasificacion",
                        _devuelve([(7, "UnAliasQueNoDebeSalir", 5)]))
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO + 1), None)
    assert not any("UnAliasQueNoDebeSalir" in t for t in mensaje.dicho)


async def test_el_dueno_si_ve_la_tabla_entera(monkeypatch):
    """Y **entera**, no recortada a veinte: ya no hay version publica."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", DUENO)
    monkeypatch.setattr(aciertos.banco, "ganadores", _devuelve({0: "Algo"}))
    monkeypatch.setattr(aciertos.banco, "clasificacion", _devuelve(_tabla(25)))
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO), None)
    todo = "\n".join(mensaje.dicho)
    assert "25." in todo
    assert "más</i>" not in todo


async def test_sin_admin_id_no_la_ve_nadie(monkeypatch):
    """Si la variable se queda vacia, `_es_edu` da falso para todos y la
    tabla no sale. **Cerrado de mas, no de menos**, que es el lado por el
    que hay que fallar."""
    monkeypatch.setattr(aciertos, "ADMIN_ID", 0)
    monkeypatch.setattr(aciertos.banco, "ganadores", _revienta)
    mensaje = _Mensaje()
    await aciertos.clasificacion(_update(mensaje, usuario=DUENO), None)
    assert mensaje.dicho[0] == aciertos.SOLO_EL_DUENO


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
    assert aciertos.SIN_NOMBRE in texto


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
