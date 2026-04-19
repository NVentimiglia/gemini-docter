"""Formatter: enforce 80-char line limit and RFC 2119 rule style."""

from __future__ import annotations

import re
import textwrap

MAX_LINE_LENGTH = 80
RFC2119_KEYWORDS = ("MUST", "MUST NOT", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "MAY", "MAY NOT")
_RFC2119_PATTERN = re.compile(r"\b(?:must|must not|shall|shall not|should|should not|may|may not)\b", re.IGNORECASE)


def enforce_rfc2119(rule: str) -> str:
    """Uppercase RFC 2119 keywords in a rule string."""
    def _upper(match: re.Match) -> str:
        return match.group(0).upper()
    return _RFC2119_PATTERN.sub(_upper, rule)


def wrap_rule(rule: str, max_length: int = MAX_LINE_LENGTH, indent: str = "  ") -> str:
    """Wrap a rule to max_length, preserving leading bullet markers."""
    if rule.startswith("- "):
        prefix = "- "
        body = rule[2:]
    else:
        prefix = ""
        body = rule

    subsequent_indent = indent if prefix else ""
    wrapped = textwrap.fill(
        body,
        width=max_length - len(prefix),
        initial_indent=prefix,
        subsequent_indent=subsequent_indent,
    )
    return wrapped


def format_rules_block(rules: list[str], max_length: int = MAX_LINE_LENGTH) -> list[str]:
    """Format and wrap a list of rules, enforcing RFC 2119 and line length."""
    formatted: list[str] = []
    for rule in rules:
        rule = enforce_rfc2119(rule)
        formatted.append(wrap_rule(f"- {rule}", max_length=max_length))
    return formatted


def format_example(example: str, threshold: int = 5) -> tuple[str, str | None]:
    """Format an example. If it exceeds the threshold, return a reference link and the content.

    Returns:
        (display_text, reference_content)
        If reference_content is None, the example stays inline.
    """
    lines = example.strip().splitlines()
    if len(lines) <= threshold:
        # Keep inline, but format nicely
        indented = "\n    ".join(lines)
        return f"  - Example:\n    {indented}", None

    # Move to reference
    ref_id = f"ref_{abs(hash(example)) % 10000}"
    return f"  - Example: (see references/{ref_id}.md)", example.strip()


def split_into_reference(rule: str, rule_index: int) -> tuple[str, str]:
    """Placeholder for rule splitting (can be expanded later if needed)."""
    return f"- {rule}", ""
