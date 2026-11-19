
To load the image from DockerHub

The dump comes from a server with case-insensitive table names, so the
`--lower_case_table_names=1` flag is required to load it (it must be set when the container is created). After loading, recreate the container with `--lower_case_table_names=0 --sql-mode=ORACLE` for the Oracle-like behavior; see README.md (Deploy, step 6) for the full procedure and the volume needed to keep the data.

```bash
docker run -d \
  --name mysql57 \
  --platform linux/amd64 \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=prado210 \
  mysql:5.7 \
  --lower_case_table_names=1
```


Connection string

```

connection_string = "mysql+pymysql://root:prado210@127.0.0.1:3306/root?charset=utf8mb4"

```

Load the dump

1. Create a `.env` file next to `load_dump.py` (keep it out of git, it holds passwords):

```
SQL_DATA_SOURCE=bkup_2026-05-24_23_00_01.sql
MYSQL_CONN_STR=mysql+pymysql://root:prado210@127.0.0.1:3306/root?charset=utf8mb4
sg_dev_pwd=prado210
```

- `SQL_DATA_SOURCE`: dump file (relative paths are resolved from the `.env` folder). It must be a plain `.sql` file; run `gunzip -k file.sql.gz` first if you only have the `.gz`.
- `MYSQL_CONN_STR`: connection string of the MySQL server (root user).
- `sg_dev_pwd`: password for the `sg_dev` user the script creates.

2. Make sure the container is running (`docker ps`), then install dependencies and run:

```bash
python3 -m venv .venv
.venv/bin/pip install pymysql python-dotenv cryptography
.venv/bin/python load_dump.py
```

What the script does:

- Loads the dump into the `sg_dev` database. **It drops and recreates `sg_dev`**, so any existing data in it is lost.
- Skips the dump's `mysql` system database section (use `--include-system` to load it anyway; not recommended on MySQL 5.7).
- Creates `'sg_dev'@'localhost'` and `'sg_dev'@'%'` with the `sg_dev_pwd` password and `ALL PRIVILEGES` on `sg_dev.*`. It is safe to re-run.
- `'sg_dev'@'localhost'` only matches connections made inside the container (`docker exec -it mysql57 mysql -usg_dev -p sg_dev`). `'sg_dev'@'%'` is what lets apps on the host (e.g. Java) connect through the published port 3306.

Connect from a Java app running on the host

```
jdbc:mysql://127.0.0.1:3306/sg_dev?useSSL=false&allowPublicKeyRetrieval=true&characterEncoding=utf8
user: sg_dev
password: value of sg_dev_pwd
```

- Driver: MySQL Connector/J 5.1.x (`com.mysql.jdbc.Driver`) or 8.x (`com.mysql.cj.jdbc.Driver`; may need `&serverTimezone=UTC`).
- MySQL has no per-user default database: the `/sg_dev` in the URL is what makes it the default schema (CLI: `mysql -usg_dev -p sg_dev`).
- `'%'` allows any client address. Fine for a local test container; to restrict it, publish the port on loopback only (`-p 127.0.0.1:3306:3306`).

Notes

- GlassFish admin console (container `glassfish3`) is served over plain HTTP: use `http://localhost:4848`, not `https://`.
