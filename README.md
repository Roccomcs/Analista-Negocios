# Cadmo · Buscador de propuestas

Elegís un barrio, un rubro y una **meta de propuestas nuevas**. El programa revisa
negocios de OpenStreetMap hasta reunir esa cantidad de negocios con contacto, o
hasta terminar los candidatos disponibles. **No usa IA, no necesita Ollama y no
envía mensajes.**

## Empezar

1. Abrí **Iniciar.cmd**. Si la ventana anterior estaba abierta, cerrala y volvé a abrirla.
2. Elegí barrio, rubro y **Propuestas nuevas** (1–200; valor inicial: 50).
3. Guardá y cerrá el Excel antes de ejecutar.
4. Pulsá **Buscar propuestas**. El registro muestra propuestas conseguidas y negocios revisados por separado.
5. Pulsá **Abrir Excel**: `outputs/cadmo/seguimiento.xlsx`.

**Detener y guardar** termina después del negocio que se está revisando y exporta
lo reunido. No interrumpe una petición HTTP a mitad de camino, por lo que puede
tardar hasta terminar la consulta o alcanzar su tiempo de espera.

## Qué cuenta como propuesta

Un negocio distinto con **al menos un Instagram, WhatsApp, correo o teléfono publicado**.
Cuenta una vez aunque tenga varios canales. En este contexto, propuesta significa
contacto potencial: no un diagnóstico, un presupuesto enviado ni un cliente interesado.

- Tener solo web, Facebook o formulario no alcanza para la meta.
- Un teléfono sirve para llamar. **No se supone que tenga WhatsApp**, ni siquiera si parece celular.
- No se cuentan candidatos de búsqueda sin identidad corroborada ni datos marcados como históricos.
- Un contacto público puede estar desactualizado: comprobar que pertenezca al negocio antes de usarlo.
- Los contactos de corridas anteriores no vuelven a contar como nuevos.
- `No contactar = Sí` y los estados distintos de `Nuevo`/`Revisar` se excluyen de la búsqueda.

Por ejemplo, **50 propuestas** puede requerir revisar 50, 100 o más negocios.
El programa no se detiene por haber revisado 50 si solo 12 tienen contacto.

Si la fuente no alcanza, informa el resultado real, por ejemplo `12/50`, y guarda
esas 12. No puede garantizar 50 contactos en cualquier barrio/rubro: no inventa
datos, no repite negocios y no cambia de zona sin que lo elijas.

## Cómo encuentra contactos sin perder tiempo

1. Consulta el barrio/rubro una vez y reutiliza la respuesta durante 24 horas.
2. Prioriza negocios que ya publican contactos en OSM.
3. Si ya tiene Instagram, WhatsApp o correo, guarda los datos sin visitar la web.
4. Si tiene web y ningún canal de mensajes (o solo teléfono), busca contactos en
   la página principal y, si hace falta, en una página de contacto. Por defecto,
   máximo dos páginas por negocio. Se detiene antes si encuentra un canal de mensajes.
5. Si no encuentra contacto, guarda el negocio en **Pendientes** y sigue con otro.

No busca cada negocio en Google ni inicia sesión en Instagram. La búsqueda externa
de Brave de la versión anterior **no se llama en este flujo**, incluso si quedó
configurada una clave. No hay consumo de una API de búsqueda paga.
Los enlaces de Pendientes son búsquedas para abrir manualmente.

Se mantienen los límites por dominio, robots.txt, límites de tamaño, tiempos de
espera y validación de URLs. No se evaden bloqueos ni se infiere identidad después
de una redirección a otro dominio.

## El Excel: solo dos hojas

| Hoja | Contenido |
|---|---|
| **Propuestas** | Nombre, barrio, Instagram, WhatsApp, correo, teléfono, web y dirección; estado, notas, exclusión, fecha y fuente. |
| **Pendientes** | Negocios sin contacto encontrado, ubicación/web si existen y enlace para buscar Instagram manualmente. |

La lista es **acumulada**, no solo de la última corrida. Arriba se muestra el total
y, en Propuestas, el resultado de la última búsqueda. Los negocios contactados se
conservan en la lista para seguimiento; filtrar por Estado y No contactar.

Editá únicamente las columnas amarillas: **Estado, Notas y No contactar**. Los
identificadores y la revisión están al final: no editarlos ni borrar filas para
eliminar negocios. Marcar `Descartado` o `No contactar = Sí`.

Guardá y cerrá el archivo. La próxima búsqueda o **Exportar / sincronizar Excel**
importa tus cambios antes de actualizarlo. Los contactos y otros datos se regeneran
desde SQLite: para aportar contactos manuales, usar el CSV descrito abajo.

El sistema acepta también el Excel anterior de siete hojas para recuperar sus
notas. Los responsables, próximas acciones, fechas y análisis anteriores se
conservan en SQLite aunque ya no ocupen lugar en el Excel simple.
Hay copias de seguridad antes de sincronizar; una copia antigua en conflicto no
sobrescribe notas nuevas. Usar una sola copia maestra entre ambos socios, por turnos.

## Fuente y límites

**OpenStreetMap no contiene todos los locales ni el detalle de Google Maps.**
No se obtienen reseñas, puntuaciones o fotos. Los datos comunitarios pueden estar
incompletos o desactualizados. Un campo vacío significa “no encontrado”.

La selección usa los límites administrativos del barrio dentro de CABA. Hay un
tope de **2.000 candidatos por consulta**; si se alcanza, se informa que la consulta
es parcial y conviene elegir un rubro más específico. Las instancias públicas de
Overpass tienen límites y disponibilidad variable: no son una API ilimitada.

© OpenStreetMap contributors · ODbL · https://www.openstreetmap.org/copyright

Reglas del servicio: https://dev.overpass-api.de/overpass-doc/en/preface/commons.html

## Importar negocios o contactos propios

Usá una copia de `ejemplos/negocios.csv` con estas columnas:

`id,nombre,zona,rubro,direccion,web,instagram,whatsapp,correo,telefono,fuente`

CSV UTF-8 con coma o punto y coma. Nombre y zona son obligatorios. Conservar ID si
ya se usó. Para agregar un contacto a un negocio encontrado por OSM, conservar
exactamente su nombre, barrio y dirección, y comprobar que sea el mismo local.
Sin una dirección coincidente, no se fusionan registros distintos por su nombre.

El CSV reemplaza a OSM durante esa corrida; solo se procesan filas del barrio
elegido. Los contactos manuales también deben corroborarse. Si un negocio antes
no tenía contacto y el CSV/OSM ahora lo aporta, puede contar como propuesta nueva.

**Volver a revisar los anteriores** actualiza contactos y permite reintentar webs
sin contacto. Los negocios ya entregados nunca vuelven a contar para la meta.
Esta opción puede tardar más; no hace falta para el uso habitual.

## Usar desde la terminal

```powershell
.\.venv\Scripts\python.exe -m analista.cli ejecutar --zona "Villa Urquiza" --rubro todos --cantidad 50
.\.venv\Scripts\python.exe -m analista.cli ejecutar --zona "Palermo" --rubro comercios --cantidad 30
.\.venv\Scripts\python.exe -m analista.cli ejecutar --zona "Villa Urquiza" --cantidad 20 --csv ejemplos/mi-lista.csv
.\.venv\Scripts\python.exe -m analista.cli exportar
.\.venv\Scripts\python.exe -m analista.cli diagnostico
.\.venv\Scripts\python.exe -m analista.cli zonas
```

`--sin-ia` sigue aceptándose para scripts anteriores, pero ya no hace falta.
`--actualizar` vuelve a revisar los anteriores sin contarlos otra vez.
El comando independiente `analizar` sigue disponible por compatibilidad, solo si
se invoca expresamente; no lo usa la ventana ni la búsqueda de propuestas. Sus
resultados quedan en SQLite y no aparecen en el Excel simple.

Códigos de salida: `0` meta lograda/operación correcta; `3` resultados parciales
guardados (fuente agotada, tope o detención solicitada); `2` hubo errores por
negocio; `1` error general; `130` interrupción abrupta. Ante interrupción abrupta,
lo guardado permanece en SQLite y se recupera con `exportar`.

## Configuración e instalación

En esta computadora ya está instalado. **No hace falta abrir Ollama.**
La configuración opcional va en `config.local.json`; ejemplo en `config.example.json`.
`max_pages` controla las páginas revisadas y `max_candidates` el límite de lugares.

`Instalar.cmd` prepara las dependencias Python usando `requirements-lock.txt`.
El motor Excel requiere el runtime de artefactos de Codex configurado en este equipo;
no se instala con pip. Para otra computadora, ver `docs/TAREAS_MANUALES.md`.

## Datos, seguridad y pruebas

- SQLite: `data/negocios.sqlite3`; conserva contactos, procedencia, historial y propuestas ya entregadas.
- Copias: `data/backups/`; al migrar, también `data/negocios.v1-backup.sqlite3`.
- Excel: `outputs/cadmo/seguimiento.xlsx`.
- Una sola ejecución escribe a la base; no compartir SQLite directamente por red.
- No se envían mensajes, formularios ni solicitudes de amistad. Respetar rechazos y reglas del canal.
- Los datos de fuentes públicas no se ejecutan como instrucciones ni fórmulas de Excel.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verificar-exportacion.py
```

Las pruebas cubren meta de contactos, agotamiento, cancelación, duplicados,
exclusiones, migración y seguimiento. La segunda verificación exporta e importa
un Excel real usando datos de prueba aislados, sin tocar las notas de producción.
