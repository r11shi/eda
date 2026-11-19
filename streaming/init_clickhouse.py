"""Creates the ClickHouse real-time warehouse tables from streaming/clickhouse_ddl.sql."""
import re
from pathlib import Path
import clickhouse_connect

sql = Path(__file__).with_name("clickhouse_ddl.sql").read_text()
sql = re.sub(r"--[^\n]*", "", sql)                      # drop comments (they may contain semicolons)
client = clickhouse_connect.get_client(host="127.0.0.1", port=8123)
for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
    client.command(stmt)
print("ClickHouse tables:", [r[0] for r in client.query("SHOW TABLES FROM food").result_rows])
