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


def split_into_reference(rule: str, rule_index: int) -> tuple[str, str]:
    """If a rule body exceeds 5 lines when wrapped, split into inline ref + detail.

    Returns (inline_rule, detail_block) where detail_block is markdown suitable
    for a references/ file.
    """
    wrapped_lines = wrap_rule(f"- {rule}").splitlines()
    if len(wrapped_lines) <= 5:
        return f"- {rule}", ""

    # Keep first sentence as the inline rule
    first_sentence_end = rule.find(". ")
    if first_sentence_end > 0:
        inline = rule[:first_sentence_end + 1]
        detail = rule[first_sentence_end + 2:]
    else:
        inline = rule[:120]
        detail = rule[120:]

    detail_block = f"### Rule {rule_index + 1}\n{detail.strip()}\n"
    return f"- {inline} (see rule {rule_index + 1})", detail_block
