def fibonacci_level_downtrend(max_value, min_value, level):
    """Oblicza poziom Fibonacciego dla trendu spadkowego."""
    fib_level = max_value - level * (max_value - min_value)
    return fib_level


def calculate_fibonacci():
    """Funkcja do obliczania poziomów Fibonacciego dla trendu spadkowego."""
    print("\n--- Obliczanie Poziomu Fibonacciego dla Trendu Spadkowego ---")
    min_value = float(input("Podaj wartość minimalną: "))
    max_value = float(input("Podaj wartość maksymalną: "))

    # Poziom 61,8% Fibonacciego
    level = 0.618
    fib_value = fibonacci_level_downtrend(max_value, min_value, level)

    print(
        f"Poziom Fibonacciego 61,8% dla wartości maksymalnej {max_value} i minimalnej {min_value} wynosi {fib_value:.2f}"
    )


def main():
    calculate_fibonacci()


if __name__ == "__main__":
    main()
