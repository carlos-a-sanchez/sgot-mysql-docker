#!/usr/bin/env python3
"""Load a mysqldump file (SQL_DATA_SOURCE) into the MySQL server (MYSQL_CONN_STR), both read from .env.

.env example:
    SQL_DATA_SOURCE=bkup_2026-05-24_23_00_01.sql
    MYSQL_CONN_STR=mysql+pymysql://root:pass@127.0.0.1:3306/root?charset=utf8mb4

Usage:
    pip install pymysql python-dotenv
    python load_dump.py [--include-system] [--env-file .env]

By default sections of the dump targeting the `mysql` system database are skipped,
so the server's own system tables are not overwritten.
"""
import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pymysql
from dotenv import load_dotenv

SYSTEM_DBS = {"mysql"}
USE_RE = re.compile(r"^USE\s+`?([^`;\s]+)`?\s*;?$", re.I)
DELIM_RE = re.compile(r"^DELIMITER\s+(\S+)\s*$", re.I)


def connect(conn_str):
    u = urlparse(conn_str)
    q = parse_qs(u.query)
    return pymysql.connect(
        host=u.hostname or "127.0.0.1",
        port=u.port or 3306,
        user=unquote(u.username or "root"),
        password=unquote(u.password or ""),
        charset=q.get("charset", ["utf8mb4"])[0],
        autocommit=True,
        local_infile=False,
    )


def statements(path):
    """Yield SQL statements from a dump, honoring DELIMITER and quoted strings."""
    delim, buf, quote = ";", [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not buf and quote is None:
                s = line.strip()
                if not s or s.startswith("--"):
                    continue
                m = DELIM_RE.match(s)
                if m:
                    delim = m.group(1)
                    continue
            i, n = 0, len(line)
            while i < n:
                c = line[i]
                if quote:
                    if c == "\\":
                        i += 1
                    elif c == quote:
                        quote = None
                elif c in "'\"`":
                    quote = c
                i += 1
            buf.append(line)
            if quote is None and line.rstrip().endswith(delim):
                stmt = "".join(buf).rstrip()
                yield stmt[: -len(delim)].rstrip()
                buf = []
    if "".join(buf).strip():
        yield "".join(buf).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", default=str(Path(__file__).with_name(".env")))
    ap.add_argument("--include-system", action="store_true", help="also load the `mysql` system database section")
    args = ap.parse_args()

    load_dotenv(args.env_file)
    src, conn_str = os.getenv("SQL_DATA_SOURCE"), os.getenv("MYSQL_CONN_STR")
    if not src or not conn_str:
        sys.exit("SQL_DATA_SOURCE and MYSQL_CONN_STR must be set in the .env file")
    src = Path(src)
    if not src.is_absolute():
        src = Path(args.env_file).resolve().parent / src
    if not src.is_file():
        sys.exit(f"Dump file not found: {src}")

    conn = connect(conn_str)
    cur = conn.cursor()
    skipping, count = False, 0
    for stmt in statements(src):
        m = USE_RE.match(stmt)
        if m:
            skipping = m.group(1).lower() in SYSTEM_DBS and not args.include_system
            print(f"{'Skipping' if skipping else 'Loading'} database `{m.group(1)}`")
        elif re.match(r"(/\*!\d+\s+)?(DROP|CREATE)\s+DATABASE", stmt, re.I):
            db = re.search(r"`([^`]+)`", stmt).group(1).lower()
            skipping = db in SYSTEM_DBS and not args.include_system
        if skipping and not m:
            continue
        try:
            cur.execute(stmt)
        except pymysql.MySQLError as e:
            sys.exit(f"Error on statement #{count + 1}: {e}\n{stmt[:300]}")
        count += 1

    pwd = os.getenv("sg_dev_pwd")
    if not pwd:
        sys.exit("sg_dev_pwd must be set in the .env file to create the sg_dev user")
    for host in ("localhost", "%"):
        cur.execute("CREATE USER IF NOT EXISTS 'sg_dev'@%s IDENTIFIED BY %s", (host, pwd))
        cur.execute("ALTER USER 'sg_dev'@%s IDENTIFIED BY %s", (host, pwd))
        cur.execute(f"GRANT ALL PRIVILEGES ON `sg_dev`.* TO 'sg_dev'@'{host}'")
        print(f"User 'sg_dev'@'{host}' created with ALL PRIVILEGES on `sg_dev`.*")
    app_pwd = os.getenv("sgapp_pwd")
    if app_pwd:
        cur.execute("CREATE USER IF NOT EXISTS 'sgapp'@'%%' IDENTIFIED BY %s", (app_pwd,))
        cur.execute("ALTER USER 'sgapp'@'%%' IDENTIFIED BY %s", (app_pwd,))
        cur.execute("GRANT ALL ON `sg_dev`.* TO 'sgapp'@'%'")
        print("User 'sgapp'@'%' created with ALL PRIVILEGES on `sg_dev`.*")
    cur.execute("FLUSH PRIVILEGES")
    conn.close()
    print(f"Done: {count} statements executed from {src.name}")


if __name__ == "__main__":
    main()
