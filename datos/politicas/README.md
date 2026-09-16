# Documentos de políticas

Un archivo `.md` por tema (por ejemplo `bloqueo_de_tarjetas.md`, `apertura_de_disputas.md`).
`make cargar-politicas` los divide en fragmentos por párrafo (líneas separadas por una línea en
blanco), calcula sus embeddings y los carga en la tabla `politicas`. Volver a correrlo reemplaza
los fragmentos de cada documento por los nuevos, así que es seguro correrlo de nuevo después de
editar un archivo.

Como son políticas propias de este banco ficticio, se conoce de antemano la respuesta correcta
para cada pregunta de evaluación que se arme sobre ellas.
