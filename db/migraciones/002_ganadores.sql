-- Quien gano de verdad en los Golden Joystick, uno por categoria.
--
-- **Se guarda el texto del nominado, igual que en `votos`**, y no su
-- numero de orden. Asi un acierto es comparar dos textos que salieron
-- los dos del mismo `premios.json`. Si aqui fuera el indice y algun dia
-- el fichero cambiara de orden, los aciertos saldrian mal y **sin dar
-- ningun error**: cada uno seguiria teniendo un numero, solo que el que
-- no es.
--
-- Una categoria sin fila es una categoria **sin resolver**, que no es lo
-- mismo que una categoria que nadie acerto. Los Golden Joystick no
-- cantan los premios todos a la vez, y mientras dura la gala hay que
-- poder contar lo que ya se sabe sin que lo que falta cuente como fallo.
CREATE TABLE IF NOT EXISTS ganadores (
    categoria  SMALLINT    PRIMARY KEY,
    nominado   TEXT        NOT NULL,
    puesto_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);
