# Verificación

## Versión actual: meta de propuestas sin IA — 2026-08-27

- **46 pruebas automatizadas aprobadas.**
- Caso simulado: 110 candidatos disponibles, un contacto cada dos negocios;
  se revisaron exactamente 100 para obtener 50 propuestas y se detuvo al alcanzar la meta.
- Sin llamadas a Ollama en la búsqueda; probado con funciones de IA reemplazadas por errores.
- Contactos publicados priorizados; Instagram/correo/WhatsApp evitan visitar webs.
- Teléfono publicado cuenta por sí solo, aunque falle la web, sin convertirse en WhatsApp.
- Duplicados, propuestas anteriores, exclusiones, candidatos sin verificar y datos
  históricos no inflan la meta. Se distingue agotamiento de fuente y consulta truncada.
- Cancelación por archivo de señal probada; el comando exporta resultados parciales
  y devuelve código 3 cuando no alcanza la meta.
- Migración de SQLite v1 a v2 conserva contactos/seguimiento y crea copia previa.
  Los contactos antes entregados se registran como anteriores, no como nuevos.
- Importación del Excel anterior de siete hojas sin cambios de seguimiento.
- Exportación/importación real del Excel simple: libro vacío, propuesta, pendiente,
  notas, revisión, importación idempotente y texto que empieza con `=` sin ejecutar fórmulas.
- Inicialización de Tkinter y acción de búsqueda verificadas con valores iniciales
  `Villa Urquiza`, `todos`, `50`, sin opción de IA. No se hizo una prueba manual de cada botón.
- Ambas hojas renderizadas y revisadas visualmente; totales reconciliados con SQLite.

### Prueba real

Consulta por **Villa Urquiza / todos**: 876 candidatos devueltos. Se pidieron **5
propuestas nuevas**; se obtuvieron exactamente 5, con 5 negocios revisados y 1
anterior omitido. Cero errores. **5,32 segundos de búsqueda**, sin contar Excel.
Este caso usó contactos ya publicados en OSM y no requirió revisar webs; no es
un promedio general ni una promesa de rendimiento para 50 propuestas reales.

Después de esta prueba hay **15 negocios en SQLite: 13 con contacto y 2 pendientes**.
Los 8 contactos anteriores se conservan; las 5 propuestas son nuevas. Ningún
mensaje enviado. El análisis IA anterior sigue guardado en SQLite, fuera del Excel.

---

## Registro histórico de la primera versión (reemplazada)

Fecha: 2026-08-27. Equipo: Windows, i5-14600KF, 16 GB RAM, RTX 3050 6 GB.
Ollama 0.33.1, modelo local qwen3:4b.

## Pruebas realizadas

- 30 pruebas automatizadas aprobadas (pytest).
- Compilación de todos los módulos Python.
- Inicialización de la ventana Tkinter y lectura de sus controles por defecto.
- Prueba aislada de exportar/importar un Excel, conservar notas y revisión,
  volver a importar sin cambios, y evitar una fórmula inyectada en un nombre.
- Consulta real a Overpass por Villa Urquiza y peluquerías/estética: 29 candidatos.
- Diez negocios reales guardados en SQLite y en el libro entregado.
- Reejecución incremental: se omitieron los dos negocios ya procesados y se
  incorporaron ocho nuevos sin crear duplicados.
- Actualización de contactos: lo no vuelto a encontrar se conserva como histórico,
  separado de los contactos activos del resumen.
- Exportación del Excel con comprobación automática de sus ocho indicadores contra
  los datos de la base y sin errores de fórmula detectados.
- Revisión visual de las siete hojas; los rangos extensos se inspeccionaron por partes.

## Contenido del Excel al finalizar

| Dato | Cantidad de negocios |
|---|---:|
| Registrados | 10 |
| Web publicada en la fuente | 2 |
| Instagram publicado | 3 |
| WhatsApp explícito encontrado | 0 |
| Correo publicado | 2 |
| Análisis IA disponible | 1 |
| Contactados | 0 |

Las categorías de contacto se superponen. No equivalen a clientes aptos ni a
consentimiento comercial. Los datos del directorio deben corroborarse.

## Casos relevantes

- La web publicada para Prana redirigía a otro dominio con contenido de otro rubro.
  Se agregó un control que detiene redirecciones entre dominios y solicita
  confirmar identidad; esa web no se analiza como si fuera del local.
- Vipeluquería's permitió leer su portada y servicios. Se generó un análisis con
  citas de esos textos, preguntas y un borrador no enviado.
- Un formulario para postularse a un empleo fue descartado como canal comercial.
- Los primeros ensayos del modelo tuvieron una respuesta cortada y otra demasiado
  genérica. Se ajustaron los límites, la selección de fragmentos por ID y la
  validación. No se presentan los errores iniciales como resultados válidos.

## Tiempos observados, no promesas

- Corrida posterior a los ajustes: dos negocios en 35.5 segundos, sin incluir
  exportación. Uno quedó sin evidencia por la redirección y el otro tuvo análisis.
- Reanálisis de las páginas guardadas de Vipeluquería's: 12.8 segundos, sin búsquedas
  ni lectura web nuevas. Se usó el modelo ya cargado.
- Incorporación de ocho negocios sin web, desde consulta en caché y sin IA: 2.3
  segundos. No representa el costo de ocho revisiones completas.

No hay aún una medición representativa de 50 o 100 negocios con búsqueda externa.
La primera carga del modelo, saturación de proveedores, sitios lentos o falta de
datos cambian los tiempos. Se recomienda ajustar la cantidad gradualmente.

## Qué no se probó / no está incluido

- Brave Search API: sin clave ni plan contratado; integración opcional desactivada.
- No se extrajo Google Maps ni se verificó cobertura exhaustiva de un barrio.
- No se revisaron visualmente los sitios de los negocios, ni páginas con sesión.
- No se enviaron mensajes, formularios o comunicaciones comerciales.
- No se configuraron tareas periódicas.
- La ventana fue comprobada funcionalmente al iniciar; no se realizó una sesión
  manual completa pulsando todos los botones.
- El motor Excel depende del runtime de Codex preparado en esta computadora.

Los cambios del sitio o los proveedores pueden requerir mantenimiento. Toda
propuesta de IA sigue necesitando revisión humana, aun cuando sus citas existan.
