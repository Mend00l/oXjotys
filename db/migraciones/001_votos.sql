-- Los votos, uno por persona y categoria.
--
-- **La clave es (usuario, categoria) y por eso se puede cambiar el voto**:
-- votar otra vez sustituye el anterior en vez de sumar uno nuevo. Sin esa
-- clave habria que borrar antes de escribir, que son dos pasos donde se
-- cuela un voto duplicado el dia que dos toques lleguen pegados.
--
-- La categoria se guarda por su NUMERO de orden y el nominado por su
-- texto. El numero porque corregir el nombre de una categoria no puede
-- invalidar los votos ya dados; el texto porque un nominado que cambie de
-- sitio en el fichero dejaria de ser el mismo si se guardara su indice, y
-- eso se descubriria al contar, cuando ya no tiene arreglo.
CREATE TABLE IF NOT EXISTS votos (
    usuario_id  BIGINT      NOT NULL,
    categoria   SMALLINT    NOT NULL,
    nominado    TEXT        NOT NULL,
    alias       TEXT,
    votado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, categoria)
);

-- Para el recuento, que agrupa por categoria.
CREATE INDEX IF NOT EXISTS votos_por_categoria ON votos (categoria);
