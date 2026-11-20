import re
from fractions import Fraction

_RATIONAL_TEXT = re.compile(r'[+-]?[0-9]+(?:/[0-9]+)?')


def parse_rational(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return Fraction(value)
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str) and _RATIONAL_TEXT.fullmatch(value):
        try:
            return Fraction(value)
        except ZeroDivisionError as exc:
            raise ValueError('rational denominator must be nonzero') from exc
    raise ValueError('expected an integer, Fraction or integer fraction text')


def format_rational(value: object) -> str:
    return str(parse_rational(value))
