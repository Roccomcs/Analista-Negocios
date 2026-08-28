# Tareas manuales

## Uso habitual

1. Abrir `Iniciar.cmd`; no hace falta Ollama.
2. Elegir barrio, rubro y meta de propuestas nuevas.
3. Guardar/cerrar Excel y pulsar **Buscar propuestas**.
4. Revisar identidad del negocio y contacto antes de escribir o llamar.
5. Completar Estado, Notas y No contactar en las columnas amarillas del Excel.

Si se consiguen menos propuestas que las pedidas, elegir otro barrio/rubro o
importar CSV. No repetir indefinidamente la misma consulta esperando otros datos.
Para volver a intentar una web antes revisada, marcar la opción de revisar anteriores.

Los negocios de **Pendientes** no tienen contacto encontrado. El enlace Buscar
Instagram ayuda a revisarlos manualmente; no es un perfil confirmado. Para agregar
un contacto encontrado por ustedes, importar un CSV con nombre, zona y dirección
coincidentes. Los datos de contacto no se importan desde las columnas del Excel.

## Instalación en otra computadora

`Instalar.cmd` instala dependencias Python. El motor de Excel requiere
**@oai/artifact-tool del runtime de Codex**, ya configurado en esta computadora.
No se instala como paquete público de pip.

Solicitar al asistente las rutas de las dependencias del workspace y configurar
el motor con `scripts/configurar-excel.ps1`. No copiar paquetes privados al
repositorio ni instalar paquetes homónimos al azar. Si falta el runtime, los datos
siguen en SQLite y pueden exportarse en el equipo configurado.

No se necesitan cuentas de Google, Brave ni Ollama para el flujo de contactos.
La integración antigua de Brave no se utiliza en este flujo.

## Errores frecuentes

| Situación | Acción |
|---|---|
| Menos propuestas que la meta | Revisar el resultado real y cambiar barrio/rubro o importar una lista propia. |
| Límite de candidatos | Consulta parcial: usar un rubro más específico. |
| HTTP 403/429 o timeout de Overpass | Intentar más tarde; no evadir restricciones ni repetir en un bucle. |
| robots.txt o web bloqueada | Revisar manualmente; no saltear restricciones. |
| Redirige a otro dominio | Confirmar identidad antes de actualizar el sitio mediante CSV. |
| Excel abierto | Guardar/cerrar y pulsar Exportar / sincronizar; SQLite conserva lo investigado. |
| Excel desactualizado | Usar la copia maestra; trasladar las notas después de comparar. |
| ID desconocido o duplicado | No modificar IDs ni revisiones. Restaurar desde una copia si hace falta. |
| Otra ejecución en curso | Esperar; solo un proceso puede escribir en la base. |
| Detener tarda | Espera a terminar el negocio/petición actual; después exporta lo reunido. |

No borrar filas para excluir contactos: usar `No contactar = Sí` o `Descartado`.
No trabajar simultáneamente con dos copias independientes de la base.
