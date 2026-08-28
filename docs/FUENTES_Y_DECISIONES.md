# Fuentes y decisiones técnicas

Revisado: 2026-08-27.

## Actualización: búsqueda por meta de contactos

El flujo principal ahora reúne propuestas nuevas sin IA ni búsquedas de Brave.
Una propuesta es un negocio con Instagram, WhatsApp, correo o teléfono publicado;
no significa que necesite un sistema ni que haya aceptado recibir publicidad.
El Excel se redujo a Propuestas y Pendientes. Los análisis, detalles técnicos y
seguimiento anterior quedan conservados en SQLite, fuera del Excel simplificado.
Se conserva una copia anterior a la migración de la base.

La cantidad solicitada cuenta propuestas nuevas, no negocios revisados. No se
cuentan duplicados ni datos históricos/candidatos sin verificar. El proceso para
al alcanzar la meta, agotar la consulta, llegar al tope de candidatos o recibir
una detención del usuario. Las instancias públicas de Overpass no son ilimitadas.

## Google Maps

Se decidió no implementar extracción masiva de su interfaz. El usuario dejó a
criterio técnico la fuente de lugares. Las restricciones de exportación y la
fragilidad de una interfaz cambiante no son una buena base para este MVP.
Los enlaces de Maps son solamente búsquedas manuales.

- https://www.google.com/intl/en-US/help/terms_maps/
- https://cloud.google.com/maps-platform/terms

## OpenStreetMap / Overpass

Datos de locales aportados por la comunidad; cobertura incompleta, especialmente
en contactos. Selección por límites administrativos OSM del barrio de CABA.
Sin geocodificación masiva, sin Nominatim, sin reseñas de usuarios.
Consulta acotada, caché 24 horas, un proceso y límite de candidatos.

- https://www.openstreetmap.org/copyright
- https://wiki.openstreetmap.org/wiki/Overpass_API
- https://dev.overpass-api.de/overpass-doc/en/preface/commons.html

**Atribución:** © OpenStreetMap contributors, ODbL. Revisar obligaciones de licencia
antes de redistribuir una base derivada. El Excel incluye la atribución y cada fila
conserva su fuente.

## IA local

**Módulo anterior, fuera del flujo actual.** Se conserva por compatibilidad; no
se invoca al buscar propuestas ni se incluye su salida en el nuevo Excel.

Ollama sirve su API local. `qwen3:4b` se eligió como punto de partida para 16 GB de
RAM y RTX 3050 6 GB. No implica que sea el mejor modelo para todos los casos.
Se debe medir con textos reales. Salida JSON con esquema y citas verificadas;
sin herramientas, sin instrucciones ejecutables desde contenido web.

- https://docs.ollama.com/windows
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/capabilities/structured-outputs
- https://ollama.com/library/qwen3:4b

## Búsqueda opcional de candidatos

**Módulo anterior, fuera del flujo actual.** La búsqueda de propuestas no lo llama,
aunque haya una clave configurada. No se ofrece como parte del modo rápido.

Brave Search API requiere clave propia y derechos de almacenamiento compatibles.
Desactivada hasta que el usuario los configure. La API está implementada, pero no
se compró ni utilizó una cuenta durante el desarrollo.

- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/api-reference/web/search/get

## Persistencia y Excel

SQLite mantiene identidades e historial. Una sola base local y un escritor por vez.
Excel tiene un bloque editable, con revisión optimista para detectar copias viejas.
Se importan solo campos conocidos, sin fórmulas ni macros. El libro se genera con
el runtime de artefactos disponible en Codex; esa dependencia no es portable por pip.

- https://www.sqlite.org/whentouse.html

## Contactos y comunicaciones

La extracción no acredita consentimiento. El sistema no envía mensajes ni configura
automatizaciones de redes sociales. Requiere revisión humana y cumplimiento del canal.

- https://whatsappbusiness.com/policy/
- https://www.postman.com/meta/instagram/folder/uxudqu0/send-api
- https://www.argentina.gob.ar/noticias/registro-no-llame-la-aaip-brinda-informacion-para-garantizar-el-cumplimiento-de-la-ley
