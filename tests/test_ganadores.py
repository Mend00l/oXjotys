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


# --- el sorteo del premio ---
# Edu lo decidio asi el 27-oct: empate arriba, uno al azar. Y el empate
# **es lo normal**, no el caso raro: con las 22 categorias de verdad sale
# empate entre el 48 y el 65% de las veces.

_TABLA = [(50, "ana", 19), (10, "edu", 19), (30, None, 19),
          (20, "pepe", 18), (40, "juan", 3)]


def test_solo_entran_los_de_la_mejor_nota():
    mejor, empatados = ganadores._empatados_arriba(_TABLA)
    assert mejor == 19
    assert [u for u, _ in empatados] == [10, 30, 50]


def test_la_lista_va_ordenada_y_no_como_venga_de_la_base():
    """Si la lista de partida baila, el sorteo no se puede repetir."""
    mejor, unos = ganadores._empatados_arriba(_TABLA)
    _, otros = ganadores._empatados_arriba(list(reversed(_TABLA)))
    assert unos == otros


def test_quien_no_dejo_alias_entra_con_su_nombre_de_pega():
    _, empatados = ganadores._empatados_arriba(_TABLA)
    assert (30, ganadores.SIN_NOMBRE) in empatados


def test_se_puede_dejar_a_alguien_fuera():
    """El dueño pone el premio: por defecto no se lo sortea a si mismo."""
    mejor, empatados = ganadores._empatados_arriba(_TABLA, fuera=(10,))
    assert mejor == 19
    assert [u for u, _ in empatados] == [30, 50]


def test_dejar_fuera_al_unico_de_arriba_baja_la_nota():
    mejor, empatados = ganadores._empatados_arriba(
        [(1, "edu", 20), (2, "ana", 7)], fuera=(1,))
    assert mejor == 7
    assert [u for u, _ in empatados] == [2]


def test_sin_nadie_no_revienta():
    assert ganadores._empatados_arriba([], fuera=()) == (0, [])
    assert ganadores._empatados_arriba([(1, "edu", 5)], fuera=(1,)) == (0, [])


def test_el_sorteo_se_repite_con_la_misma_semilla():
    """**Es para lo que sirve la semilla**: un `random.choice` a secas sale
    igual de limpio y no hay forma de demostrarlo."""
    _, empatados = ganadores._empatados_arriba(_TABLA)
    uno = ganadores._sortear(empatados, "2026-11-11")
    otro = ganadores._sortear(empatados, "2026-11-11")
    assert uno == otro
    assert uno in empatados


def test_con_otra_semilla_puede_salir_otro():
    """No se exige que cambie --son tres y puede repetir-- pero con
    bastantes semillas tienen que salir todos."""
    _, empatados = ganadores._empatados_arriba(_TABLA)
    salen = {ganadores._sortear(empatados, str(n))[0] for n in range(200)}
    assert salen == {10, 30, 50}


def test_con_uno_solo_sale_ese():
    assert ganadores._sortear([(7, "ana")], "da-igual") == (7, "ana")
