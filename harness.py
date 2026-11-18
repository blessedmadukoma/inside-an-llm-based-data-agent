"""Ask the data agent one question and print its answer.

    uv run python harness.py "Find the region with the most people in Kenya."
    uv run python harness.py --layer layers/kenya.md "Find the region with the most residents in Kenya."

Add --trace traces/<name>.json to save the prompt and every request and response.
"""

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

import llm
from llm import DB_PATH, chat, make_client, run_sql
from make_db import make_db

MAX_TOOL_CALLS = 15

TASK = (
    "Answer the question below by querying the SQLite database with the "
    "run_sql tool. You can call it as many times as you need."
)
ANSWER_FORMAT = "End your answer with the final query in a ```sql block."


def get_schema():
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return "\n\n".join(sql for (sql,) in rows if sql)
    finally:
        db.close()


def read_layer(path):
    if not path:
        return "", None
    raw = Path(path).read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def build_prompt(schema, layer_text, question):
    parts = [TASK, f"Database schema:\n```sql\n{schema}\n```"]
    if layer_text:
        parts.append(f"Domain definitions:\n{layer_text}")
    parts += [f"Question:\n{question}", ANSWER_FORMAT]
    return "\n\n".join(parts)


def extract_final_sql(text):
    blocks = re.findall(r"```sql\s*(.*?)```", text or "", re.I | re.S)
    return blocks[-1].strip() if blocks else None


def handle_call(arguments, calls_used):
    try:
        query = json.loads(arguments)["query"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return arguments, f"ERROR: invalid tool arguments ({e})"
    if calls_used > MAX_TOOL_CALLS:
        return query, "ERROR: tool call limit reached"
    return query, run_sql(query)


def run_chat(client, cfg, prompt, seed):
    messages = [{"role": "user", "content": prompt}]
    calls_used = 0
    while True:
        response = chat(client, cfg, messages, seed=seed, tools=True)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        calls = []
        for call in message.tool_calls or []:
            calls_used += 1
            query, result = handle_call(call.function.arguments, calls_used)
            calls.append(call.id)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        if not calls:
            return "answered", message.content or ""
        if calls_used >= MAX_TOOL_CALLS:
            return "step_limit", message.content or ""


def main():
    parser = argparse.ArgumentParser(description="Ask the data agent one question.")
    parser.add_argument("question")
    parser.add_argument("--layer", help="a semantic layer file to add to the prompt")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--trace", help="save the prompt and every request and response here")
    args = parser.parse_args()

    make_db()
    cfg, client = make_client("gpt-oss")
    schema = get_schema()
    layer_text, layer_sha256 = read_layer(args.layer)
    prompt = build_prompt(schema, layer_text, args.question)
    status, answer = run_chat(client, cfg, prompt, seed=args.seed)

    print(answer)
    final_sql = extract_final_sql(answer)
    if final_sql:
        print(f"\nThe final query, run again: {run_sql(final_sql)}")
    print(f"Stop reason: {status}. Model calls: {len(llm.CALLS)}.")

    if args.trace:
        Path(args.trace).parent.mkdir(parents=True, exist_ok=True)
        Path(args.trace).write_text(json.dumps({
            "question": args.question,
            "seed": args.seed,
            "layer": args.layer,
            "layer_sha256": layer_sha256,
            "prompt": prompt,
            "status": status,
            "answer": answer,
            "calls": llm.CALLS,
        }, indent=2, ensure_ascii=False))
        print(f"Trace saved to {args.trace}")


if __name__ == "__main__":
    main()
