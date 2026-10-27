"""La herramienta de los ganadores, lo que no toca ni base ni Google.

Importa: **el vuelco al Sheet corre una sola vez**, el dia de la gala, y
sobre el documento compartido con los votos de ofertasXbot y los puntos
de Marcy. Lo que se prueba aqui es que no lo pise:

  - una pestaña con otra cabecera **no se toca**;
  - `update` se llama con los argumentos **nombrados**, que gspread 6
    cambio el orden y sin nombrarlos escribe en columnas que no son;
  - la pestaña se vacia antes, para que una tabla mas corta no deje
    filas viejas debajo haciendose pasar por nuevas.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herramientas import ganadores  # noqa: E402


class _Pestana:
    """Una pestaña de pega que apunta lo que le piden."""

    def __init__(self, cabecera=None, titulo="oXJOTYs"):
        self.title = titulo
        self._cabecera = cabecera or []
        self.vaciada = False
        self.escrito = None

    def row_values(self, fila):
        return self._cabecera

    def clear(self):
        self.vaciada = True

    def update(self, values=None, range_name=None, **k):
        assert values is not None, "los valores van nombrados"
        assert range_name is not None, "el rango va nombrado"
        self.escrito = (values, range_name)


# --- los pares de la linea de comandos ---

def test_un_par_mal_escrito_para_el_script():
    with pytest.raises(SystemExit):
        ganadores._leer_pares(["0:2", "esto-no"])


def test_los_pares_salen_como_numeros():
    assert ganadores._leer_pares(["0:2", "13:0"]) == [(0, 2), (13, 0)]


# --- las filas que van al Sheet ---

def test_quien_no_dejo_nombre_va_como_alguien():
    """**El mismo nombre que en la clasificacion del bot**, no una copia:
    si se cambia uno, el documento y la tabla dejan de llamar igual a la
    misma persona."""
    filas = ganadores._filas([(7, None, 3)], resueltas=22, cuando="hoy")
    assert filas == [["7", ganadores.SIN_NOMBRE, "3", "22", "hoy"]]


def test_todo_va_en_texto():
    """Nada de numeros: lo que se escribe sin interpretar se lee igual."""
    filas = ganadores._filas([(7, "edu", 3)], resueltas=22, cuando="hoy")
    assert all(isinstance(celda, str) for celda in filas[0])


# --- el vuelco ---

def test_una_pestana_vacia_se_escribe_entera():
    hoja = _Pestana()
    ganadores._volcar(hoja, [["1", "edu", "9", "22", "hoy"]])
    valores, rango = hoja.escrito
    assert hoja.vaciada
    assert valores[0] == ganadores.TITULOS
    assert rango == "A1:E2"


def test_la_pestana_de_los_aciertos_se_reconoce_por_su_cabecera():
    hoja = _Pestana(cabecera=list(ganadores.TITULOS))
    ganadores._volcar(hoja, [["1", "edu", "9", "22", "hoy"]])
    assert hoja.escrito is not None


def test_una_pestana_de_otro_no_se_toca():
    hoja = _Pestana(cabecera=["mes", "usuario", "nombre", "puntos"],
                    titulo="Marcy")
    with pytest.raises(SystemExit):
        ganadores._volcar(hoja, [["1", "edu", "9", "22", "hoy"]])
    assert not hoja.vaciada
    assert hoja.escrito is None


def test_el_rango_crece_con_las_filas():
    hoja = _Pestana()
    ganadores._volcar(hoja, [["1", "a", "1", "22", "hoy"]] * 30)
    assert hoja.escrito[1] == "A1:E31"
