# GlyphFunge

**Frontend geometrico determinista para Befunge-93. Tu describes la trayectoria. Befunge la recorre.**

```text
GlyphFuck resuelve geometria ASCII determinista.
Befunge hace la geometria ejecutable.
GlyphFunge une esas dos ideas.
```

## Explicacion en 30 segundos

Los programas de Befunge-93 son rejillas 2D de instrucciones de un caracter, caminadas por un
puntero de instrucciones que se mueve como una oruga. Escribirlos significa
colocar flecha por flecha en la rejilla — exactamente el tipo de layout espacial
exacto en el que los humanos y los LLMs la regan.

GlyphFunge te deja escribir *trayectorias* en su lugar: rutas nombradas con operaciones de push/add/print,
vueltas, ciclos y ramificaciones. El compilador emite el playfield exacto
de Befunge-93 — un `.bf` real que puedes correr en cualquier interprete de Befunge-93.
Sin runtime, sin VM propia. El compilador solo construye la rejilla; Befunge
la ejecuta.

```
countdown.gf → parser → router (geometria) → validator → countdown.bf → cualquier interprete Befunge-93
```

## Instalar y correr

Sin dependencias. Python ≥ 3.10.

```bash
cd GlyphFunge
python -m glyphfunge compile examples/countdown.gf -o generated/countdown.bf
python -m glyphfunge inspect examples/countdown.gf
python -m glyphfunge run examples/countdown.gf
python -m glyphfunge verify examples/countdown.gf
```

## Por que esto le gana a escribir la rejilla a mano — el countdown

`examples/countdown.gf`:

```text
canvas 12 6
entry main
expect output "5 4 3 2 1 0 "

route main:
    push 5
    turn down
    go 1
    label loop
    turn right
    dup
    print_num
    push 1
    sub
    dup
    branch_zero exit loopback
end

route exit at 7 3 facing down:
    print_num
    halt
end

route loopback at 7 1 facing up:
    turn left
    go 5
    turn down
    goto loop
end
```

compila a este playfield de Befunge-93 (`generated/countdown.bf`):

```
5v
 v<<<<<<
 >:.1-:|
       .
       @
```

Lee el rectangulo: `push 5` arriba a la izquierda, `v` abajo a la linea principal
`>:.1-:|`, y cuando el contador es non-zero el `|` lanza el IP **hacia arriba** al
corredor `<<<<<<`, que lo guia alrededor del ciclo y de vuelta al `>` del
inicio. El ciclo es literalmente visible como un ciclo. Ese es todo el
punto de GlyphFunge.

Output — en el interprete de referencia incluido **y** en el
tercero independiente `befunge.js`:

```
5 4 3 2 1 0
```

## Backend nativo de Code IR (v0.5, capa 2)

GlyphFunge ahora acepta JSON canonico `code-ir/0.1-draft` sin importar
el paquete experimental de Code IR en Python. Esto mantiene el compilador publico
standalone mientras permite que cualquier frontend validado de Code IR lo alimente.

```text
Code IR JSON canonico → fuente de ruta GlyphFunge → Befunge-93 ordinario
```

La capa 2 soporta un `main() -> int` sin parametros, locales declarados `int`,
`Assign` de linea recta, aritmetica literal (`+ - * // %`), cero o mas
sentencias `Emit`, y un `Return` final. Una local leida se expande a la ultima
expresion asignada, asi que el output se mantiene como operaciones de pila nativas de Befunge;
no hay runtime de memoria oculta ni VM privada. Comparaciones enteras y un
`if/else` terminal bajan a operaciones reales de Befunge `!`/`` ` `` y rutas `|`.
Llamadas, ciclos, arrays, maps y strings siguen rechazados hasta que exista su
lowering geometrico nativo.

Para `/` y `%`, los operandos deben ser no-negativos: Code IR especifica division
por piso mientras Befunge es por truncamiento, y esa es la region semantica compartida. Todos
los valores intermedios estan restringidos a rango de 32-bit con signo para evidencia
cross-host.

```bash
python -m glyphfunge compile-ir examples/code_ir_arithmetic.json \
  -o generated/code_ir_arithmetic.bf \
  --gf-output generated/code_ir_arithmetic.gf
```

El fixture reasigna locales y luego emite `24 ` usando operaciones nativas de Befunge.

## Referencia de sintaxis (v0.4)

```text
canvas W H                   # opcional; debe caber en el campo 80x25 de Befunge-93
entry NAME                   # la ruta de entrada siempre empieza en (0, 0) mirando a la derecha
expect output "STRING"       # opcional, usado por `verify`

route NAME:                  # ruta de entrada: no necesita placement
route NAME at X Y facing right|left|up|down:   # todas las demas rutas
    push N                   # N en 0..9  -> digito
    add | sub | mul | div | mod | not | greater
    dup | swap | drop
    print_num | print_char
    print "TEXT"             # modo string: emite " + reverso + " + comas
    label NAME               # punto de union pasable para `goto`
    go N                     # dibuja N flechas continuando recto
    turn right|left|up|down  # una celda de flecha que dobla el IP
    skip                     # '#' trampoline (salta la siguiente celda)
    branch_zero Z NZ         # '|': cero va ABAJO a Z, non-zero ARRIBA a NZ
    goto NAME                # camina recto hacia la ruta/label NAME
    halt                     # '@'; cada ruta debe terminar con halt|goto|branch_zero
end
```

Reglas que el compilador impone en vez de adivinar:

- El brazo **cero** de `branch_zero` debe empezar exactamente una celda **abajo** de la
  ramificacion; el brazo **non-zero** exactamente una celda **arriba**. Eso es lo que `|`
  hace en Befunge-93 — asi que GlyphFunge rechaza cualquier otra geometria.
- `goto` camina recto en la direccion actual y debe entrar a la celda objetivo.
  Si no puede, obtienes `ROUTE_ERROR` con coordenadas, no una sorpresa.
- Dos rutas escribiendo caracteres diferentes en una celda es un `GLYPH_ERROR`
  que nombra ambas rutas y la celda. (Dos rutas compartiendo una celda con el
  *mismo* caracter es un merge legal, inspeccionable.)
- Cada ruta termina en `halt`, `goto` o `branch_zero`.
- `push` solo acepta 0..9 (push de digito Befunge-93; compone numeros mas grandes).

## La bandera: FizzBuzz como pura geometria (v0.2)

`examples/fizzbuzz.gf` — cuatro ramificaciones, diez rutas, una columna compartida de "elevador"
donde cada brazo se encuentra, y un corredor de regreso arriba: como se ve un
if/else-if/else anidado con ciclo cuando el flujo de control es un lugar:

```
1v
 v<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
 v       >:.>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>1+:44*-|
 v   >:5%|            ^                     ^       $
 >:3%|   >" zzuB",,,,,^>" ",>>>>>>>>>>>>>>>>^       @
     >"zziF",,,,>>>>:5%|                    ^
                       >" zzuB",,,,,>>>>>>>>^
```

Output (ambos interpretes concuerdan): `1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz `
— 1,538 pasos, ejercido con brazos Fizz-, Buzz-, FizzBuzz- y de numeros todos
fisicamente distintos corredores.

## Demo de autorreferencia (v0.2)

`examples/meta_befunge.gf` compila a un programa de Befunge que *imprime otro
programa de Befunge valido* (`93+.@`), que imprime `12 `. La cadena se prueba
end-to-end: dos niveles de ejecucion, sin GlyphFunge participando downstream.

```text
meta_befunge.gf → meta_befunge.bf → (corre) → "93+.@" → (corre) → "12 "
```

### Nota honesta sobre self-hosting completo

Escribir el *compilador mismo* de GlyphFunge en Befunge-93 esta fuera del alcance de un
backend Befunge-93: el playfield esta limitado a 80×25 = 2000 celdas, y
el modelo de fuente de GlyphFunge excluye intencionalmente la auto-modificacion `p`/`g`.
Lo que v0.2 si demuestra es el loop de sustrato parando un nivel antes:
texto Befunge emitido por programas de Befunge generados por GlyphFunge. El self-hosting
completo necesitaria un target de clase Befunge-98 — anotado para el roadmap,
no reclamado.

## Lado a lado: aritmetica

`examples/arithmetic.gf` nucleo:

```text
route main:
    push 9
    push 3
    add
    print_num
    halt
end
```

generado `generated/arithmetic.bf`:

```
93+.@
```

output: `12 ` (Befunge-93 `.` imprime el numero seguido de un espacio).

## Evidencia (v0.4, toda reproducible con `python -m glyphfunge verify`)

| ejemplo | playfield | sha256 (.bf generado) | output | referencia | independiente (befunge.js) |
|---|---|---|---|---|---|
| arithmetic | 8x2 | `221797a271b9e7a1bab20a4173a4ea867f85ea11f3d47642537717e71f360266` | `12 ` | PASS, 5 pasos | PASS |
| branch | 8x5 | `d4250e98adfd548928be31d5ec0c13cb0caa86588e766397e3bd7079f8a99490` | `0 ` | PASS, 7 pasos | PASS |
| countdown | 12x6 | `4cb51acb1184e87cab9176644cc8443dbbe51a1c1e15f94c06cea02e67220085` | `5 4 3 2 1 0 ` | PASS, 68 pasos | PASS |
| hello | 30x1 | `753072bf869627c921e722bde32881fa7ffbfe971edc74256b559e0c48dfc4cc` | `Hello, World!` | PASS, 15 pasos | PASS |
| fizzbuzz | 60x8 | `75ce71f83a9a651fd1dbe1b3ce84ad218328c9c1e529eb91ccf7d4d9970fcb4e` | `1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz ` | PASS, 1538 pasos | PASS |
| meta_befunge | 20x2 | `e84bd135ce2f7d14890e135c3deca8d0a7720f6d5e04026e872badb194ce8e80` | `93+.@` | PASS | PASS |
| code_ir_arithmetic | 80x3 | `a60e2bd45dd6a76c12d3c72463357a736730ba81118d143614aa8a4f88a76879` | `24 ` | PASS, 24 pasos | PASS |

Mismo fuente `.gf` siempre produce output `.bf` byte-identico
(probado en pruebas estilo CI, incluyendo un SHA-256 fijado para `countdown.bf`).

## Prueba de ejecucion independiente (sin trampa)

`tests/test_glyphfunge.py` incluye una prueba que entrega cada programa generado
a un interprete tercero de Befunge-93 — el `befunge.js` de
[*Interpret-Esolangs-Online*](https://github.com/ARaza448/Interpret-Esolangs-Online)
si esta presente como checkout hermano, via `node tools/run_befunge.js` (override
con `BEFUNGE_JS_LIB`). El compilador nunca ve outputs esperados; las pruebas checan
comportamiento, no nombres de archivo. Si el interprete independiente no se encuentra, la
prueba **se salta con una razon explicita impresa** — nunca finge un pase.

```bash
python -m pytest tests -q -rs     # 45 pruebas; razones de skip se muestran si hay
```

## Limitaciones (v0.4, intencional)

- Sin auto-modificacion `p`/`g`, sin concurrencia, sin IPs multiples, sin
  Befunge-98, sin fingerprints, sin `?` (la fuente de aleatoriedad esta prohibida).
- Sin ops de input en el lenguaje aun (`&`/`~` diferidos).
- Solo digitos individuales se pushean directamente; numeros mas grandes deben componerse
  aritmeticamente.
- Una forma de branch: `|` con cero-abajo / non-zero-arriba. (`_` necesita brazos
  horizontales; intencionalmente excluido de v0.1.)
- La entrada esta fija en (0, 0) mirando a la derecha — asi es como empieza
  Befunge-93.
- El analisis estatico de pila es exacto dentro del set de ops, pero cruza a lenguaje
  de MAYBE donde es posible una profundidad dependiente de trayectoria; no reclama
  seguridad general.

## Layout

```
glyphfunge/            parser, ast, geometria, router, compilador, code_ir, validator, cli, interprete
examples/              programas GlyphFunge mas el fixture canonico de Code IR
generated/             .bf commiteados y artifacts de bridge (byte-estables)
tests/                 suite pytest (45 pruebas)
tools/run_befunge.js   harness para el interprete tercero independiente
DESIGN.md              que vino de GlyphFuck, que es especifico de Befunge, por que
```

GlyphFuck es la referencia geometrica y **no** se toca en este proyecto.

## Licencia

MIT — ver LICENSE.
