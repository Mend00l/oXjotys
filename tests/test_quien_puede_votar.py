"""Quien pasa el filtro de los grupos y quien no."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import socios  # noqa: E402


class _Bot:
    """Uno que no esta en ningun grupo, como el de verdad mientras se
    prueba: Telegram contesta «chat not found» a todo."""

    def __init__(self):
        self.preguntas = 0

    async def get_chat_member(self, chat_id, user_id):
        self.preguntas += 1
        raise RuntimeError("Bad Request: chat not found")


async def test_el_dueno_vota_siempre(monkeypatch):
    """**Para preguntar si alguien esta en un grupo, el bot tiene que
    estar ya dentro.** O sea que sin esto, probar la votacion obliga a
    meterlo en la comunidad antes de tiempo. Paso el 27-oct-2026."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    monkeypatch.setattr(socios, "GRUPOS", ["-1002064045581"])
    socios._memoria.clear()
    bot = _Bot()

    assert await socios.puede_votar(bot, 7710010)
    assert bot.preguntas == 0, "a Telegram ni se le pregunta"


async def test_a_los_demas_se_les_sigue_preguntando(monkeypatch):
    """Y si el bot no esta en el grupo, no pasa nadie: dar por bueno a
    alguien porque Telegram no contesta abriria la votacion entera."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    monkeypatch.setattr(socios, "GRUPOS", ["-1002064045581"])
    socios._memoria.clear()
    bot = _Bot()

    assert not await socios.puede_votar(bot, 999999)
    assert bot.preguntas == 1
