"""Test script for exception debugging."""


class CustomError(Exception):
    """Custom error for testing."""
    pass


def risky_operation(value: int) -> int:
    """Operation that may raise an exception."""
    if value < 0:
        raise ValueError(f"Value must be non-negative: {value}")
    if value == 0:
        raise CustomError("Cannot process zero")
    return 100 // value


def main() -> None:
    """Main entry point."""
    values = [10, 5, 2, 0, -1]

    for value in values:
        try:
            result = risky_operation(value)
            print(f"risky_operation({value}) = {result}")
        except ValueError as e:
            print(f"ValueError: {e}")
        except CustomError as e:
            print(f"CustomError: {e}")


if __name__ == "__main__":
    main()
