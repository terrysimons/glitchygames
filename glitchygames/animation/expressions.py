"""Minimal expression parser for animation transition conditions.

Parses the `when` field from TOML transition rules into evaluable
expression objects. Does NOT use eval()/exec(). Custom recursive
descent parser with whitelisted operations.

Grammar (Python precedence: not > and > or; "and" and "or" are left-associative):
    expression    := or_expr
    or_expr       := and_expr ("or" and_expr)*
    and_expr      := not_expr ("and" not_expr)*
    not_expr      := "not" not_expr | primary
    primary       := "(" expression ")" | abs_expr | comparison | term
    abs_expr      := "abs" "(" term ")" [comparison_op term]
    comparison    := term comparison_op term
    term          := variable | number | "true" | "false"
    comparison_op := ">" | "<" | ">=" | "<=" | "==" | "!="
    variable      := identifier (looked up in context dict)
    number        := float literal

Reserved words (lowercase only, matched as whole words): and, or, not, abs, true, false.
Comparisons cannot be chained ("a < b < c" is an error; write "a < b and b < c").
"""

from __future__ import annotations

import re
from typing import Any, override

# Token patterns
_TOKEN_PATTERN = re.compile(
    r'\s*('
    r'>=|<=|==|!=|>|<'  # comparison operators
    r'|\('  # open paren
    r'|\)'  # close paren
    r'|-?\d+\.?\d*'  # numbers (including negative)
    r'|[a-zA-Z_]\w*'  # identifiers and keywords (keywords are matched as whole words)
    r')\s*'
)

_COMPARISON_OPERATORS = frozenset({'>', '<', '>=', '<=', '==', '!='})
_RESERVED_WORDS = frozenset({'and', 'or', 'not', 'abs', 'true', 'false'})
_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_]\w*$')


class Expression:
    """Base class for parsed expressions."""

    def evaluate(self, context: dict[str, Any]) -> bool | float:
        """Evaluate this expression against a context dict.

        Args:
            context: Variable name → value mapping.

        Returns:
            The result of evaluating this expression.

        """
        raise NotImplementedError


class VariableExpr(Expression):
    """A variable reference, looked up in the context dict."""

    def __init__(self, name: str) -> None:
        """Initialize with variable name."""
        self.name = name

    @override
    def evaluate(self, context: dict[str, Any]) -> bool | float:
        """Look up the variable. Unknown variables evaluate to False.

        Returns:
            The variable's value, or False if not in context.

        """
        return context.get(self.name, False)


class LiteralExpr(Expression):
    """A literal numeric or boolean value."""

    def __init__(self, value: float | bool) -> None:
        """Initialize with literal value."""
        self.value = value

    @override
    def evaluate(self, context: dict[str, Any]) -> bool | float:
        """Return the literal value.

        Returns:
            The literal value.

        """
        return self.value


class AbsExpr(Expression):
    """Absolute value: abs(inner)."""

    def __init__(self, inner: Expression) -> None:
        """Initialize with inner expression."""
        self.inner = inner

    @override
    def evaluate(self, context: dict[str, Any]) -> float:
        """Evaluate abs(inner).

        Returns:
            The absolute value of the inner expression.

        """
        return abs(float(self.inner.evaluate(context)))


class ComparisonExpr(Expression):
    """A comparison between two expressions: left op right."""

    def __init__(self, left: Expression, operator: str, right: Expression) -> None:
        """Initialize with left operand, operator, and right operand."""
        self.left = left
        self.operator = operator
        self.right = right

    @override
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate the comparison.

        Returns:
            True if the comparison holds.

        """
        left_value = float(self.left.evaluate(context))
        right_value = float(self.right.evaluate(context))

        if self.operator == '>':
            return left_value > right_value
        if self.operator == '<':
            return left_value < right_value
        if self.operator == '>=':
            return left_value >= right_value
        if self.operator == '<=':
            return left_value <= right_value
        if self.operator == '==':
            return left_value == right_value
        if self.operator == '!=':
            return left_value != right_value

        msg = f'Unknown operator: {self.operator}'
        raise ValueError(msg)


class AndExpr(Expression):
    """Logical and: left and right (short-circuiting)."""

    def __init__(self, left: Expression, right: Expression) -> None:
        """Initialize with left and right operands."""
        self.left = left
        self.right = right

    @override
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate left, and right only if left is truthy.

        Returns:
            True if both operands are truthy.

        """
        return bool(self.left.evaluate(context)) and bool(self.right.evaluate(context))


class OrExpr(Expression):
    """Logical or: left or right (short-circuiting)."""

    def __init__(self, left: Expression, right: Expression) -> None:
        """Initialize with left and right operands."""
        self.left = left
        self.right = right

    @override
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate left, and right only if left is falsy.

        Returns:
            True if either operand is truthy.

        """
        return bool(self.left.evaluate(context)) or bool(self.right.evaluate(context))


class NotExpr(Expression):
    """Logical negation: not operand."""

    def __init__(self, operand: Expression) -> None:
        """Initialize with the operand to negate."""
        self.operand = operand

    @override
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Negate the operand's truthiness.

        Returns:
            True if the operand is falsy.

        """
        return not self.operand.evaluate(context)


def tokenize(expression_string: str) -> list[str]:
    """Split an expression string into tokens.

    Args:
        expression_string: The `when` clause string from TOML.

    Returns:
        List of token strings.

    Raises:
        ValueError: If the expression contains invalid characters.

    """
    tokens = _TOKEN_PATTERN.findall(expression_string)

    # Verify we consumed the entire input (no invalid characters)
    reconstructed = ''.join(tokens)
    stripped_input = expression_string.replace(' ', '')
    if reconstructed != stripped_input:
        msg = f"Invalid characters in expression: '{expression_string}'"
        raise ValueError(msg)

    return tokens


def parse(expression_string: str) -> Expression:
    """Parse a `when` expression string into an Expression tree.

    Supports:
    - Bare variable: "on_ground" -> bool check
    - Comparison: "velocity_y < -10.0" -> compare
    - Abs comparison: "abs(velocity_x) > 0.1" -> abs + compare
    - Boolean literals: "true", "false"
    - Boolean operators and grouping: "velocity_y > 10 and not on_ground",
      "(a or b) and c" (precedence: not > and > or)

    Args:
        expression_string: The `when` clause from TOML.

    Returns:
        An Expression that can be evaluated against a context dict.

    Raises:
        ValueError: If the expression is malformed.

    """
    tokens = tokenize(expression_string)
    if not tokens:
        msg = f"Empty expression: '{expression_string}'"
        raise ValueError(msg)

    expression, remaining = _parse_or_expression(tokens)
    if remaining:
        if remaining[0] == ')':
            msg = f"Unbalanced parentheses: unexpected ')' in '{expression_string}'"
            raise ValueError(msg)
        msg = f'Unexpected tokens after expression: {remaining}'
        raise ValueError(msg)

    return expression


def _parse_or_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse or_expr := and_expr ("or" and_expr)*.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    left, remaining = _parse_and_expression(tokens)
    while remaining and remaining[0] == 'or':
        right, remaining = _parse_and_expression(remaining[1:])
        left = OrExpr(left=left, right=right)
    return left, remaining


def _parse_and_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse and_expr := not_expr ("and" not_expr)*.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    left, remaining = _parse_not_expression(tokens)
    while remaining and remaining[0] == 'and':
        right, remaining = _parse_not_expression(remaining[1:])
        left = AndExpr(left=left, right=right)
    return left, remaining


def _parse_not_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse not_expr := "not" not_expr | primary.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    if tokens and tokens[0] == 'not':
        if len(tokens) > 1 and tokens[1] in _COMPARISON_OPERATORS:
            msg = "Reserved word 'not' cannot be used as a variable"
            raise ValueError(msg)
        operand, remaining = _parse_not_expression(tokens[1:])
        return NotExpr(operand=operand), remaining
    return _parse_primary(tokens)


def _parse_primary(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse a parenthesized group, abs expression, comparison, or term.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    if not tokens:
        msg = 'Unexpected end of expression'
        raise ValueError(msg)

    first_token = tokens[0]

    if first_token in {'and', 'or'}:
        msg = f"Unexpected operator '{first_token}': it needs an expression on its left"
        raise ValueError(msg)

    if first_token == '(':
        return _parse_group(tokens)

    # abs( term ) [op term]
    if first_token == 'abs':
        return _parse_abs_expression(tokens)

    # Parse left side (variable or number)
    left, remaining = _parse_term(tokens)
    return _parse_optional_comparison(left=left, remaining=remaining)


def _parse_group(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse "(" expression ")".

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    inside = tokens[1:]
    if not inside:
        msg = "Unbalanced parentheses: missing ')'"
        raise ValueError(msg)
    if inside[0] == ')':
        msg = 'Empty parentheses'
        raise ValueError(msg)

    expression, remaining = _parse_or_expression(inside)
    if not remaining:
        msg = "Unbalanced parentheses: missing ')'"
        raise ValueError(msg)
    if remaining[0] != ')':
        msg = f"Expected ')' but got '{remaining[0]}'"
        raise ValueError(msg)
    return expression, remaining[1:]


def _parse_optional_comparison(
    left: Expression, remaining: list[str]
) -> tuple[Expression, list[str]]:
    """Parse an optional "comparison_op term" following the left operand.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    Raises:
        ValueError: If comparisons are chained.

    """
    if not remaining or remaining[0] not in _COMPARISON_OPERATORS:
        return left, remaining

    operator = remaining[0]
    right, remaining = _parse_term(remaining[1:])
    if remaining and remaining[0] in _COMPARISON_OPERATORS:
        msg = (
            f"Chained comparison is not supported (found '{remaining[0]}' after "
            f"'{operator}'); combine comparisons with 'and' instead"
        )
        raise ValueError(msg)
    return ComparisonExpr(left=left, operator=operator, right=right), remaining


def _parse_abs_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse abs(term) with an optional comparison.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    if len(tokens) < 2 or tokens[1] != '(':
        found = tokens[1] if len(tokens) > 1 else 'end of expression'
        msg = f"Reserved word 'abs' must be followed by '(', got '{found}'"
        raise ValueError(msg)

    inner, remaining = _parse_term(tokens[2:])

    if not remaining or remaining[0] != ')':
        msg = "Expected ')' to close abs()"
        raise ValueError(msg)

    abs_expr = AbsExpr(inner=inner)
    return _parse_optional_comparison(left=abs_expr, remaining=remaining[1:])


def _parse_term(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse a single term (variable, number, or boolean).

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    if not tokens:
        msg = 'Unexpected end of expression: expected a term'
        raise ValueError(msg)

    token = tokens[0]
    remaining = tokens[1:]

    # Boolean literals
    if token == 'true':
        return LiteralExpr(value=True), remaining
    if token == 'false':
        return LiteralExpr(value=False), remaining

    if token in _RESERVED_WORDS:
        msg = f"Reserved word '{token}' cannot be used as a variable"
        raise ValueError(msg)

    # Number
    try:
        value = float(token)
        return LiteralExpr(value=value), remaining
    except ValueError:
        pass

    # Variable (identifier)
    if _IDENTIFIER_PATTERN.match(token):
        return VariableExpr(name=token), remaining

    msg = f"Unexpected token: '{token}'"
    raise ValueError(msg)
