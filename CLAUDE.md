# RW-ODOO-Optima

Aplikacja desktopowa w Python + PyQt6 do porównywania dokumentów rozchodu wewnętrznego (RW) eksportowanych z dwóch systemów: ODOO i Comarch Optima.

## Cel programu

Porównanie artykułów i ilości między dokumentami z systemu ODOO (format XML bez namespace) oraz Comarch Optima (format XML z namespace `http://www.cdn.com.pl/optima/dokument`).

## Struktura projektu

```
main.py        — główny kod aplikacji
build.bat      — skrypt kompilacji do .exe (PyInstaller)
test.xml       — przykładowy plik ODOO
test2.XML      — przykładowy plik Comarch Optima
.venv/         — środowisko wirtualne Python
```

## Uruchomienie

```bash
.venv\Scripts\python.exe main.py
```

## Kompilacja do EXE

```bash
build.bat
# lub
.venv\Scripts\pyinstaller.exe --onefile --windowed --name "RW-ODOO-Optima" main.py
```

Wynikowy plik `.exe` trafia do folderu `dist\`.

## Architektura kodu (`main.py`)

### `DocumentPanel(QWidget)`
Uniwersalny panel do wczytywania i wyświetlania pliku XML.

Parametry konstruktora:
- `title` — nazwa wyświetlana w nagłówku panelu
- `namespace` — namespace XML (`""` dla ODOO, `NS_OPTIMA` dla Optimy)
- `multi_file` — jeśli `True`, umożliwia wczytanie wielu plików naraz z akumulacją ilości

Kluczowe atrybuty:
- `aggregated` — słownik `{kod: {"nazwa": str, "ilosc": float}}` po agregacji
- `doc_date` — data dokumentu (używana w porównaniu)
- `_loaded_files` — lista ścieżek wczytanych plików

Funkcje specyficzne dla trybu `multi_file=True` (panel ODOO):
- Przycisk **"Wczytaj pliki..."** — otwiera dialog multi-select
- Przycisk **"Wyczyść"** — resetuje wszystkie dane
- Przycisk **"Zmień datę"** — otwiera dialog kalendarza i zapisuje nową datę do plików XML na dysku (pola `DATA_DOKUMENTU`, `DATA_WYSTAWIENIA`, `DATA_OPERACJI`)

### `ComparePanel(QWidget)`
Panel porównania — pobiera dane z obu `DocumentPanel` i zestawia je.

Kolumny tabeli: Kod, Nazwa, Ilość ODOO, Ilość Optima, Różnica, Status

Kolory wierszy:
- zielony — ilości zgodne
- czerwony — obie strony mają artykuł, ale ilości różne
- żółty — artykuł tylko w jednym pliku (Tylko ODOO / Tylko Optima)

### `MainWindow(QMainWindow)`
Główne okno z pionowym splitterem:
- Górna połowa: poziomy splitter z panelem ODOO (lewy) i Optima (prawy)
- Dolna połowa: panel porównania

## Format plików XML

### ODOO (`test.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<ROOT>
  <DOKUMENT>
    <NAGLOWEK>
      <NUMER_PELNY>...</NUMER_PELNY>
      <DATA_DOKUMENTU>2026-01-31</DATA_DOKUMENTU>
      ...
    </NAGLOWEK>
    <POZYCJE>
      <POZYCJA>
        <TOWAR><KOD>17046</KOD><NAZWA>...</NAZWA></TOWAR>
        <ILOSC>123.41</ILOSC>
      </POZYCJA>
    </POZYCJE>
  </DOKUMENT>
</ROOT>
```

### Comarch Optima (`test2.XML`)
Identyczna struktura, ale z namespace na każdym tagu:
```xml
<ROOT xmlns="http://www.cdn.com.pl/optima/dokument">
```

## Ważne szczegóły implementacyjne

- Kody artykułów są normalizowane do **wielkich liter** (`.upper()`) przy wczytywaniu — porównanie jest case-insensitive
- Panel ODOO obsługuje **wiele plików** — ilości artykułów o tym samym kodzie sumują się
- Zmiana daty w panelu ODOO **nadpisuje pliki XML na dysku**
- Dependencje: `PyQt6`, `pyinstaller` (w `.venv`)
