"""`/ranking`: el resultado, para todo el mundo, pero no antes de tiempo.

**Hay dos razones distintas para no enseñarlo**, y por eso la fecha no es
la de cierre:

  - Antes de cerrar, ver el marcador arrastra el voto: la gente vota a lo
    que va ganando.
  - Y entre el cierre --el 9-- y la gala --el 11-- seria destripar lo que
    todavia no se sabe.
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import recuento  # noqa: E402


class _Mensaje:
    def __init__(self):
        self.dicho = []

    async def reply_text(self, texto, **k):
        self.dicho.append(texto)


def _update(mensaje):
    return type("U", (), {
        "effective_message": mensaje,
        "effective_user": type("Q", (), {"id": 1})(),
    })()


async def test_antes_de_la_fecha_no_se_enseña(monkeypatch):
    monkeypatch.setattr(recuento, "RANKING_DESDE",
                        recuento.ahora() + timedelta(days=2))
    mensaje = _Mensaje()

    await recuento.ranking(_update(mensaje), None)

    assert "Todavía no" in mensaje.dicho[0]
    assert "Golden Joystick" in mensaje.dicho[0]


async def test_desde_la_fecha_sale_el_recuento(monkeypatch):
    monkeypatch.setattr(recuento, "RANKING_DESDE",
                        recuento.ahora() - timedelta(minutes=1))

    async def _recuento():
        return {0: [("Big Walk", 7), ("Valheim", 3)]}

    async def _gente():
        return 10

    monkeypatch.setattr(recuento.banco, "recuento", _recuento)
    monkeypatch.setattr(recuento.banco, "cuanta_gente", _gente)
    mensaje = _Mensaje()

    await recuento.ranking(_update(mensaje), None)

    todo = "\n".join(mensaje.dicho)
    assert "Recuento" in todo
    assert "10 personas han votado" in todo
    assert "🥇 Big Walk" in todo


async def test_el_ranking_no_es_solo_para_edu(monkeypatch):
    """A diferencia de `/recuento`, que si lo es: este lo pide cualquiera
    y por eso tiene su propia fecha."""
    monkeypatch.setattr(recuento, "ADMIN_ID", 999)
    monkeypatch.setattr(recuento, "RANKING_DESDE",
                        recuento.ahora() - timedelta(minutes=1))

    async def _recuento():
        return {}

    async def _gente():
        return 0

    monkeypatch.setattr(recuento.banco, "recuento", _recuento)
    monkeypatch.setattr(recuento.banco, "cuanta_gente", _gente)
    mensaje = _Mensaje()

    await recuento.ranking(_update(mensaje), None)

    assert mensaje.dicho, "alguien que no es Edu tiene que verlo"
