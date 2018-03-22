# Sprawdzarka zadań
Dla kursu Sztuczna Inteligencja prowadzonego w semestrze letnim 2017/2018 na
Uniwersytecie Wrocawskim.

Przykłady użycia:

1. Uruchomienie wszystkich testów dla danego zadania:
  `python validator.py zad1 python rozwiazanie.py`

2. Uruchomienie wybranych testów
  `python validator.py --cases 1,3-5 zad1 a.out`

3. Urochomienie na innych testach
  `python validator.py --testset large_tests.yaml zad1 python rozwiazanie.py`

4. Wypisanie przykładowego wejścia/wyjścia:
  `python validator.py --show_example zad1`

5. Wypisanie informacji o rozwiązaniu:
  `python validator.py --verbose zad1 python rozwiazanie.py`

6. Wymuszenie użycia STDIN/STDOUT do komunikacji:
  `python validator.py --stdio zad1 python rozwiazanie.py`

7. Ustawienie mnożnika dla limitów czasowych:
  `python validator.py --timeout-multiplier 2.5 zad1 python rozwiazanie.py`
