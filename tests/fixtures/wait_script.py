"""Test script that waits - for debugging the debugger."""
import time

def main():
    x = 1
    y = 2
    z = x + y
    print(f"Result: {z}")
    return z

if __name__ == "__main__":
    result = main()
    print(f"Done: {result}")
