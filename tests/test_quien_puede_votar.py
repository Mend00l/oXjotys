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


class _BotQueEscribe:
    def __init__(self):
        self.dicho = []

    async def send_message(self, quien, texto, **k):
        self.dicho.append((quien, texto))


def _cambio(estaba, esta, chat_id=-1001234567890, tipo="supergroup",
            titulo="Pruebas"):
    """Un `my_chat_member` de mentira, con lo poco que se mira."""
    chat = type("Chat", (), {"id": chat_id, "type": tipo, "title": titulo})()
    return type("Update", (), {
        "my_chat_member": type("C", (), {
            "chat": chat,
            "old_chat_member": type("M", (), {"status": estaba})(),
            "new_chat_member": type("M", (), {"status": esta})(),
        })()})()


async def test_al_meterlo_en_un_grupo_dice_su_numero(monkeypatch):
    """**El numero de un grupo no se ve por ningun lado** y es lo unico
    que hace falta para GRUPOS. Preguntarselo a Telegram no vale: para
    eso el bot tiene que estar ya dentro."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    bot = _BotQueEscribe()
    contexto = type("Ctx", (), {"bot": bot})()

    await socios.me_han_metido(_cambio("left", "member"), contexto)

    quien, texto = bot.dicho[0]
    assert quien == 7710010
    assert "-1001234567890" in texto
    assert "Pruebas" in texto
    assert "GRUPOS" in texto


async def test_al_sacarlo_tambien_se_dice(monkeypatch):
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    bot = _BotQueEscribe()
    contexto = type("Ctx", (), {"bot": bot})()

    await socios.me_han_metido(_cambio("member", "kicked"), contexto)

    assert "sacado" in bot.dicho[0][1]


async def test_un_ascenso_a_administrador_no_se_canta(monkeypatch):
    """Si no, cada vez que se le toca un permiso al bot llega un aviso
    con un numero que ya se tenia."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    bot = _BotQueEscribe()
    contexto = type("Ctx", (), {"bot": bot})()

    await socios.me_han_metido(_cambio("member", "administrator"), contexto)

    assert bot.dicho == []


async def test_lo_de_un_chat_privado_no_cuenta(monkeypatch):
    """Un «me han metido» de un chat de una persona no es un grupo."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    bot = _BotQueEscribe()
    contexto = type("Ctx", (), {"bot": bot})()

    await socios.me_han_metido(
        _cambio("left", "member", chat_id=7710010, tipo="private"), contexto)

    assert bot.dicho == []


async def test_a_los_demas_se_les_sigue_preguntando(monkeypatch):
    """Y si el bot no esta en el grupo, no pasa nadie: dar por bueno a
    alguien porque Telegram no contesta abriria la votacion entera."""
    monkeypatch.setattr(socios, "ADMIN_ID", 7710010)
    monkeypatch.setattr(socios, "GRUPOS", ["-1002064045581"])
    socios._memoria.clear()
    bot = _Bot()

    assert not await socios.puede_votar(bot, 999999)
    assert bot.preguntas == 1
