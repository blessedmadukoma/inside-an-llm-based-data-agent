"""Create data/kenya.sqlite: one table, seven made-up people."""

import sqlite3

from llm import DB_PATH

ROWS = [
    (1, "Amina", "Nairobi", "R"),
    (2, "Brian", "Nairobi", "R"),
    (3, "Chege", "Nairobi", "V"),
    (4, "Daudi", "Coast", "R"),
    (5, "Esther", "Coast", "R"),
    (6, "Faith", "Coast", "R"),
    (7, "Grace", "Nairobi", "V"),
]


def make_db():
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE ke_table (id INTEGER, name TEXT, region TEXT, status TEXT)")
    con.executemany("INSERT INTO ke_table VALUES (?, ?, ?, ?)", ROWS)
    con.commit()
    con.close()


if __name__ == "__main__":
    make_db()
    print(f"Created {DB_PATH}")
