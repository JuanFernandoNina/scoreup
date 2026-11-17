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
