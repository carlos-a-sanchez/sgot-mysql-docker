FROM mysql:5.7
ENV MYSQL_ROOT_PASSWORD=prado210
COPY initdb/ /docker-entrypoint-initdb.d/
CMD ["mysqld", "--lower_case_table_names=1"]
