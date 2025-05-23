def midpoint(x1, x2):
    """
    Oblicza punkt w połowie drogi między dwoma liczbami na osi liczbowej.

    :param x1: Pierwszy punkt (liczba)
    :param x2: Drugi punkt (liczba)
    :return: Wartość środkowa (midpoint)
    """
    return (x1 + x2) / 2


def main():
    p1 = 377.7
    p2 = 394.7
    mid = midpoint(p1, p2)  # Znajdujemy punkt środkowy
    print(mid)  # Wyświetlamy wynik


if __name__ == "__main__":
    main()
