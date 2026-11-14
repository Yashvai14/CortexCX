def sub(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert old in s, (path, old[:90])
    open(path, "w", encoding="utf-8").write(s.replace(old, new, 1))

R = "D:/CortexCX/backend/app/ai/routing/router.py"
sub(R, '''            route = Route(str(data["route"]).upper())''', '''            route = _ROUTE_ALIASES[str(data["route"]).upper().strip()]''')
sub(R, '''class IntentRouter:
    """Stateless; construct once or use the classmethods."""''', '''_ROUTE_ALIASES: dict[str, Route] = {
    "DIRECT": Route.DIRECT, "DIRECT_CONVERSATION": Route.DIRECT,
    "RAG": Route.RAG, "RAG_KNOWLEDGE": Route.RAG,
    "TOOLS": Route.TOOLS, "TOOL": Route.TOOLS, "BUSINESS_TOOL": Route.TOOLS,
    "ESCALATE": Route.ESCALATE, "HUMAN_ESCALATION": Route.ESCALATE,
    "CLARIFY": Route.CLARIFY, "CLARIFICATION": Route.CLARIFY,
}


class IntentRouter:
    """Stateless; construct once or use the classmethods."""''')
sub(R, '''        "ESCALATE = a person must handle it (asks for a human, legal/payment dispute, account security).\n"''',
       '''        "ESCALATE = a person must handle it (explicitly asks for a human, legal/payment dispute, account security). "
        "Never ESCALATE a greeting, thanks, correction, confusion or an ambiguous message.\n"
        "CLARIFY = too ambiguous to act on: ask one short clarifying question.\n"''')
sub(R, '''DIRECT|RAG|TOOLS|ESCALATE", "confidence"''', '''DIRECT|RAG|TOOLS|ESCALATE|CLARIFY", "confidence"''')
print("ok")
