"""Que el bot no se quede sordo sin que se entere nadie.

**El que recoge los mensajes es una tarea aparte.** Si se muere, el
proceso sigue vivo: Railway lo ve verde, el registro se queda mudo y la
gente escribe al bot sin que conteste. Paso el 26-oct-2026 --dos
`Conflict` al desplegar y 24 horas sin poder votar-- y no lo dijo nadie.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402


class _Updater:
    """Uno que deja de escuchar a la tercera vuelta."""

    def __init__(self, aguanta: int | None):
        self.aguanta = aguanta          # None = no se para nunca
        self.vueltas = 0

    @property
    def running(self) -> bool:
        self.vueltas += 1
        return self.aguanta is None or self.vueltas <= self.aguanta


def _app(aguanta: int | None):
    return type("App", (), {"updater": _Updater(aguanta)})()


async def test_si_deja_de_escuchar_el_bot_se_cierra(monkeypatch):
    """Cerrarse es la gracia: asi Railway lo levanta otra vez. Quedarse
    vivo y mudo es lo que costo un dia de votacion."""
    monkeypatch.setattr(main, "VIGILA", 0)
    app = _app(aguanta=2)

    with pytest.raises(SystemExit):
        await main._vigilar(app)

    assert app.updater.vueltas == 3


async def test_mientras_escuche_no_se_cierra(monkeypatch):
    """Y no se cierra por su cuenta: solo cuando el que escucha se ha
    parado de verdad."""
    import asyncio

    monkeypatch.setattr(main, "VIGILA", 0)
    app = _app(aguanta=None)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(main._vigilar(app), timeout=0.05)


async def test_el_conflict_se_cuenta_en_cristiano(caplog):
    """Su texto en ingles no dice como se arregla: hay dos procesos con el
    mismo token."""
    from telegram.error import Conflict

    contexto = type("C", (), {"error": Conflict("terminated by other getUpdates")})()
    with caplog.at_level("ERROR"):
        await main.se_rompio(None, contexto)

    assert "mismo token" in caplog.text
    assert "Traceback" not in caplog.text
