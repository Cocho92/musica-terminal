# Barra de pestañas propia ("minimalista redondeado"):
#   izquierda: pestañas redondeadas con un ícono según lo que corre en ellas
#   derecha:   lo que suena con `musica`
# Se activa en kitty.conf con:  tab_bar_style custom
# Colores: Gruvbox Material Dark (el tema de kitty.conf). Íconos: Material Design de la Nerd Font que trae Kitty
# (códigos U+F0000+, que ninguna otra fuente del sistema pisa), seguidos de un espacio duro para que ocupen 1 celda.
import json
import os
import socket
import time

from kitty.boss import get_boss
from kitty.fast_data_types import Screen, add_timer, wcswidth
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb, color_as_int


def _c(h: str) -> int:
    return as_rgb(int(h.lstrip("#"), 16))


ACTIVA_BG, ACTIVA_FG = _c("#d8a657"), _c("#1d2021")      # amarillo gruvbox, texto oscuro
INACTIVA_BG, INACTIVA_FG = _c("#32302f"), _c("#928374")  # gris oscuro, texto gris
MUSICA, TEXTO, TENUE = _c("#d3869b"), _c("#d4be98"), _c("#7c6f64")
REFRESCO = 1.0          # segundos entre redibujados (el tiempo de la canción avanza de a 1 s)
NB = " "           # espacio duro: el ícono no se ensancha a 2 celdas

ICONOS = (               # (palabras en el título de la pestaña, ícono)
    (("claude",), "\U000F06A9"),                          # robot
    (("musica", "mpv"), "\U000F075A"),                   # música
    (("python", "pip", "uv ", "venv"), "\U000F0320"),    # python
    (("git", "lazygit"), "\U000F02A2"),                  # git
    (("node", "npm", "pnpm", "bun", "deno"), "\U000F0399"),  # node
    (("ssh",), "\U000F048B"),                            # servidor
)
CARPETA, CONSOLA = "\U000F024B", "\U000F018D"
PLAY, PAUSA = "\U000F040A", "\U000F03E4"
COLA = "\U000F0CB8"     # lista de reproducción
VOL = ("\U000F0581", "\U000F057F", "\U000F0580", "\U000F057E")   # silencio, bajo, medio, alto

_timer = None
_cache: dict = {"t": 0.0, "musica": None}


def _icono(titulo: str) -> str:
    t = titulo.lower()
    for palabras, ico in ICONOS:
        if any(p in t for p in palabras):
            return ico
    return CARPETA if titulo.startswith(("~", "/")) else CONSOLA


def _acortar(titulo: str, n: int) -> str:
    casa = os.path.expanduser("~")
    if titulo.startswith(casa):
        titulo = "~" + titulo[len(casa):]
    return titulo if len(titulo) <= n else titulo[: n - 1] + "…"


# ---------------------------------------------------------------- estado de la derecha
def _mpv(sock: socket.socket, n: int, *cmd):
    sock.sendall(json.dumps({"command": list(cmd), "request_id": n}).encode() + b"\n")
    buf = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            return None
        buf += chunk
        while b"\n" in buf:
            linea, buf = buf.split(b"\n", 1)
            msg = json.loads(linea)
            if msg.get("request_id") == n:
                return msg.get("data") if msg.get("error") == "success" else None


def _musica():
    """Datos de lo que suena con `musica` (dict), o None. Pregunta a mpv como mucho cada REFRESCO segundos."""
    ahora = time.monotonic()
    if ahora - _cache["t"] < REFRESCO - 0.2:
        return _cache["musica"]
    _cache["t"], _cache["musica"] = ahora, None
    run = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    try:
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(0.2)
            s.connect(f"{run}/musica-mpv.sock")
            props = ("pause", "path", "media-title", "time-pos", "duration", "playlist-pos", "playlist-count",
                     "volume")
            v = {p: _mpv(s, i, "get_property", p) for i, p in enumerate(props, 1)}
    except (OSError, ValueError):
        return None
    m = {"pausa": bool(v["pause"]), "titulo": v["media-title"] or "", "artista": "", "album": "",
         "pos": v["time-pos"], "dur": v["duration"], "n": (v["playlist-pos"] or 0) + 1,
         "total": v["playlist-count"] or 1, "vol": v["volume"]}
    try:
        with open(f"{run}/musica-now.json") as f:
            cola = json.load(f).get("queue") or []
        c = next((c for c in cola if c.get("id") and c["id"] in (v["path"] or "")), None)
        if c:
            m.update(titulo=c.get("title") or m["titulo"], artista=c.get("artists") or "", album=c.get("album") or "")
    except (OSError, ValueError, AttributeError):
        pass
    if m["titulo"]:
        _cache["musica"] = m
    return _cache["musica"]


def _hms(seg) -> str:
    seg = int(seg or 0)
    return f"{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}" if seg >= 3600 else f"{seg // 60}:{seg % 60:02d}"


def _corta(s: str, n: int) -> str:
    return s if len(s) <= n else (s[: n - 1] + "…" if n > 1 else "")


def _estado(screen: Screen, fondo: int) -> None:
    """A la derecha, lo que suena:  ▶ Tema — Artista · Álbum   1:23 ━━●──── 3:43   3/25   󰕾 80%
    Si no entra se va achicando: primero el álbum, después volumen, cola y barra; al final se acorta el título."""
    m = _musica()
    if not m:
        return
    libre = screen.columns - screen.cursor.x - 2
    vol = m["vol"] or 0
    vol_ico = VOL[0 if vol <= 0 else 1 if vol < 34 else 2 if vol < 67 else 3]
    t_pos, t_dur = _hms(m["pos"]), _hms(m["dur"])

    def barra(n: int) -> list:
        lleno = int(n * (m["pos"] or 0) / m["dur"]) if m["dur"] else 0
        return [(MUSICA, "━" * lleno + "●"), (TENUE, "─" * max(0, n - lleno - 1))]

    # (nombre, segmentos[(color, texto)]) en orden de aparición; se quitan según PRIORIDAD si no entran
    def armar(quitar: set, ancho_titulo: int) -> list:
        segs = [(MUSICA, f"{PAUSA if m['pausa'] else PLAY}{NB}"),
                (MUSICA, _corta(m["titulo"], ancho_titulo))]
        if m["artista"]:
            segs.append((TEXTO, " — " + _corta(m["artista"], 25)))
        if m["album"] and "album" not in quitar and m["album"] != m["titulo"]:
            segs.append((TENUE, " · " + _corta(m["album"], 25)))
        if "barra" in quitar:
            segs.append((TENUE, f"   {t_pos}/{t_dur}"))
        else:
            segs += [(TENUE, f"   {t_pos} ")] + barra(12) + [(TENUE, f" {t_dur}")]
        if m["total"] > 1 and "cola" not in quitar:
            segs.append((TENUE, f"   {COLA}{NB}{m['n']}/{m['total']}"))
        if "vol" not in quitar:
            segs.append((TENUE, f"   {vol_ico}{NB}{round(vol)}%"))
        return segs

    quitar, ancho_titulo = set(), 40
    for paso in (None, "album", "vol", "cola", "barra"):
        if paso:
            quitar.add(paso)
        segs = armar(quitar, ancho_titulo)
        ancho = sum(wcswidth(t) for _, t in segs)
        if ancho <= libre:
            break
    else:                       # ni así entra: achicar el título
        sobra = ancho - libre
        ancho_titulo = max(0, ancho_titulo - sobra)
        segs = armar(quitar, ancho_titulo)
        ancho = sum(wcswidth(t) for _, t in segs)
        if ancho > libre or ancho_titulo < 8:
            # último recurso: ícono, título corto y tiempo
            fijo = f"{PAUSA if m['pausa'] else PLAY}{NB}"
            tiempo = f"  {t_pos}"
            n = libre - wcswidth(fijo) - len(tiempo)
            if n < 6:
                return          # no hay lugar: no se muestra
            segs = [(MUSICA, fijo), (MUSICA, _corta(m["titulo"], n)), (TENUE, tiempo)]
            ancho = sum(wcswidth(t) for _, t in segs)

    screen.cursor.bg = as_rgb(fondo)
    screen.cursor.fg = 0
    screen.draw(" " * (screen.columns - screen.cursor.x - ancho - 1))
    for color, texto in segs:
        screen.cursor.fg = color
        screen.draw(texto)
    screen.cursor.fg = 0
    screen.draw(" ")


def _refrescar(timer_id) -> None:
    for tm in get_boss().all_tab_managers:
        tm.mark_tab_bar_dirty()


# ---------------------------------------------------------------- pestañas
def draw_tab(draw_data: DrawData, screen: Screen, tab: TabBarData, before: int, max_tab_length: int,
             index: int, is_last: bool, extra_data: ExtraData) -> int:
    global _timer
    if _timer is None:
        _timer = add_timer(_refrescar, REFRESCO, True)

    fondo = color_as_int(draw_data.default_bg)
    bg, fg = (ACTIVA_BG, ACTIVA_FG) if tab.is_active else (INACTIVA_BG, INACTIVA_FG)
    texto = f"{_icono(tab.title)}{NB}{index} {_acortar(tab.title, max(8, min(25, max_tab_length - 6)))}"

    if screen.cursor.x == 0:
        screen.cursor.bg = as_rgb(fondo)
        screen.draw(" ")
    screen.cursor.bg, screen.cursor.fg = as_rgb(fondo), bg
    screen.draw("")                       # borde redondeado izquierdo
    screen.cursor.bg, screen.cursor.fg = bg, fg
    screen.cursor.bold = tab.is_active
    screen.draw(texto)
    screen.cursor.bold = False
    screen.cursor.bg, screen.cursor.fg = as_rgb(fondo), bg
    screen.draw("")                       # borde redondeado derecho
    screen.cursor.fg = 0
    screen.draw(" ")
    fin = screen.cursor.x

    if is_last:
        _estado(screen, fondo)
    return fin
