# Sprawdzarka turniejowa

## Uruchomienie
`ai_dueller.py [--local_ai_su] [--verbose 0|1|2] [--num_games 10] GRA FOLDER0 FOLDER1`
Uruchomi `num_games` rozgrywek między graczem w folderze `FOLDER0` a graczem w folderze `FOLDER1`. Opcja `verbose` wyświetli przebieg gier. Użycie opcji `--local_ai_su` umożliwi uruchamianie na własnych komputerach (wykorzystany będzie skrypt `ai_su.sh`).

W katalogu `reversi_random` zaimplementowano przykładowego gracza w reversi.

Protokół komunikacji ze sprawdzaczką:
1. Program czyta ze standardowego wejścia i pisze na standardowe wyjście.
2. Sprawdzaczka może przysłać następujące komunikaty:
- `UGO %f %f` -- gracz otrzymujący ten komunikat program ma rozpocząć grę. Parametry podają czas na wykonanie ruchu i pozostały czas na grę.
- `HEDID %f %f ...` -- gracz otrzymujący ten komunikat ma zareagować na ruch przeciwnika. Pierwsze dwie liczby oznaczają czas na ruch i pozostały czas na grę, dalsza część linii zależy od gry.
- `ONEMORE` -- gracz ma się zresetować, zaczyna się nowa gra
- `BYE` -- gracz ma się wyłączyć
3. Gracze wysyłają sprawdzaczce następujące komunikaty:
- `RDY` -- określenie gotowości, wysyłane po starcie programu i po prośbie o reset.
- `IDO ...` -- odpowiedź na `UGO` i `HEDID`: ruch gracza, w formacie zależnym od gry.
4. Uwagi:
- Gracz wie, że zaczyna rozgrywkę jeśli po starcie dostaje komunikat `UGO`. Jeśli po starcie dostaje komunikat `HEDID...` oznacza to że jest drugim graczem.
- Czas inicjalizacji (i czas po resecie) jest limitowany z limitem 5s.
- Limity czasów dla ruchów są podawane przy każdym ruchu - liczy się czas mierzony przez sprawdzaczkę (a więc z narzutem na komunikację).
- Podczas turnieju gracze będą mieli *na wyłączność* jeden rdzeń procesora (2 hyper-thready) i 6GB RAM. Limity zostaną zaimplementowane w sprawdzaczce w niedalekiej przyszłości (przysłanie działającego PR do `ai_su.go` używającego cgroups do ustalania limitów jest warte do 5 puntów pracownianych).
- Gracz może wypisywać komunikaty do debugowania na `stderr`, kanał ten jest ignorowany przez sprawdzaczkę.

Przykładowa komunikacja:
```
P0 -> S: `RDY`
P1 -> S: `RDY`
S -> P0: `UGO 5.000000 60.000000`
P0 -> S: `IDO 3 2`
S -> P1: `HEDID 5.000000 60.000000 3 2`
P1 -> S: `IDO 2 2`
S -> P0: `HEDID 5.000000 59.970938 2 2`
P0 -> S: `IDO 5 4`
S -> P1: `HEDID 5.000000 59.962543 5 4`
P1 -> S: `IDO 4 2`
S -> P0: `HEDID 5.000000 59.938420 4 2`
P0 -> S: `IDO 2 3`
...
```

## Zgłaszanie programów
Programy do oceny należy umieścić w katalogu `/pio/scratch/2/ai_solutions/[reversi|jungle]_iXXXXXX/` gdzie XXXXXX jest numerem indeksu. Folder ma mieć prawa odczytu tylko dla jego właściciela `700`. W folderze musi znajdować się przynajmniej plik `run.sh` który zostanie uruchomiony bashem. Plik ten ma ustawić środowisko dla gracza i uruchomić program gracza.

Sprawdzanie poprawności zgłoszeń można wykonywać na komputerach lab110-01..lab110-10 i lab137-01..lab137-18 uruchamiając (w katalogu `/pio/scratch/2/ai_solutions/`) komendę `./ai_duller.py reversi reversi_random reversi_iXXX`. Gracze mogą być zaimplementowani w dowolnej technologii, pod warunkiem że będą działać na komputerach lab110-XX.

Programy zachowujące się niesportowo (np. próbujące zawiesić/uszkodzić przeciwnika) będą usuwane z turnieju.

## Protokoły dla poszczególnych gier

### Reversi
Ruch zapisujemy jako parę liczb całkowitych przedzielonych spacją. Ruch pasujący jest parą `-1 -1`, dołożenia kamienia to dwie liczby z zakresu 0-7. Początkowe ustawienie planszy to
```
........
........
........
...#o...
...o#...
........
........
........
```
Grę rozpoczyna gracz `o`. 

### Dżungla
Ruch zapisujemy jako czwórkę liczb całkowitych przedzielonych spacją: `XS YS XD YD` gdzie `XS, YS` to współrzędne pola startowego, a `XD, YD` to współrzędne pola docelowego (współrzędne `X` zawierają się w `[0, 6]`, a `Y` w `[0, 8]`). Ruch pasujący to `-1 -1 -1 -1`. Początkowe ustawienie planszy to:
```
L.....T
.D...C.
R.J.W.E
.......
.......
.......
e.w.j.r
.c...d.
t.....l
```
Partię rozpoczyna zawsze gracz grający małymi literami.
