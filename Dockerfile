FROM mysql:5.7
ARG MYSQL_ROOT_PASSWORD=prado210
ENV MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
COPY build-data.sh /build-data.sh
COPY initdb/ /initdb/
COPY users.sql /initdb/02-users.sql
RUN /build-data.sh && rm -rf /initdb /build-data.sh
CMD ["mysqld", "--datadir=/var/lib/mysql-sgot", "--lower_case_table_names=0", "--sql-mode=ORACLE"]
