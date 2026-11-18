"""Rebuild the text that gpt-oss reads for the first request in a trace.

The provider applies the model's chat template (the harmony format) before the
model runs, and the API never returns that text. This script rebuilds it with
OpenAI's harmony library, so the provider's real text can differ in details.

    uv run --group template python render_template.py traces/people_seed2.json
"""

import json
import sys

from openai_harmony import (
    Conversation,
    DeveloperContent,
    HarmonyEncodingName,
    Message,
    ReasoningEffort,
    Role,
    SystemContent,
    ToolDescription,
    load_harmony_encoding,
)

EFFORT = {"low": ReasoningEffort.LOW, "medium": ReasoningEffort.MEDIUM, "high": ReasoningEffort.HIGH}


def main():
    trace = json.load(open(sys.argv[1], encoding="utf-8"))
    request = trace["calls"][0]["request"]
    enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)

    system = SystemContent.new().with_reasoning_effort(EFFORT[request.get("reasoning_effort", "medium")])
    tools = [
        ToolDescription.new(t["function"]["name"], t["function"]["description"], parameters=t["function"]["parameters"])
        for t in request.get("tools", [])
    ]
    messages = [Message.from_role_and_content(Role.SYSTEM, system)]
    if tools:
        messages.append(Message.from_role_and_content(Role.DEVELOPER, DeveloperContent.new().with_function_tools(tools)))
    for m in request["messages"]:
        if m["role"] == "user":
            messages.append(Message.from_role_and_content(Role.USER, m["content"]))

    ids = enc.render_conversation_for_completion(Conversation.from_messages(messages), Role.ASSISTANT)
    print(enc.decode(ids))
    print(f"\n{len(ids)} tokens. The provider counted {trace['calls'][0]['response']['usage']['prompt_tokens']}.")
    question = trace["question"]
    print("Tokens in the question:", [(enc.decode([i]), i) for i in enc.encode(question, allowed_special=set())])


if __name__ == "__main__":
    main()
