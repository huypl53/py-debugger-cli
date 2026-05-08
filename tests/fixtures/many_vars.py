"""Test script for --limit flag with many variables."""


def main():
    a = 1
    b = 2
    c = None
    d = [1, 2, 3]
    e = "hello"
    f = None
    g = {"key": "value"}
    h = 100
    i = None
    j = 42
    # 10 variables total: 3 None, 7 non-None

    # Now change some
    a = 999  # changed
    h = 200  # changed

    print(f"Done: a={a}, h={h}")


if __name__ == "__main__":
    main()
