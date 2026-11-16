---
name: musica
description: Reproducir música de YouTube Music en la computadora del usuario (solo audio, con mpv, en segundo plano) y controlarla. Usar cuando pida poner, reproducir o escuchar música, una canción, un artista, un álbum o un estilo (ej. "reproducí fito paez", "poné lofi", "quiero escuchar jazz"), o cuando pida pausar, seguir, parar, subir/bajar el volumen, adelantar o saber qué está sonando.
argument-hint: "[canción, artista o estilo]"
---

# Música con `musica`

`~/.local/bin/musica` busca en YouTube Music y reproduce solo el audio con mpv. Ya está instalado y probado
(depende de mpv, yt-dlp y uv). No instales nada ni uses el navegador para esto.

## Reproducir algo

1. Listar los 5 resultados (nunca uses el modo sin opciones: abre un menú interactivo que necesita una terminal real):
   ```bash
   musica -l <búsqueda>
   ```
2. Mostrarle al usuario las 5 opciones numeradas (título, artista, álbum, duración) y preguntarle cuál quiere.
   Esperar su respuesta: no elegir por él, salvo que haya pedido explícitamente "poné la primera" o similar.
3. Reproducir en segundo plano la elegida, con **exactamente la misma búsqueda** del paso 1:
   ```bash
   musica -b -n <N> <búsqueda>
   ```
   Reemplaza lo que esté sonando. Después de la elegida sigue sola con una "radio" de canciones parecidas
   (recomendaciones de YouTube Music), así que "siguiente"/"anterior" funcionan con `musica ctl next|prev`. Confirmá el título que imprime; si no coincide con el que eligió (la búsqueda
   cambió entre llamadas), avisale y volvé a listar.

Si `$ARGUMENTS` trae una búsqueda (se llamó como `/musica fito paez`), empezá directamente por el paso 1.

## Controlar lo que suena

```bash
musica ctl status            # qué suena, posición, volumen
musica ctl pause | play | toggle
musica ctl next | prev       # siguiente / anterior de la cola (radio de YouTube Music, ~25 temas)
musica ctl stop
musica ctl vol 50            # absoluto 0-130; también +10 / -10
musica ctl seek +60          # adelantar 60 s; -30 atrasa; 120 va al segundo 120
```
"no hay música sonando" (exit 1) significa que no hay nada reproduciéndose.

Lo que ponés con `-b` sigue sonando de fondo aunque se cierre la terminal. Si el usuario quiere ver o manejar el
reproductor él mismo, decile que abra `musica ui` en Kitty (tapa del álbum, barra de progreso, anterior/siguiente
y teclas), o `musica ui -m` para el modo barra de 1-2 líneas. Ojo: salir del reproductor (`q`) o cerrar esa terminal PARA la música. No lo ejecutes vos: necesita una
terminal interactiva.

## Si falla

- Error 403, lentitud o "Buffering" constante: actualizar yt-dlp con `uv tool upgrade yt-dlp` y reintentar.
  yt-dlp usa Bun como runtime de JavaScript (`~/.config/yt-dlp/config`); sin eso YouTube limita la velocidad.
- Error al buscar: probablemente cambió YouTube Music; el script usa la librería ytmusicapi (la resuelve uv).
- El log de la última reproducción en segundo plano está en `$XDG_RUNTIME_DIR/musica.log`.

Respondé en español y breve: la lista de opciones y luego una línea confirmando qué suena.

En Kitty también hay atajos para lo que suena de fondo: Alt+Shift+espacio (pausa), Alt+Shift+N / P
(siguiente / anterior), Alt+Shift+K / J (subir / bajar volumen), Alt+Shift+S (parar). Las teclas multimedia de la
notebook y el applet de sonido de Cinnamon también la controlan (MPRIS).
