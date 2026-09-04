"""Temperature conversion.

Known bug: celsius_to_fahrenheit() uses the wrong multiplier.
"""


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit: F = C * 9/5 + 32."""
    # BUG: should multiply by 9/5, not 9/10.
    return celsius * 9 / 10 + 32
