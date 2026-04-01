"""Minimal expression parser for animation transition conditions.

Parses the `when` field from TOML transition rules into evaluable
expression objects. Does NOT use eval()/exec(). Custom recursive
descent parser with whitelisted operations.

Phase 1 grammar:
    expression := abs_expr | comparison | bare_variable
    abs_expr   := "abs(" variable ")" comparison_op number
    comparison := term comparison_op term
    bare_variable := variable
    term       := variable | number
    comparison_op := ">" | "<" | ">=" | "<=" | "==" | "!="
    variable   := identifier (looked up in context dict)
    number     := float literal

Phase 2 (future, same `when` syntax): adds "and", "or", "not", parentheses.
"""

from __future__ import annotations

import re
from typing import Any, override

# Token patterns
_TOKEN_PATTERN = re.compile(
    r'\s*('
    r'>=|<=|==|!=|>|<'  # comparison operators
    r'|abs'             # abs function
    r'|\('              # open paren
    r'|\)'              # close paren
    r'|-?\d+\.?\d*'     # numbers (including negative)
    r'|[a-zA-Z_]\w*'   # identifiers
    r')\s*'
)


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

    Supports Phase 1 grammar:
    - Bare variable: "on_ground" → bool check
    - Comparison: "velocity_y < -10.0" → compare
    - Abs comparison: "abs(velocity_x) > 0.1" → abs + compare
    - Boolean literals: "true", "false"

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

    expression, remaining = _parse_expression(tokens)
    if remaining:
        msg = f'Unexpected tokens after expression: {remaining}'
        raise ValueError(msg)

    return expression


def _parse_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse a full expression from tokens.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    if not tokens:
        msg = 'Unexpected end of expression'
        raise ValueError(msg)

    # Try abs expression: abs( variable ) op number
    if tokens[0] == 'abs':
        return _parse_abs_expression(tokens)

    # Parse left side (variable or number)
    left, remaining = _parse_term(tokens)

    # If no more tokens, it's a bare variable/literal
    if not remaining:
        return left, remaining

    # Check for comparison operator
    if remaining[0] in {'>', '<', '>=', '<=', '==', '!='}:
        operator = remaining[0]
        right, remaining = _parse_term(remaining[1:])
        return ComparisonExpr(left=left, operator=operator, right=right), remaining

    # Just a bare term
    return left, remaining


def _parse_abs_expression(tokens: list[str]) -> tuple[Expression, list[str]]:
    """Parse abs(variable) op number.

    Returns:
        Tuple of (parsed Expression, remaining tokens).

    """
    # Expect: abs ( variable ) op number
    if len(tokens) < 4:
        msg = f'Incomplete abs expression: {tokens}'
        raise ValueError(msg)

    if tokens[1] != '(':
        msg = f"Expected '(' after abs, got '{tokens[1]}'"
        raise ValueError(msg)

    inner, remaining = _parse_term(tokens[2:])

    if not remaining or remaining[0] != ')':
        msg = "Expected ')' to close abs()"
        raise ValueError(msg)

    remaining = remaining[1:]  # consume ')'
    abs_expr = AbsExpr(inner=inner)

    # Check for comparison operator
    if remaining and remaining[0] in {'>', '<', '>=', '<=', '==', '!='}:
        operator = remaining[0]
        right, remaining = _parse_term(remaining[1:])
        return ComparisonExpr(left=abs_expr, operator=operator, right=right), remaining

    return abs_expr, remaining


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

    # Number
    try:
        value = float(token)
        return LiteralExpr(value=value), remaining
    except ValueError:
        pass

    # Variable (identifier)
    if re.match(r'^[a-zA-Z_]\w*$', token):
        return VariableExpr(name=token), remaining

    msg = f"Unexpected token: '{token}'"
    raise ValueError(msg)
