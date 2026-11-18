# ScoreUp en Vercel + Supabase

Esta opción necesita internet. Para campamentos sin conexión, sigue el [README](../README.md) y usa SQLite local. Las instalaciones son independientes: no hay sincronización automática entre SQLite y Supabase.

## Desplegar

1. Crea un proyecto Supabase y copia la URI de **Connect → Transaction pooler → URI** (puerto 6543).
2. Sustituye `[YOUR-PASSWORD]` por tu contraseña de base de datos, sin los corchetes. Codifica los caracteres especiales de la contraseña como parte de una URL; no encierres el host entre corchetes.
3. Importa `JuanFernandoNina/scoreup` en Vercel, raíz del repositorio y framework Flask. Conserva la configuración de `pyproject.toml` y `vercel.json`.
4. Configura estas variables en el entorno que vayas a desplegar:

| Variable | Valor |
|---|---|
| `SCOREUP_DB_BACKEND` | `postgres` |
| `DATABASE_URL` | URI privada del transaction pooler |
| `SECRET_KEY` | Clave aleatoria privada y estable |
| `PUBLIC_BASE_URL` | URL pública HTTPS, sin barra final |
| `SCOREUP_QR_BACKEND` | `opencv` |

Si no defines `PUBLIC_BASE_URL`, se deriva de `VERCEL_URL`. Mantén una dirección estable para los QR. No publiques `.env`, contraseñas ni claves. Una clave nueva invalida los QR anteriores.

5. Despliega. Si cambias variables después, haz **Redeploy**.

El esquema se crea automáticamente. PostgreSQL conserva los datos y las evidencias como `BYTEA`; no se necesita Supabase Storage ni service-role key. Las conexiones usan TLS y prepared statements desactivados. Las escrituras se serializan con un advisory lock de transacción.

## Copiar datos locales (opcional)

Desde PowerShell en la raíz, con tu entorno instalado:

```powershell
.\.venv\Scripts\python.exe -m pip install "psycopg[binary]>=3.2,<4"
$env:DATABASE_URL = "PEGAR_URI_PRIVADA_AQUI"
.\.venv\Scripts\python.exe scripts\migrate_supabase.py
```

Primero revisa el simulacro. Para aplicar:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_supabase.py --apply
Remove-Item Env:DATABASE_URL
```

El script copia `scoreup.db` y `static/uploads`. No altera la fuente. Rechaza un destino con datos: **no uses `--replace` a menos que quieras reemplazar los datos cloud**. La URI no se imprime por el script; no compartas tu historial de terminal ni capturas con secretos.

## Estáticos, QR y errores

- Vercel instala `pyproject.toml`, sin QReader/PyTorch. OpenCV lee imágenes sin descargar modelos.
- El build copia los estáticos a `public/static`, excepto `uploads`. Las evidencias se sirven por rutas autenticadas.
- Comprime las fotos: el límite de Vercel Functions puede ser menor que los 10 MB permitidos localmente.
- Ante un 500, consulta **Runtime Logs**. Una URI con host entre corchetes falla antes de conectar; un error de autenticación requiere revisar contraseña/usuario.
- Comprueba login de cada rol, QR Staff y director, evidencia y proyección después del despliegue. Crear las tablas no carga tus datos ni certifica esos flujos.

## Rendimiento de la persistencia cloud

- Cada operación carga un snapshot consistente con **una consulta SQL**, en vez de once consultas independientes. Por compatibilidad con las rutas actuales, el snapshot todavía contiene las once tablas operativas; no es una consulta limitada a la pantalla ni un caché compartido entre usuarios.
- Los guardados comparan con la línea de base de esa transacción y escriben **solo filas nuevas, modificadas o eliminadas**. Un cambio de evento no borra y reinserta usuarios, clubes o notas sin cambios.
- Las filas de cada tabla se envían en bloque mediante `jsonb_populate_recordset` y las sentencias se agrupan con el pipeline de psycopg. Los guardados sin cambios no ejecutan escrituras.
- El login y la lectura de una imagen QR no toman el lock de escritura ni guardan las tablas. Portada/login/registro anónimos y recursos estáticos públicos no requieren una conexión a la base. Las evidencias siguen autenticadas, también por sus rutas antiguas de uploads.
- Se conservan el advisory lock para modificaciones, transacciones, unicidad oficial, control de versión y filtros de permisos. No se reutilizan snapshots entre peticiones ni se publica un caché global de datos.

En una base local ficticia de **65 registros**, cargar y guardar el cambio de un evento pasó de **87 sentencias a 2** (una lectura y una escritura). Esa comparación excluye conexión, inicio y fin de transacción; **no es una medición del tiempo ni del rendimiento real de Vercel/Supabase**.

### Aplicar la actualización

Despliega el nuevo commit de GitHub (o haz Redeploy si no hay despliegue automático). Esta optimización no requiere cambiar variables, recrear tablas ni volver a importar datos. **No ejecutes `--replace` para aplicar una actualización de código.**

Si persiste latencia, compara la región de las Functions de Vercel con la región de Supabase y elige regiones cercanas, según tu plan. Revisa duración en Runtime Logs; la conexión, la red, el arranque en frío y el tamaño del snapshot aún pueden afectar la respuesta. Para un volumen mucho mayor será necesario pasar a consultas específicas por pantalla/organización.

### Pruebas PostgreSQL locales (desarrollo)

`tests/test_pg_store.py` prueba deltas y cantidad de sentencias sin necesitar un servidor. Para integración real, prepara **una base local descartable con TLS cuyo nombre termine en `_test`** e instala `psycopg[binary]`. Nunca uses la URI de Supabase de producción:

```powershell
$env:SCOREUP_TEST_DATABASE_URL = "postgresql://postgres@127.0.0.1:55433/scoreup_perf_test?sslmode=require"
.\.venv\Scripts\python.exe tests\manual_postgres.py
Remove-Item Env:SCOREUP_TEST_DATABASE_URL
```

El script rechaza servidores no locales y nombres sin ese sufijo, porque reemplaza datos de esa base de prueba. Comprueba conservación de filas no modificadas, JSON, rollback de evidencias, concurrencia, login/roles, formularios/versiones, aislamiento, proyección y migración explícita.
