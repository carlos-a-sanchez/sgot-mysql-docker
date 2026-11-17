# sgot-mysql-docker
Tool to build a mysql docker image with sgot data for testing

Runs a MySQL 5.7 container and loads the `sg_dev` database from a mysqldump file using `load_dump.py`.
See [how-to-mysql-image.md](how-to-mysql-image.md) for more detail (Java connection, `.env` values).

## Requirements

- Docker
- Python 3
- A plain `.sql` dump file (not committed to git; `gunzip -k file.sql.gz` if you only have the `.gz`)

## Deploy

1. Start the container. `--lower_case_table_names=1` is required (the dump comes from a case-insensitive server) and can only be set when the container is created.

```bash
docker run -d \
  --name mysql57 \
  --platform linux/amd64 \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=prado210 \
  mysql:5.7 \
  --lower_case_table_names=1
```

2. Wait ~30-40 seconds until MySQL accepts connections:

```bash
docker logs mysql57 2>&1 | tail -3
docker exec mysql57 mysqladmin -uroot -pprado210 ping
```

3. Create a `.env` file (ignored by git):

```
SQL_DATA_SOURCE=bkup_2026-05-24_23_00_01.sql
MYSQL_CONN_STR=mysql+pymysql://root:prado210@127.0.0.1:3306/root?charset=utf8mb4
sg_dev_pwd=prado210
```

4. Load the dump and create the `sg_dev` user:

```bash
python3 -m venv .venv
.venv/bin/pip install pymysql python-dotenv cryptography
.venv/bin/python load_dump.py
```

This drops and recreates `sg_dev`, skips the dump's `mysql` system database, and creates `sg_dev@localhost` and `sg_dev@%` with all privileges on `sg_dev.*`. It is safe to re-run.

5. Check:

```bash
docker exec mysql57 mysql -usg_dev -pprado210 sg_dev -e "show tables"
```

JDBC URL for apps on the host: `jdbc:mysql://127.0.0.1:3306/sg_dev?useSSL=false&allowPublicKeyRetrieval=true`

## Stop / start / remove

```bash
docker stop mysql57      # stop (data is kept)
docker start mysql57     # start again, no reload needed
docker logs -f mysql57   # follow logs
```

Remove the container completely (**deletes all data**; you will need to redo the Deploy steps):

```bash
docker rm -f mysql57
docker volume prune      # optional: removes the orphaned anonymous data volumes
```

To reset only the data, keep the container and re-run `.venv/bin/python load_dump.py`.

## Publish the image to Docker Hub (and keep it updated)

`docker commit` of a running container does **not** include the data (the MySQL image stores it in a volume), so the image is built from the `Dockerfile`, which copies `initdb/` into `/docker-entrypoint-initdb.d/`. The data is loaded the first time a container starts from the image (about 1-2 minutes). Users then just pull and run it:

```bash
docker run -d --name mysql57 --platform linux/amd64 -p 3306:3306 carlossanchezdocker/sgot-mysql57:latest
```

Root password and `sg_dev` password are both `prado210` (defined in `Dockerfile` and `initdb/02-users.sql`). `lower_case_table_names=1` is already set in the image.

**Warning:** the image contains the dump data. Publish it to a **private** Docker Hub repository unless the data is safe to share.

### First publish / every update

Run these whenever the dump changes (or the image needs a change):

```bash
# 1. Generate the init scripts from the dump (only the sg_dev part, header + data)
DUMP=bkup_2026-05-24_23_00_01.sql        # your SQL_DATA_SOURCE file
mkdir -p initdb
{ sed -n '1,/SQL_NOTES=0/p' "$DUMP"; sed -n '/DROP DATABASE IF EXISTS `sg_dev`/,$p' "$DUMP"; } > initdb/01-sg_dev.sql
# initdb/02-users.sql creates the sg_dev users (already in the repo folder; recreate it if missing)

# 2. Build (tag with a version and latest)
docker build --platform linux/amd64 -t carlossanchezdocker/sgot-mysql57:latest -t carlossanchezdocker/sgot-mysql57:2026-11-17 .

# 3. Quick test on another port (wait ~2 min for the load)
docker run -d --name sgot_test --platform linux/amd64 -p 3307:3306 carlossanchezdocker/sgot-mysql57:latest
docker exec sgot_test mysql -usg_dev -pprado210 sg_dev -e "show tables"
docker rm -f sgot_test

# 4. Publish
docker login
docker push carlossanchezdocker/sgot-mysql57:latest
docker push carlossanchezdocker/sgot-mysql57:2026-11-17
```

Use a new date/version tag on each update and keep pushing `latest`. Existing users get the update with:

```bash
docker pull carlossanchezdocker/sgot-mysql57:latest
docker rm -f mysql57        # deletes the old container and its data
docker run -d --name mysql57 --platform linux/amd64 -p 3306:3306 carlossanchezdocker/sgot-mysql57:latest
```

`initdb/` is git-ignored because it contains the data; regenerate it with step 1.
