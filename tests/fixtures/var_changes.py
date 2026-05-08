"""Test script for --changed flag."""


def main():
    x = 1      # line 5
    y = 2      # line 6
    x = 10     # line 7 - x changes
    z = 3      # line 8 - z is new
    y = y      # line 9 - y unchanged (same value reassigned)
    x = x + 1  # line 10 - x changes again
    print(f"x={x}, y={y}, z={z}")


if __name__ == "__main__":
    main()
