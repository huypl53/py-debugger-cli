"""Test script for state change tracking."""


def modify_data(data: dict) -> None:
    """Modify data in place."""
    data["count"] += 1
    data["items"].append(data["count"])


def main() -> None:
    """Main entry point."""
    data = {"count": 0, "items": []}

    for i in range(5):
        modify_data(data)
        total = sum(data["items"])
        print(f"Iteration {i}: count={data['count']}, total={total}")


if __name__ == "__main__":
    main()
