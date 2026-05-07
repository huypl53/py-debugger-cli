"""Simple test script for debugging."""


def greet(name: str) -> str:
    """Return a greeting."""
    message = f"Hello, {name}!"
    return message


def main() -> None:
    """Main entry point."""
    names = ["Alice", "Bob", "Charlie"]
    for name in names:
        greeting = greet(name)
        print(greeting)


if __name__ == "__main__":
    main()
