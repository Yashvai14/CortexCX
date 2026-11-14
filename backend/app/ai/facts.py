"""Turn raw tool results into a short, plain-language fact sheet for the LLM.

Raw JSON invited two failure modes with small local models: quoting internal ids/SKUs to customers, and
mislabelling fields (an order's `created_at` was reported as "shipped on ..."). The fact sheet has no ids,
labels every date explicitly, and states what is NOT known.
"""
from typing import Any


def _date(iso: Any) -> str | None:
    return str(iso)[:10] if iso else None


def _money(v: Any, cur: str | None) -> str:
    try:
        return f"{float(v):.2f} {cur or 'USD'}"
    except (TypeError, ValueError):
        return str(v)


def render_facts(tool_results: list[Any]) -> str:
    lines: list[str] = []
    for r in tool_results:
        name = r.tool_name
        if not r.success:
            lines.append(f"- {name} failed; its information is unavailable. Do not guess it.")
            continue
        d = r.data

        if name == "order_tracking" and isinstance(d, dict):
            if d.get("found"):
                o = d["order"]
                bits = [f"Order {o['order_number']}: status is {o['status']}"]
                if o.get("carrier"):
                    bits.append(f"carrier {o['carrier']}")
                if o.get("tracking_number"):
                    bits.append(f"tracking number {o['tracking_number']}")
                if _date(o.get("estimated_delivery")):
                    bits.append(f"estimated delivery {_date(o['estimated_delivery'])}")
                if _date(o.get("created_at")):
                    bits.append(f"order placed on {_date(o['created_at'])}")
                bits.append(f"total {_money(o.get('total_amount'), o.get('currency'))}")
                lines.append("- " + "; ".join(bits) + ".")
                if o.get("items"):
                    items = ", ".join(f"{i['quantity']} x {i['product_name']}" for i in o["items"])
                    lines.append(f"  Items: {items}.")
                lines.append("  The shipping/dispatch date is NOT known; never state one.")
            elif d.get("verification_required"):
                lines.append(
                    "- The customer's order could not be shown yet: ask them for the email address used at checkout. "
                    "Reveal nothing else about the order."
                )
            else:
                lines.append("- No order matched those details. Say you could not find it and ask them to double-check.")

        elif name == "product_search" and isinstance(d, list):
            if not d:
                lines.append("- No matching products were found in the catalog.")
            for p in d[:5]:
                stock = f"{p['quantity_available']} in stock" if p.get("in_stock") else "sold out"
                lines.append(f"- {p['name']}: {_money(p['price'], p.get('currency'))}, {stock}. {p.get('description') or ''}".rstrip())

        elif name == "inventory_lookup" and isinstance(d, dict):
            if d.get("found"):
                i = d["inventory"]
                state = f"in stock ({i['quantity_available']} available)" if i["in_stock"] else "sold out"
                low = " Low stock: mention that it is selling fast." if i["in_stock"] and i.get("low_stock") else ""
                lines.append(f"- {i['product_name']} is {state}.{low}")
            else:
                lines.append("- That product was not found in the catalog.")

        elif name == "coupon_tool" and isinstance(d, dict):
            if "valid" in d:
                lines.append(
                    f"- Coupon is valid: {d['description']}." if d["valid"] else f"- Coupon is NOT valid: {d['reason']}"
                )
            elif d.get("code"):
                val = d["discount_value"]
                off = f"{val:g}% off" if d.get("discount_type") == "percentage" else f"{_money(val, 'USD')} off"
                lines.append(f"- Available offer: code {d['code']} gives {off}.")

        elif name == "policy_lookup" and isinstance(d, dict):
            if d.get("content"):
                lines.append(f"- {d.get('title', 'Policy')}: {d['content']}")
            # A missing policy *record* is not something to tell the customer (their policy lives in the uploaded
            # documents), so it adds nothing to the facts. Emitting it made small models say "we have no official
            # policy record" in the answer.

        else:
            lines.append(f"- {name}: {d}")
    return "\n".join(lines)
