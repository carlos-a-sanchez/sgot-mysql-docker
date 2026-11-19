#!/bin/bash
# Build-time only: initialize a datadir, load initdb/*.sql with lower_case_table_names=1
# (the dump was taken that way), so the image can then run with lower_case_table_names=0.
set -euo pipefail
D=/var/lib/mysql-sgot
S=/tmp/build.sock
mkdir -p "$D" && chown mysql:mysql "$D"
mysqld --initialize-insecure --user=mysql --datadir="$D" --lower_case_table_names=1
mysqld --user=mysql --datadir="$D" --lower_case_table_names=1 --skip-networking --socket="$S" &
for i in $(seq 60); do mysqladmin --socket="$S" -uroot ping >/dev/null 2>&1 && break; sleep 1; done
mysql --socket="$S" -uroot <<SQL
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
CREATE USER 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
GRANT ALL ON *.* TO 'root'@'%' WITH GRANT OPTION;
SQL
for f in /initdb/*.sql; do echo "Loading $f"; mysql --socket="$S" -uroot -p"${MYSQL_ROOT_PASSWORD}" < "$f"; done
mysqladmin --socket="$S" -uroot -p"${MYSQL_ROOT_PASSWORD}" shutdown
wait
