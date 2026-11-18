"""The model client and the one tool, run_sql."""

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DB_PATH = Path(__file__).parent / "data" / "kenya.sqlite"
MAX_ROWS = 50

MODELS = {
    "gpt-oss": {
        "base_url": "https://ollama.com/v1",
        "key": os.getenv("OLLAMA_API_KEY"),
        "model": "gpt-oss:120b",
        "settings": {
            "temperature": 1.0,
            "top_p": 1.0,
            "reasoning_effort": "medium",
        },
    },
}

RUN_SQL = {
    "name": "run_sql",
    "description": "Run a read-only SQLite query on the database.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}

# Every request and response that chat() sends and receives, for --trace.
CALLS = []


def make_client(name):
    if name not in MODELS:
        raise ValueError(f"Unknown model {name!r}. Choose from: {', '.join(MODELS)}")
    cfg = MODELS[name]
    if not cfg["key"]:
        raise RuntimeError("No API key. Copy .env.example to .env and set OLLAMA_API_KEY.")
    return cfg, OpenAI(base_url=cfg["base_url"], api_key=cfg["key"])


def chat(client, cfg, messages, seed=1, tools=False):
    request = {
        "model": cfg["model"],
        "messages": messages,
        "seed": seed,
        **cfg["settings"],
    }
    if tools:
        request["tools"] = [{"type": "function", "function": RUN_SQL}]
    response = client.chat.completions.create(**request)
    CALLS.append({
        "request": json.loads(json.dumps(request, default=str)),
        "response": response.model_dump(exclude_none=True),
    })
    return response


def run_sql(query):
    cleaned = re.sub(r"^\s*(--[^\n]*\n|/\*[\s\S]*?\*/\s*)*", "", query)
    if not re.match(r"(?is)^(select|with|pragma)\b", cleaned):
        return "ERROR: only SELECT, WITH or PRAGMA queries are allowed."

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    deadline = time.monotonic() + 10
    db.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        cur = db.execute(query)
        columns = [col[0] for col in cur.description] if cur.description else []
        rows, row_count = [], 0
        for row in cur:
            row_count += 1
            if len(rows) < MAX_ROWS:
                rows.append(list(row))
        return json.dumps({"columns": columns, "rows": rows, "row_count": row_count})
    except sqlite3.Error as e:
        return f"ERROR: {e}"
    finally:
        db.close()
