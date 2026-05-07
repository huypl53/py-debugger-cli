"""Test script with loop for debugging."""


def process_items(items: list[int]) -> int:
    """Process a list of items and return sum."""
    total = 0
    for i, item in enumerate(items):
        total += item
        if total > 100:
            break
    return total


def main() -> None:
    """Main entry point."""
    items = [10, 20, 30, 40, 50]
    result = process_items(items)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
