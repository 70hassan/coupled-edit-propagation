"""
Task 005: Expression Calculator - Operator precedence change

Scenario: A calculator's `tokenize` function was changed to emit a richer token
format with type annotations and position info. The parser and evaluator that
consume tokens still expect the old plain-string format.

Difficulty: Medium
Coupling type: Internal data representation change across processing stages
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "calc/tokenizer.py": '''
import re


class Token:
    """Rich token with type and position information."""
    def __init__(self, kind: str, value: str, position: int):
        self.kind = kind      # "NUMBER", "OP", "LPAREN", "RPAREN"
        self.value = value
        self.position = position

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, pos={self.position})"


def tokenize(expression: str) -> list[Token]:
    """
    MODIFIED: Now returns list of Token objects instead of list of plain strings.
    Previously returned e.g. ["3", "+", "4", "*", "2"].
    Now returns [Token("NUMBER", "3", 0), Token("OP", "+", 1), ...].
    """
    tokens = []
    i = 0
    while i < len(expression):
        if expression[i].isspace():
            i += 1
            continue
        elif expression[i].isdigit() or (expression[i] == '.' and i + 1 < len(expression) and expression[i+1].isdigit()):
            start = i
            while i < len(expression) and (expression[i].isdigit() or expression[i] == '.'):
                i += 1
            tokens.append(Token("NUMBER", expression[start:i], start))
        elif expression[i] in "+-*/^%":
            tokens.append(Token("OP", expression[i], i))
            i += 1
        elif expression[i] == '(':
            tokens.append(Token("LPAREN", "(", i))
            i += 1
        elif expression[i] == ')':
            tokens.append(Token("RPAREN", ")", i))
            i += 1
        else:
            raise ValueError(f"Unexpected character '{expression[i]}' at position {i}")
    return tokens
''',
        "calc/parser.py": '''
from calc.tokenizer import tokenize


def parse_expression(expr_string: str) -> float:
    """
    Parse and evaluate a mathematical expression.
    Supports +, -, *, /, ^ (power), % (modulo), and parentheses.
    """
    tokens = tokenize(expr_string)
    if not tokens:
        return 0.0
    result, pos = _parse_addition(tokens, 0)
    return result


def _parse_addition(tokens: list, pos: int) -> tuple[float, int]:
    """Handle + and - (lowest precedence)."""
    left, pos = _parse_multiplication(tokens, pos)
    while pos < len(tokens) and tokens[pos] in ("+", "-"):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_multiplication(tokens, pos)
        if op == "+":
            left += right
        else:
            left -= right
    return left, pos


def _parse_multiplication(tokens: list, pos: int) -> tuple[float, int]:
    """Handle *, /, % (medium precedence)."""
    left, pos = _parse_power(tokens, pos)
    while pos < len(tokens) and tokens[pos] in ("*", "/", "%"):
        op = tokens[pos]
        pos += 1
        right, pos = _parse_power(tokens, pos)
        if op == "*":
            left *= right
        elif op == "/":
            left /= right
        else:
            left %= right
    return left, pos


def _parse_power(tokens: list, pos: int) -> tuple[float, int]:
    """Handle ^ (highest precedence, right-associative)."""
    base, pos = _parse_atom(tokens, pos)
    if pos < len(tokens) and tokens[pos] == "^":
        pos += 1
        exp, pos = _parse_power(tokens, pos)
        base = base ** exp
    return base, pos


def _parse_atom(tokens: list, pos: int) -> tuple[float, int]:
    """Handle numbers and parenthesized sub-expressions."""
    if pos >= len(tokens):
        raise ValueError("Unexpected end of expression")

    tok = tokens[pos]
    if tok == "(":
        pos += 1
        value, pos = _parse_addition(tokens, pos)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise ValueError("Missing closing parenthesis")
        pos += 1
        return value, pos
    elif tok in ("+", "-"):
        sign = 1 if tok == "+" else -1
        pos += 1
        value, pos = _parse_atom(tokens, pos)
        return sign * value, pos
    else:
        try:
            return float(tok), pos + 1
        except ValueError:
            raise ValueError(f"Expected number, got '{tok}'")
''',
        "calc/formatter.py": '''
from calc.tokenizer import tokenize


def highlight_operators(expression: str) -> str:
    """Return expression with operators wrapped in brackets for display."""
    tokens = tokenize(expression)
    parts = []
    for tok in tokens:
        if tok in "+-*/^%":
            parts.append(f"[{tok}]")
        else:
            parts.append(tok)
    return " ".join(parts)


def count_operations(expression: str) -> dict[str, int]:
    """Count each type of operator in the expression."""
    tokens = tokenize(expression)
    counts = {}
    for tok in tokens:
        if tok in "+-*/^%":
            counts[tok] = counts.get(tok, 0) + 1
    return counts


def get_token_count(expression: str) -> int:
    """Return total number of tokens in expression."""
    return len(tokenize(expression))
''',
    }

    modified_function = "tokenize"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from calc.tokenizer import tokenize, Token


def test_tokenize_returns_token_objects():
    result = tokenize("3 + 4")
    assert len(result) == 3
    assert isinstance(result[0], Token)
    assert result[0].kind == "NUMBER"
    assert result[0].value == "3"
    assert result[1].kind == "OP"
    assert result[1].value == "+"


def test_tokenize_complex():
    result = tokenize("(10.5 + 2) * 3")
    assert result[0].kind == "LPAREN"
    assert result[1].value == "10.5"
    assert result[3].value == "2"
    assert result[4].kind == "RPAREN"
'''

    hidden_tests = '''
import sys
sys.path.insert(0, ".")
from calc.parser import parse_expression
from calc.formatter import highlight_operators, count_operations, get_token_count


def test_parse_simple_addition():
    assert parse_expression("3 + 4") == 7.0


def test_parse_precedence():
    assert parse_expression("3 + 4 * 2") == 11.0


def test_parse_parentheses():
    assert parse_expression("(3 + 4) * 2") == 14.0


def test_parse_power():
    assert parse_expression("2 ^ 3") == 8.0


def test_parse_complex():
    result = parse_expression("(2 + 3) * 4 - 6 / 2")
    assert abs(result - 17.0) < 0.001


def test_parse_modulo():
    assert parse_expression("10 % 3") == 1.0


def test_parse_nested_parens():
    assert parse_expression("((2 + 3) * (4 - 1))") == 15.0


def test_highlight_operators():
    result = highlight_operators("3 + 4 * 2")
    assert "[+]" in result
    assert "[*]" in result
    assert "3" in result


def test_count_operations():
    result = count_operations("3 + 4 * 2 + 1")
    assert result["+"] == 2
    assert result["*"] == 1


def test_token_count():
    assert get_token_count("3 + 4") == 3
    assert get_token_count("(1 + 2) * 3") == 7
'''

    ground_truth_repairs = {
        "calc/parser.py": "All comparisons like tokens[pos] == '+' must use tokens[pos].value == '+', and float(tok) must be float(tok.value), and paren checks must use .value",
        "calc/formatter.py": "Comparisons like tok in '+-*/^%' must use tok.value, and parts.append(tok) must use tok.value",
    }

    return TaskInstance(
        task_id="task_005_calculator",
        instruction=(
            "The function `tokenize` in calc/tokenizer.py was intentionally changed. "
            "It now returns a list of Token objects (with .kind, .value, .position attributes) "
            "instead of a list of plain strings. This change is correct and must NOT be reverted. "
            "Fix all downstream code in calc/parser.py and calc/formatter.py that still treats "
            "tokens as plain strings (comparisons, float conversions, string operations)."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="medium",
        revert_indicators=[
            "tokens.append(expression[start:i])",
            "tokens.append(expression[i])",
            "-> list[str]:",
            "-> List[str]:",
        ],
        modified_is_async=False,
    )
