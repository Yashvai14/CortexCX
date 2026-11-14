"""Distinct customer-facing messages for situations that used to share one canned line.

  offer_text       the knowledge base cannot answer: say so honestly and OFFER the team (nothing is escalated yet)
  tool_failure     a business system (orders, stock...) errored: nothing is wrong with the customer's request
  internal_error   the pipeline itself failed: apologise, ask to resend, never claim anyone was contacted
  already_with_team / agent_ack   the customer already has an open request with a person

A message containing OFFER_MARKER is how the next turn knows a yes/no answers an offer (conversation state is
derived from the stored messages, so no extra table or migration is needed).
"""
import hashlib

OFFER_MARKER = "bring in the team"

_OFFERS = {
    "no_knowledge": [
        "I don't have that information in front of me, and I don't want to guess. Would you like me to bring in the team to look into it?",
        "I'm not able to find that in what I have, and I'd rather not give you wrong information. Want me to bring in the team to check?",
    ],
    "complaint": [
        "I'm really sorry about that. I can't find the exact steps for this one. Would you like me to bring in the team to help?",
        "That's frustrating, I'm sorry. I don't have a clear answer for this, so would you like me to bring in the team?",
    ],
    "conflict": [
        "I'm seeing two different versions of this in our records, and I don't want to give you the wrong one. Shall I bring in the team to confirm it?",
    ],
}
_ALREADY = [
    "Your request is already with the team, and they'll reply here as soon as they can. Anything I can help with in the meantime?",
    "The team already has your request. They'll get back to you here. Is there anything else I can help with while you wait?",
]
_AGENT_ACK = [
    "Got it, I've added that for the team.",
    "Noted, I've passed that on.",
    "Thanks, I've shared that with the team too.",
]
TOOL_FAILURE = "I'm having trouble checking that right now. Could you try again in a few minutes?"
INTERNAL_ERROR = "Sorry, something went wrong on my side. Could you send that again in a moment?"


def _pick(pool: list[str], seed: str, recent: list[str]) -> str:
    start = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(pool)
    recent_l = [r.strip().lower() for r in recent]
    for i in range(len(pool)):
        cand = pool[(start + i) % len(pool)]
        if cand.strip().lower() not in recent_l:
            return cand
    return pool[start]


def offer_text(kind: str, seed: str = "", recent: list[str] | None = None) -> str:
    return _pick(_OFFERS.get(kind, _OFFERS["no_knowledge"]), seed or kind, recent or [])


def already_with_team(seed: str = "", recent: list[str] | None = None) -> str:
    return _pick(_ALREADY, seed or "already", recent or [])


def agent_ack(seed: str = "", recent: list[str] | None = None) -> str:
    return _pick(_AGENT_ACK, seed or "ack", recent or [])


def is_offer(text: str | None) -> bool:
    return bool(text) and OFFER_MARKER in text.lower()
