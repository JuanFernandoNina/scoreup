# Arquitectura del sistema

## Enfoque general

ScoreUp es una **aplicación monolítica modular** escrita en Python.
Flask procesa las peticiones y Jinja2 genera las páginas HTML. Los cálculos y
la persistencia están separados en módulos, aunque varias reglas de negocio
siguen dentro de las rutas de `app.py`.

```text
Navegador: administrador / staff / director
                    |
                    v
        app.py + templates/ (Flask y Jinja2)
              |                |
              v                v
          calc.py           data.py
          Cálculos          Entidades
              \                /
               v              v
                   persist.py
                       |
                       v
                   SQLite
                 scoreup.db
```

## Responsabilidades

| Componente | Responsabilidad |
| --- | --- |
| `app.py` | Rutas HTTP, sesiones, permisos, formularios, QR y exportaciones. |
| `data.py` | Entidades con `dataclasses` y datos iniciales de demostración. |
| `calc.py` | Porcentajes, puntajes, rankings y desempates. |
| `persist.py` | Lectura, guardado, inicialización y migración de SQLite. |
| `templates/` | Vistas de administrador, staff y director. |
| `tests/test_scoreup.py` | Pruebas automáticas con bases temporales. |
| `docs/` y `mkdocs.yml` | Fuentes y configuración de este sitio independiente. |

La interfaz utiliza Tailwind CSS mediante CDN. La aplicación no debe
confundirse con el sitio estático generado por MkDocs.

## Entidades principales

- **Club**: pertenece a una organización y contiene miembros.
- **Usuario**: pertenece a una organización y tiene rol `admin`, `staff` o `director`.
- **Evento**: define fecha, temporada, puntaje máximo y estado de cierre.
- **Criterio**: pertenece a un evento y tiene un peso porcentual.
- **EventoClub**: registra la participación de un club en un evento.
- **Evaluacion**: relaciona evento, club, evaluador, valores y versión.
- **MotivoPenalizacion / PenalizacionAplicada**: definen y registran descuentos.
- **Incidente**: guarda descripción, gravedad, estado y evidencia opcional.

## Flujo de una evaluación

1. El staff accede a su evento, desde el panel o mediante el QR de un club.
2. La aplicación verifica sesión, rol, organización y participación del club.
3. Comprueba que el evento esté abierto y los criterios sumen 100 %.
4. Valida cada nota dentro del rango de 0 a 100.
5. Guarda la evaluación oficial o una corrección permitida.
6. Los rankings se calculan utilizando las evaluaciones oficiales.

## Reglas de cálculo

Para cada criterio se multiplica su nota por su peso dividido entre 100:

```text
porcentaje = suma(nota_criterio × peso_criterio / 100)
puntaje_evento = redondear(porcentaje / 100 × puntaje_máximo, 2)
puntaje_temporada = suma(puntajes_evento) − suma(penalizaciones_temporada)
```

**Ejemplo:** notas 80 y 90 con pesos 40 % y 60 % producen
`80 × 0.40 + 90 × 0.60 = 86 %`. Si el máximo es 200, el puntaje es **172**.

El ranking por evento no resta penalizaciones. Desempata usando la nota del
criterio de mayor peso; si el empate persiste, comparte posición. La temporada
descuenta las penalizaciones correspondientes a sus eventos.

## Integridad y seguridad

- Una evaluación oficial por club y evento, respaldada por una restricción SQLite.
- Correcciones solo por el autor y con control de versión del formulario.
- Criterios y participación bloqueados después de comenzar las evaluaciones.
- Cierre condicionado a pesos válidos y evaluaciones completas.
- Sesiones firmadas, contraseñas con hash y protección CSRF.
- Datos filtrados por organización y controles de acceso por rol.
- Recarga y guardado transaccional, con bloqueo de peticiones en el proceso.

!!! warning "No publicar archivos privados"
    No copies a `docs/` la base de datos, `.secret_key`, archivos `.env`,
    respaldos ni evidencias privadas. Todo lo que se incluya en el sitio
    podría distribuirse al publicar la documentación.

## Límites actuales

No hay microservicios ni una API REST pública independiente. Una fábrica de
aplicaciones y una capa completa de servicios serían posibles refactorizaciones,
no componentes ya implementados.
