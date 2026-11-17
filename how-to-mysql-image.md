
To load the image from DockerHub

The dump comes from a server with case-insensitive table names, so the
`--lower_case_table_names=1` flag is required (it must be set when the container is created).

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
- Creates `'sg_dev'@'localhost'` with the `sg_dev_pwd` password and `ALL PRIVILEGES` on `sg_dev.*`. It is safe to re-run.
- Note: `'sg_dev'@'localhost'` only works from inside the container, e.g. `docker exec -it mysql57 mysql -usg_dev -p sg_dev`. From the host, connect as `root`.
