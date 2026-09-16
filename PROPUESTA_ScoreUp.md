# Propuesta inicial – ScoreUp: Sistema de Evaluación de Clubes de Conquistadores

**Asignatura:** Taller de Programación
**Proyecto:** ScoreUp – Evaluación y calificación de clubes en eventos y temporadas
**Tipo de actividad:** Presentación y sustentación de propuesta de proyecto
**Modalidad:** Trabajo grupal
**Tecnología propuesta:** Python + Flask (HTML/CSS con Jinja2)
**Enfoque técnico:** Arquitectura de software, principios SOLID y patrones de diseño
**Entregable:** Documento de propuesta inicial

---

## 1. Descripción del problema

En una organización de Conquistadores se realizan periódicamente eventos (campamentos, reuniones, actividades regionales) en los que participan varios clubes. Actualmente, la evaluación del desempeño de cada club se maneja de forma manual: planillas en papel u hojas de cálculo, criterios definidos de manera informal y resultados que no siempre pueden rastrearse a una evaluación original.

Esta situación genera varios problemas concretos:

- La información está dispersa entre planillas, correos y mensajes.
- No se puede responder con certeza preguntas como: ¿qué criterios se evaluaron?, ¿quién evaluó a cada club?, ¿cuál fue el porcentaje ponderado?, ¿qué club ganó la temporada?, ¿qué penalizaciones se aplicaron y por qué motivo?
- Los cálculos (porcentaje ponderado, desempates, suma de penalizaciones) se realizan a mano y son propensos a errores.
- No existe una forma confiable de cerrar un evento: se puede evaluar aún cuando los criterios no están completos o sus pesos no suman 100%.
- Los incidentes disciplinarios quedan solo como relato verbal, sin registro con evidencia.

## 2. Problema central a investigar

> ¿Cómo mejorar el registro, cálculo y seguimiento de las evaluaciones de los clubes de Conquistadores durante sus eventos y temporadas mediante una aplicación informática que centralice la información, automatice los cálculos y permita la consulta de resultados por parte de todos los actores (administradores, evaluadores y directores de club)?

El problema es relevante porque el resultado de la evaluación determina el ranking de cada temporada y tiene un impacto directo en la motivación y reconocimiento de los clubes. Un error de cálculo o un dato perdido puede cambiar un resultado oficial.

## 3. Justificación

- **Automatización de cálculos:** el porcentaje ponderado, el puntaje por evento y el ranking de temporada se calculan de forma sistemática, eliminando errores manuales (ver `calc.py`).
- **Centralización:** toda la información de clubes, eventos, evaluaciones, penalizaciones e incidentes queda en un único sistema con persistencia (`persist.py` sobre SQLite).
- **Transparencia:** cada evaluación queda asociada a un evaluador (staff principal) y a una fecha, lo que permite auditar los resultados.
- **Control:** se impone una regla de negocio que impide cerrar un evento si los pesos de los criterios no suman 100% (`app.py`, `admin_evento_cerrar`).
- **Escalabilidad:** al separar dominio, cálculo y persistencia, el sistema puede crecer (nuevos tipos de evaluación, nuevos reportes) sin reescribir componentes enteros.

## 4. Objetivo general

Desarrollar un sistema informático (ScoreUp) que permita a una organización de Conquistadores registrar, evaluar, calificar y dar seguimiento al desempeño de sus clubes en eventos y temporadas, con resultados confiables y consultables por todos los actores involucrados.

## 5. Objetivos específicos

1. **OE-01.** Identificar los criterios e información necesarios para evaluar el desempeño de un club en un evento (criterios con peso, puntaje máximo).
2. **OE-02.** Diseñar un mecanismo para registrar evaluaciones por club y por evento, con valores por criterio y comentario del evaluador.
3. **OE-03.** Implementar los cálculos de porcentaje ponderado, puntaje por evento, desempates y ranking de temporada, considerando penalizaciones.
4. **OE-04.** Permitir la consulta de resultados y reportes por parte de administradores y directores de club, con exportación a Excel y PDF.
5. **OE-05.** Diseñar una arquitectura de software modular (interfaz, lógica de aplicación, dominio, acceso a datos) que facilite el mantenimiento y la evolución del sistema.

## 6. Alcance

### 6.1 Funcionalidades mínimas

- **A. Gestión de la organización y usuarios**
  - Registro de una organización con su usuario administrador inicial.
  - Roles con permisos: Administrador, Staff (evaluador) y Director de club.
  - Creación, edición y eliminación de usuarios; asignación de contraseñas seguras.

- **B. Gestión de clubes y miembros**
  - Alta, baja y modificación de clubes.
  - Registro de miembros (nombre, edad, cargo, año de ingreso, categoría).
  - Importación de miembros desde archivo Excel.

- **C. Gestión de eventos**
  - Creación de eventos (fecha, lugar, tipo, temporada, puntaje máximo).
  - Configuración de criterios con peso (la suma debe alcanzar 100% para cerrar).
  - Asignación de clubes participantes y de un staff principal por club.
  - Cierre del evento (bloquea modificaciones y evaluaciones).

- **D. Evaluación**
  - Registro de evaluaciones por staff: valor 0–100 por criterio y comentario.
  - Identificación de la evaluación oficial (la del staff principal) y respaldos.
  - Cálculo automático de porcentaje ponderado y puntaje.

- **E. Penalizaciones e incidentes**
  - Catálogo de motivos de penalización (descripción y puntos de descuento).
  - Aplicación y anulación de penalizaciones por staff.
  - Registro de incidentes con tipo, gravedad, descripción y evidencia fotográfica.

- **F. Resultados y reportes**
  - Ranking por evento y por temporada (puntaje bruto − penalizaciones).
  - Regla de desempate por el criterio de mayor peso.
  - Reporte de actividad del staff (clubes asignados vs. evaluaciones completadas).
  - Exportación de resultados a Excel y PDF.

### 6.2 Fuera del alcance de la primera versión

- Aplicación móvil nativa.
- Notificaciones automáticas por correo o mensajería.
- Integración con sistemas institucionales externos.
- Módulo de pagos o inscripciones.
- Sistema de autoevaluación por parte de los clubes.
- Predicción de desempeño mediante Machine Learning.

Estas funcionalidades pueden plantearse como trabajo futuro.

## 7. Identificación de actores

| Actor | Responsabilidad |
|---|---|
| **Administrador** | Gestiona la organización, los clubes, los eventos, los criterios y los usuarios. Genera accesos masivos y exporta resultados. |
| **Staff evaluador** | Evalúa a los clubes asignados, registra incidentes y aplica penalizaciones. Es el evaluador principal u oficial de un club en el evento. |
| **Director de club** | Consulta el ranking de temporada y los puntajes obtenidos por su club en los eventos cerrados. |

**Justificación:** se mantienen los tres roles porque son los que aparecen en el flujo real del problema: quien configura y administra (admin), quien evalúa (staff) y quien consume resultados (director). No se incorpora un rol de "ciudadano" porque el contexto no lo requiere; podrá agregarse en el futuro si la organización lo solicita.

## 8. Requerimientos funcionales

| Código | Requerimiento |
|---|---|
| RF-01 | El sistema deberá permitir registrar una nueva organización junto con su usuario administrador inicial. |
| RF-02 | El sistema deberá autenticar a los usuarios mediante usuario y contraseña y validar sus permisos según el rol (admin, staff, director). |
| RF-03 | El sistema deberá permitir crear, renombrar y eliminar clubes. |
| RF-04 | El sistema deberá permitir registrar y eliminar miembros de un club, así como importarlos desde un archivo Excel. |
| RF-05 | El sistema deberá permitir crear eventos con fecha, lugar, tipo, temporada y puntaje máximo. |
| RF-06 | El sistema deberá permitir configurar criterios de evaluación con su peso por evento. |
| RF-07 | El sistema deberá impedir cerrar un evento cuando la suma de pesos de sus criterios no sea 100%. |
| RF-08 | El sistema deberá permitir asignar clubes a un evento e indicar el staff principal evaluador de cada club. |
| RF-09 | El sistema deberá permitir al staff registrar evaluaciones (valor 0–100 por criterio y comentario) para los clubes asignados. |
| RF-10 | El sistema deberá calcular automáticamente el porcentaje ponderado y el puntaje de cada evaluación por evento. |
| RF-11 | El sistema deberá calcular el ranking por evento con desempate según el criterio de mayor peso. |
| RF-12 | El sistema deberá calcular el ranking de temporada restando las penalizaciones del puntaje bruto. |
| RF-13 | El sistema deberá permitir gestionar motivos de penalización (nombre, descripción, puntos, activo/inactivo). |
| RF-14 | El sistema deberá permitir al staff aplicar y al administrador anular penalizaciones a los clubes. |
| RF-15 | El sistema deberá permitir registrar incidentes con tipo, gravedad, descripción y evidencia fotográfica. |
| RF-16 | El sistema deberá permitir filtrar incidentes por evento, club, tipo, gravedad y estado. |
| RF-17 | El sistema deberá generar masivamente usuarios y contraseñas para staff y directores de un evento. |
| RF-18 | El sistema deberá permitir importar usuarios (staff o directores) desde archivos Excel. |
| RF-19 | El sistema deberá permitir exportar los resultados a Excel y PDF. |
| RF-20 | El sistema deberá mostrar al director el puntaje y la posición de su club en la temporada y en los eventos cerrados. |

## 9. Requerimientos no funcionales

| Código | Categoría | Requerimiento |
|---|---|---|
| RNF-01 | Usabilidad | La interfaz deberá ser sencilla y guiar al usuario con formularios y tablas claras; no se requiere conocimientos técnicos previos. |
| RNF-02 | Seguridad | El sistema deberá controlar el acceso por rol y almacenar las contraseñas de forma segura (hash). |
| RNF-03 | Rendimiento | Las consultas habituales (listados, rankings, reportes) deberán ejecutarse en un tiempo razonable para el volumen de datos esperado. |
| RNF-04 | Mantenibilidad | La solución deberá organizarse en capas (interfaz, lógica, dominio, persistencia) que faciliten su mantenimiento. |
| RNF-05 | Escalabilidad | La arquitectura deberá permitir incorporar nuevas funcionalidades (reportes, módulos) sin modificar grandes partes del sistema. |
| RNF-06 | Portabilidad | El sistema deberá ejecutarse con dependencias mínimas (Python + Flask + SQLite) y ser replicable mediante un listado de requerimientos. |

## 10. Historias de usuario

### HU-01 – Registrar un evento con criterios

**Como** administrador,
**quiero** crear un evento y definir sus criterios con su peso,
**para** preparar la evaluación de los clubes participantes.

**Criterios de aceptación:**
- Se debe indicar nombre, fecha, lugar, tipo, temporada y puntaje máximo.
- Se deben agregar criterios con peso en porcentaje.
- El sistema debe advertir cuando la suma de pesos supere 100%.
- El evento no se puede cerrar hasta que la suma de pesos sea 100%.

### HU-02 – Evaluar a un club

**Como** staff evaluador,
**quiero** registrar la evaluación de un club asignado indicando un valor por cada criterio,
**para** que su puntaje se calcule de forma automática y trazable.

**Criterios de aceptación:**
- Cada valor debe estar entre 0 y 100.
- Se debe poder incluir un comentario.
- Si ya existe una evaluación mía para el club, debe actualizarse (no duplicarse).
- El sistema debe mostrar el porcentaje ponderado y el puntaje resultante.

### HU-03 – Consultar el ranking de temporada

**Como** administrador,
**quiero** ver el ranking de la temporada indicada,
**para** conocer el orden final de los clubes y poder publicarlo.

**Criterios de aceptación:**
- El ranking debe ordenar por puntaje bruto − penalizaciones.
- Las posiciones deben respetar los empates (posición compartida).
- Debe incluir el detalle por evento y el monto de penalizaciones.

### HU-04 – Ver el desempeño de mi club

**Como** director de club,
**quiero** consultar el puntaje y la posición de mi club,
**para** informar a mis miembros sobre los resultados.

**Criterios de aceptación:**
- Solo debo ver los datos de mi propio club.
- Debe mostrar la posición en la temporada y los puntajes de los eventos cerrados.

### HU-05 – Reportar un incidente con evidencia

**Como** staff evaluador,
**quiero** reportar un incidente disciplinario adjuntando una fotografía,
**para** dejar un registro verificable del hecho.

**Criterios de aceptación:**
- Debo seleccionar tipo, gravedad y descripción.
- Debo poder adjuntar una imagen en formato permitido (png, jpg, gif, webp).
- El sistema debe asignar fecha y hora automáticamente.

### HU-06 – Exportar resultados

**Como** administrador,
**quiero** exportar los resultados del ranking a Excel o PDF,
**para** generar los documentos oficiales de la organización.

**Criterios de aceptación:**
- Se debe elegir formato (Excel o PDF) y alcance (temporada o evento).
- El archivo debe incluir encabezados, valores por criterio y totales.
- El archivo se debe descargar con un nombre identificable.

## 11. Propuesta inicial de arquitectura

La solución es una **arquitectura monolítica en capas**, compatible con los conceptos de Clean Architecture: las dependencias apuntan hacia adentro (dominio) y la infraestructura es reemplazable.

```
    Administrador      Staff evaluador      Director de club
          │                  │                     │
          └──────────────┬───┴─────────────────────┘
                         ▼
              ┌───────────────────┐
              │   Interfaz web    │        templates/ (Jinja2) + app.py
              │  (presentación)   │        (plantillas y rutas)
              └──────────┬────────┘
                         ▼
              ┌───────────────────┐
              │ Lógica de         │        app.py (rutas, control de
              │  aplicación /     │        sesión, casos de uso)
              │  casos de uso     │
              └──────────┬────────┘
                         ▼
              ┌───────────────────┐
              │      Dominio      │        data.py (entidades) +
              │  reglas y cálculos│        calc.py (lógica de negocio)
              └──────────┬────────┘
                         ▼
              ┌───────────────────┐
              │ Acceso a datos    │        persist.py (repositorio)
              │  (repositorio)    │
              └──────────┬────────┘
                         ▼
              ┌───────────────────┐
              │   SQLite  .db     │
              └───────────────────┘
```

**Justificación de la decisión:**

- **Monolítica:** el dominio es pequeño y está bien delimitado (evaluación de clubes). Una solución monolítica en capas es más simple de desarrollar, probar y mantener que un conjunto de microservicios.
- **Separación de responsabilidades:** la presentación (`templates/`, rutas en `app.py`), las entidades (`data.py`), la lógica de cálculo (`calc.py`) y la persistencia (`persist.py`) están separadas, lo que permite evolucionar cada capa de forma independiente.
- **Facilidad de migración futura:** si la organización crece o se requiere una API o aplicación móvil, la lógica de negocio de `calc.py` puede reutilizarse sin cambios porque no depende de la base de datos.

## 12. Aplicación de principios SOLID

### 12.1 Single Responsibility Principle (SRP)

Cada módulo tiene una única responsabilidad:
- `data.py` solo define las entidades del dominio (dataclasses).
- `calc.py` solo contiene la lógica de cálculo (ponderación, rankings, desempates).
- `persist.py` solo serializa y persiste el estado.
- `app.py` solo atiende peticiones HTTP y coordina las demás capas.

Una entidad como `Evaluacion` no se encarga de calcularse ni guardarse a sí misma; esas responsabilidades viven en `calc.py` y `persist.py`.

### 12.2 Open/Closed Principle (OCP)

El sistema está diseñado para extenderse sin modificar el núcleo:
- Los **criterios** de un evento son datos configurables: se agregan nuevos criterios sin tocar el modelo.
- Los **motivos de penalización** se gestionan como catálogo: un nuevo motivo no exige cambios en `calc.py`.
- El cálculo de rankings de `calc.py` itera sobre criterios y evaluaciones genéricas; agregar un nuevo tipo de evento no obliga a modificar la fórmula.

### 12.3 Dependency Inversion Principle (DIP)

La lógica de dominio no depende de la base de datos concreta:
- `calc.py` trabaja sobre los objetos del dominio (listas de evaluaciones, criterios, eventos) y no conoce SQLite.
- `persist.py` actúa como intermediario: `app.py` pide “guardar el estado actual” y el repositorio decide cómo (SQLite, y más adelante cualquier otra base).

```
   Caso de uso (app.py)
        │
        ▼
   persist.save / persist.load     ← interfaz de persistencia
        ▲
        │
   Implementación SQLite
```

Esto permite, en el futuro, reemplazar el almacenamiento sin modificar el resto del sistema.

**Nota:** se analizan tres principios (SRP, OCP y DIP) por ser los más directamente observables en la solución actual; LSP e ISP pueden incorporarse en etapas posteriores.

## 13. Patrones de diseño propuestos

### 13.1 Patrón Repository (Acceso a datos)

**`persist.py`** implementa un repositorio: el resto del sistema manipula objetos de dominio (clubs, eventos, evaluaciones) y delega en el repositorio la tarea de guardarlos y recuperarlos (es un Adapter sobre SQLite). Esto aísla el resto de la aplicación de los detalles de la base de datos y justifica el principio DIP.

**Ventajas:** cambios de motor de base de datos, esquema o serialización solo afectan a `persist.py`.

### 13.2 Patrón Factory (Creación de usuarios y entidades)

La creación de usuarios según rol (admin, staff, director) aparece repetida en `app.py` con `seed_data.Usuario(...)`. Se propone centralizar esta creación en una **fábrica de usuarios**:

```
             UsuarioFactory
                  │
      ┌───────────┼──────────────┐
      ▼           ▼              ▼
  Usuario      Usuario        Usuario
   Admin        Staff          Director
 (org)        (evento)         (club)
```

**Ventajas:** se evita la repetición del código de construcción, se garantiza que cada tipo de usuario se inicialice con los campos correctos (evento_id para staff, club_id para director) y se simplifica la generación masiva de accesos.

**Justificación de uso:** se eligieron estos patrones porque responden a necesidades reales del sistema (persistencia desacoplada y creación variada de usuarios), no por obligación académica.

## 14. Consideración de DDD

- **Dominio:** evaluación y calificación del desempeño de clubes de Conquistadores en eventos y temporadas.
- **Entidad principal:** `Club` (identidad persistente: nombre, miembros, puntajes por temporada).
- **Entidades:** `Organizacion`, `Usuario`, `Miembro`, `Evento`, `Criterio`, `Evaluacion`, `Incidente`, `PenalizacionAplicada`, `MotivoPenalizacion`.
- **Objetos de valor:** `PorcentajePonderado`, `Puntaje`, `Temporada`, `EstadoEvento`, `EstadoIncidente`, `Gravedad`, `Fecha`.
- **Estados del evento:**

```
    ABIERTO
       │
       ▼ (suma de pesos = 100% y cierre)
    CERRADO
```

- **Estados del incidente:**

```
    ABIERTO  →  EN_REVISION  →  RESUELTO
```

**Reglas de negocio identificadas:**
- La suma de los pesos de los criterios de un evento debe ser 100% para cerrarlo.
- La evaluación oficial de un club es la del staff principal asignado.
- El desempate entre clubes se resuelve comparando el criterio de mayor peso.
- El puntaje de temporada es la suma de puntajes por evento menos las penalizaciones.

## 15. Prototipo

Se cuenta con un **prototipo funcional** implementado con Flask y plantillas Jinja2 en `templates/`. Las pantallas principales son:

| Pantalla | Ruta | Funcionalidad |
|---|---|---|
| Inicio / Login | `index.html`, `login.html` | Autenticación por usuario y contraseña, redirección según rol |
| Registro | `registro.html` | Alta de organización + administrador inicial |
| Dashboard admin | `admin/dashboard.html` | Indicadores: eventos activos/próximos, miembros, staff |
| Clubes | `admin/clubes.html`, `club_miembros.html` | CRUD de clubes y miembros, importación Excel |
| Eventos | `admin/eventos.html`, `evento_detalle.html` | Creación, criterios, asignación, generación de accesos |
| Incidentes | `admin/incidentes.html` | Registro, filtros y cambio de estado |
| Penalizaciones | `admin/motivos.html`, `penalizaciones.html` | Catálogo de motivos y aplicación de descuentos |
| Resultados | `admin/resultados.html`, `reportes.html` | Rankings y exportación Excel/PDF |
| Panel staff | `staff/panel.html` | Evaluación por criterio, incidentes y penalizaciones |
| Panel director | `director/panel.html` | Posición y puntajes de su club |

El prototipo valida el flujo de interacción end-to-end: desde la creación del evento hasta la exportación del ranking, pasando por la evaluación y las penalizaciones.

## 16. Planificación inicial

| Etapa | Actividad | Producto |
|---|---|---|
| 1 | Análisis del problema | Problema y contexto |
| 2 | Levantamiento de requerimientos | Requerimientos e historias de usuario |
| 3 | Diseño arquitectónico | Arquitectura propuesta |
| 4 | Diseño del dominio | Entidades y reglas de negocio |
| 5 | Diseño de interfaz | Prototipo |
| 6 | Implementación inicial | Primer incremento funcional |
| 7 | Integración | Sistema integrado |
| 8 | Pruebas | Evidencias de pruebas |
| 9 | Refactorización | Versión mejorada |
| 10 | Presentación final | Producto terminado |

El proyecto ya cuenta con un primer incremento implementado (módulos de clubes, eventos, criterios, evaluaciones, rankings y exportación), de modo que las etapas 1 a 8 corresponde consolidarlas, documentarlas y refinar la solución.

## 17. Conclusiones

- El problema de la evaluación manual de clubes es real y genera errores y falta de trazabilidad; ScoreUp lo aborda centralizando la información y automatizando los cálculos.
- La arquitectura en capas (interfaz → casos de uso → dominio → repositorio) permite un mantenimiento simple y deja abierta la evolución futura del sistema.
- Los principios SRP, OCP y DIP se aplican de forma concreta en la separación de `app.py`, `data.py`, `calc.py` y `persist.py`.
- Los patrones Repository y Factory responden a necesidades puntuales (persistencia desacoplada y creación variada de usuarios), evitando su uso artificial.
- El prototipo funcional demuestra la viabilidad técnica de la propuesta y constituye la línea base para las siguientes etapas del Taller de Programación.

## 18. Referencias bibliográficas

- Martin, R. C. (2018). *Clean Architecture: A Craftsman's Guide to Software Structure and Design.* Prentice Hall.
- Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements of Reusable Object-Oriented Software.* Addison-Wesley.
- Evans, E. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software.* Addison-Wesley.
- Flask Documentation. https://flask.palletsprojects.com/
- Documentación de Python (dataclasses, sqlite3). https://docs.python.org/