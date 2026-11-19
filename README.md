# sgot-mysql-docker
Tool to build a mysql docker image with sgot data for testing

Runs a MySQL 5.7 container and loads the `sg_dev` database from a mysqldump file using `load_dump.py`.
See [how-to-mysql-image.md](how-to-mysql-image.md) for more detail (Java connection, `.env` values).

## Requirements

- Docker
- Python 3
- A plain `.sql` dump file (not committed to git; `gunzip -k file.sql.gz` if you only have the `.gz`)

## Deploy

1. Start the container for loading. The dump was taken on a case-insensitive server, so it only loads with `--lower_case_table_names=1`. A named volume is used so the data survives step 6, where the container is recreated with the final settings.

```bash
docker run -d \
  --name mysql57 \
  --platform linux/amd64 \
  -p 3306:3306 \
  -v mysql57data:/var/lib/mysql \
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

6. Switch to the Oracle-like settings (`sql_mode=ORACLE`, `lower_case_table_names=0`) by recreating the container on the same volume:

```bash
docker rm -f mysql57        # the data stays in the mysql57data volume
docker run -d \
  --name mysql57 \
  --platform linux/amd64 \
  -p 3306:3306 \
  -v mysql57data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=prado210 \
  mysql:5.7 \
  --lower_case_table_names=0 --sql-mode=ORACLE
```

`sql_mode=ORACLE` equals `PIPES_AS_CONCAT,ANSI_QUOTES,IGNORE_SPACE,NO_KEY_OPTIONS,NO_TABLE_OPTIONS,NO_FIELD_OPTIONS,NO_AUTO_CREATE_USER`.

**Caveat:** tables are stored in lowercase (`sg_cliente`) but some triggers/views in the dump reference uppercase names (`SG_PARAMETRO`). With `lower_case_table_names=0` table names are case-sensitive, so use lowercase names in queries; objects referring to uppercase names may fail at runtime (check with the app).

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

## Reload the data (new dump) into an existing container

The dump only loads with `lower_case_table_names=1`, so a container running the final settings (`0` + `ORACLE`) has to be switched temporarily. The data lives in the `mysql57data` volume, so recreating the container does not lose it.

1. Point `SQL_DATA_SOURCE` in `.env` to the new dump (a plain `.sql` file).

2. Recreate the container with `lower_case_table_names=1` and wait until it is up:

```bash
docker rm -f mysql57
docker run -d --name mysql57 --platform linux/amd64 -p 3306:3306 \
  -v mysql57data:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=prado210 \
  mysql:5.7 --lower_case_table_names=1
docker exec mysql57 mysqladmin -uroot -pprado210 ping     # repeat until "mysqld is alive"
```

3. Load the dump (drops and recreates `sg_dev`, recreates the users):

```bash
.venv/bin/python load_dump.py
```

4. Recreate the container with the final settings:

```bash
docker rm -f mysql57
docker run -d --name mysql57 --platform linux/amd64 -p 3306:3306 \
  -v mysql57data:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=prado210 \
  mysql:5.7 --lower_case_table_names=0 --sql-mode=ORACLE
```

5. Check:

```bash
docker exec mysql57 mysql -usgapp -pAFF24BD045 sg_dev -e "select @@lower_case_table_names, @@sql_mode; show tables"
```

To also publish the new data as an image, continue with the section below (regenerate `initdb/` from the new dump, then build and push).

## Publish the image to Docker Hub (and keep it updated)

`docker commit` of a running container does **not** include the data (the MySQL image stores it in a volume), so the image is built from the `Dockerfile`. At build time `build-data.sh` creates a datadir (`/var/lib/mysql-sgot`, outside the volume), loads `initdb/*.sql` with `lower_case_table_names=1` (required by the dump), and the image then starts with `--lower_case_table_names=0 --sql-mode=ORACLE`. The data is already in the image, so containers start in seconds. Users just pull and run it:

```bash
docker rm -f mysql57 2>/dev/null   # a container named mysql57 (or anything using port 3306) must not exist; this deletes its data
docker run -d --name mysql57 --platform linux/amd64 -p 3306:3306 carlossanchezdocker/sgot-mysql57:latest
```

If you get `container name "/mysql57" is already in use` (or `port is already allocated`), an older container exists: remove it with `docker rm -f mysql57`, or use another name and port, e.g. `--name sgot -p 3307:3306`.

Root password and `sg_dev` password are both `prado210` (defined in `Dockerfile` and `users.sql`). Users are defined in `users.sql`: `sg_dev` (localhost and `%`) and `sgapp@%` (password in `users.sql`), both with all privileges on `sg_dev.*`. `sql_mode=ORACLE` and `lower_case_table_names=0` are already set in the image (see the table-name caveat above).

**Warning:** the image contains the dump data. Publish it to a **private** Docker Hub repository unless the data is safe to share.

### First publish / every update

Run these whenever the dump changes (or the image needs a change):

```bash
# 1. Generate the init scripts from the dump (only the sg_dev part, header + data)
DUMP=bkup_2026-05-24_23_00_01.sql        # your SQL_DATA_SOURCE file
mkdir -p initdb
{ sed -n '1,/SQL_NOTES=0/p' "$DUMP"; sed -n '/DROP DATABASE IF EXISTS `sg_dev`/,$p' "$DUMP"; } > initdb/01-sg_dev.sql
# users.sql (tracked in git) is copied by the Dockerfile as the 02 init script

# 2. Build (tag with a version and latest).
# Please notice the final point is part of the command, it refers to the current directory
docker build --platform linux/amd64 -t carlossanchezdocker/sgot-mysql57:latest -t carlossanchezdocker/sgot-mysql57:2026-11-17 .

## To validate the build
docker images | grep sgot lists the image

# 3. Quick test on another port
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
