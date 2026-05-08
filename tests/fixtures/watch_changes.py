"""Test script for watch diff feature."""


def main():
    x = 0
    y = 0
    z = "constant"

    for i in range(5):
        x += 1        # x changes each iteration
        if i == 3:
            y = 100   # y changes only once at i=3
        # z never changes
        print(f"i={i}, x={x}, y={y}, z={z}")


if __name__ == "__main__":
    main()
