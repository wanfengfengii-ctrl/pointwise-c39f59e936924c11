from analysis.polynomial import Polynomial, poly_trim


def roots_strictly_inside_unit_disk(coefficients: Polynomial) -> bool:
    """Apply the real-coefficient Schur reduction in exact arithmetic."""
    polynomial = poly_trim(coefficients)
    if not polynomial:
        raise ValueError('the zero polynomial has no strict root classification')
    while len(polynomial) > 1:
        constant, leading = polynomial[0], polynomial[-1]
        if abs(constant) >= abs(leading):
            return False
        # Subtract the reversed polynomial at a scale that cancels the constant.
        # Removing the resulting root at zero reduces the degree by one.
        polynomial = poly_trim(
            leading * polynomial[index] - constant * polynomial[-index - 1]
            for index in range(1, len(polynomial))
        )
    return True
