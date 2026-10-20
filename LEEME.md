# Votación de los Golden Joystick

Bot de Telegram para que la gente de los grupos vote los premios. Se
vota **en privado**, una categoría cada vez, a botonazos.

**21 categorías y 168 nominados**, de la edición de 2026. La votación
oficial cerró el 23 de octubre y los ganadores se anuncian el 11 de
noviembre: esta es la nuestra, con sus fechas.

## Cómo se vota

Se le escribe al bot y él va sacando categorías. Cada nominado es un
botón; al tocarlo **se guarda y salta a la siguiente**. No hay pantalla
de confirmación a propósito: son veintiuna y cada toque de más es gente
que abandona.

- **Se guarda al tocar, no al final.** Quien lo deje a medias vuelve y
  retoma por lo que le falta, aunque sea días después.
- **Se puede cambiar** hasta que cierre. El voto anterior se sustituye.
- **Ocho nominados por pantalla.** La mayoría de categorías tienen seis,
  así que casi todas se resuelven sin pasar página; la de veinte son
  tres páginas.
- **Se puede saltar** una categoría. Mejor eso que votar al azar por
  salir del paso.

## Quién puede votar

Solo quien esté en alguno de los grupos de `GRUPOS`. Se le pregunta a
Telegram, así que **el bot tiene que estar metido en cada grupo** —y en
un canal, además, como administrador—.

Esto no hace imposible hacer trampas: quien tenga tres cuentas vota tres
veces. Lo que hace es que para votar mil haya que meter mil cuentas en
el grupo, y eso se ve. Como efecto secundario, quien quiera votar y no
esté, se une.

## Comandos

| Comando | Quién | Qué hace |
|---|---|---|
| `/votar` o `/start` | cualquiera | empieza o retoma la votación |
| `/recuento` | solo Edu | cómo va, categoría por categoría |
| `/estado` | solo Edu | si está abierta y cuánta gente ha votado |

**El recuento es solo para Edu y en privado**, a propósito: enseñar el
marcador a mitad de votación arrastra el voto, que la gente vota a lo
que va ganando.

## El cierre

Se pone una fecha en `CIERRA_EL` y se cierra sola. A partir de ahí no se
admiten votos y el bot le manda el resultado a Edu **con un botón para
publicarlo** donde diga `PUBLICAR_EN`. No se publica solo: el resultado
se lee antes de salir, por si hay que corregir algo o contar algo al
lado.

Las categorías **«nuestras»** las elige Edu y el bot no las vota ni las
cuenta: se escriben en el mensaje al publicarlo.

## Montarlo en local

    py -3.12 -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env     # y se rellenan los valores
    python main.py

Las pruebas:

    venv\Scripts\python.exe -m pytest

## En Railway

Un **servicio** apuntando a este repo, más una **base de datos**:
*New → Database → Postgres*, que deja puesta la variable `DATABASE_URL`.

**No lleva `railway.toml` a propósito.** Railway lo retira el 1 de
diciembre de 2026, así que esto se configura en el panel.

    Start command:  python main.py

| Variable | De dónde sale |
|---|---|
| `TELEGRAM_TOKEN` | lo da BotFather |
| `ADMIN_ID` | tu id de Telegram, en números |
| `DATABASE_URL` | la pone Railway al crear la base |
| `GRUPOS` | los grupos que pueden votar, por comas |
| `CIERRA_EL` | `2026-11-09 23:59`, en hora de España |
| `PUBLICAR_EN` | dónde se ofrece publicar el resultado |
| `ENLACE_DEL_GRUPO` | lo que se le enseña a quien no está |

## Tres cosas que se dan por sabidas

**Los votos van en una base de datos y no en una hoja de cálculo.**
Votar las 21 categorías son 21 escrituras por persona, y el cupo de
Google —300 por minuto— lo comparten los otros cuatro bots con la misma
cuenta de servicio. Quince personas votando a la vez se lo comen, y lo
que se rompe entonces no es esto: es Miss apuntando un aviso.

**La fecha de cierre va en hora de España.** Railway corre en UTC: sin
zona, «el 9 a medianoche» cerraría a las dos de la madrugada del 10.

**La zona va en el disparador, no solo en el planificador.** Un
disparador construido a mano coge la de la máquina. Costó una tarde en
ofertasXbot.
