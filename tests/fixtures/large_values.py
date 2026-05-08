"""Test script for auto-truncate feature."""


def main():
    # Small values (should not truncate)
    small_list = [1, 2, 3]
    small_dict = {"a": 1, "b": 2}
    small_str = "hello"

    # Large values (should truncate)
    large_list = list(range(100))
    large_dict = {f"key_{i}": i for i in range(50)}
    large_str = "x" * 500
    large_set = set(range(100))

    # Nested large values
    nested_large = {
        "name": "test",
        "data": list(range(100)),
        "metadata": {f"m_{i}": i for i in range(30)}
    }

    # Edge cases
    exactly_20 = list(range(20))  # at threshold, should NOT truncate
    exactly_21 = list(range(21))  # over threshold, should truncate

    print("Done")


if __name__ == "__main__":
    main()
