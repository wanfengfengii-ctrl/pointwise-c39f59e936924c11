from collections.abc import Iterable
from fractions import Fraction
from itertools import zip_longest

Polynomial = tuple[Fraction, ...]


def poly_trim(coefficients: Iterable[Fraction | int]) -> Polynomial:
    """Use ascending powers and the empty tuple for the zero polynomial."""
    result = [Fraction(coefficient) for coefficient in coefficients]
    while result and not result[-1]:
        result.pop()
    return tuple(result)


def poly_add(left: Polynomial, right: Polynomial) -> Polynomial:
    return poly_trim(a + b for a, b in zip_longest(left, right, fillvalue=Fraction(0)))


def poly_multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    if not left or not right:
        return ()
    result = [Fraction(0)] * (len(left) + len(right) - 1)
    for left_degree, left_coefficient in enumerate(left):
        for right_degree, right_coefficient in enumerate(right):
            result[left_degree + right_degree] += left_coefficient * right_coefficient
    return poly_trim(result)


def poly_divmod(dividend: Polynomial, divisor: Polynomial) -> tuple[Polynomial, Polynomial]:
    remainder = list(poly_trim(dividend))
    divisor = poly_trim(divisor)
    if not divisor:
        raise ZeroDivisionError('polynomial division by zero')
    quotient = [Fraction(0)] * max(0, len(remainder) - len(divisor) + 1)
    while len(remainder) >= len(divisor):
        shift = len(remainder) - len(divisor)
        coefficient = remainder[-1] / divisor[-1]
        quotient[shift] = coefficient
        for index, value in enumerate(divisor):
            remainder[shift + index] -= coefficient * value
        while remainder and not remainder[-1]:
            remainder.pop()
    return poly_trim(quotient), tuple(remainder)


def poly_gcd(left: Polynomial, right: Polynomial) -> Polynomial:
    left, right = poly_trim(left), poly_trim(right)
    while right:
        left, right = right, poly_divmod(left, right)[1]
    return tuple(value / left[-1] for value in left) if left else ()
