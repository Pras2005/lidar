class UnitConverter:
    """
    Utility for Phase 4: Unit conversion and formatting.
    Supports m, cm, mm, inch, ft.
    """
    CONVERSIONS = {
        'm': 1.0,
        'cm': 100.0,
        'mm': 1000.0,
        'inch': 39.3701,
        'ft': 3.28084
    }

    @staticmethod
    def convert(value_m: float, to_unit: str) -> float:
        return value_m * UnitConverter.CONVERSIONS.get(to_unit, 1.0)

    @staticmethod
    def format(value_m: float, to_unit: str) -> str:
        val = UnitConverter.convert(value_m, to_unit)
        return f"{val:.2f} {to_unit}"
