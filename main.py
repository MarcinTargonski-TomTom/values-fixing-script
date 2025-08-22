#!/usr/bin/env python3
"""
Skrypt do znajdowania wspólnych wartości w plikach values.yaml z podkatalogów
i przenoszenia ich do głównego pliku values.yaml.

Użycie: python main.py <ścieżka_do_katalogu_nadrzędnego>
"""

import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List, Set
import argparse


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Wczytuje plik YAML i zwraca jego zawartość."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except Exception as e:
        print(f"Błąd podczas wczytywania {file_path}: {e}")
        return {}


def save_yaml_file(file_path: Path, data: Dict[str, Any]):
    """Zapisuje dane do pliku YAML."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, default_flow_style=False, allow_unicode=True, sort_keys=True)
        print(f"Zapisano: {file_path}")
    except Exception as e:
        print(f"Błąd podczas zapisywania {file_path}: {e}")


def find_subdirectory_yaml_files(parent_dir: Path) -> List[Path]:
    """Znajduje wszystkie pliki values.yaml w podkatalogach (rekursywnie), pomijając pliki bezpośrednio w katalogach warstw."""
    yaml_files = []

    def search_recursive(current_dir: Path, depth: int = 0):
        """Rekursywnie przeszukuje katalogi w poszukiwaniu plików values.yaml."""
        # Ograniczenie głębokości dla bezpieczeństwa (maksymalnie 3 poziomy w głąb)
        if depth > 3:
            return

        for item in current_dir.iterdir():
            if item.is_dir():
                values_file = item / "values.yaml"
                if values_file.exists():
                    # Sprawdź czy to nie jest plik values.yaml bezpośrednio w katalogu warstwy (ttomsd, ttomhd)
                    # Jeśli parent tego pliku to katalog warstwy (ttomXX), a grandparent to katalog główny
                    parent_name = item.parent.name
                    grandparent = item.parent.parent

                    # Jeśli to jest podkatalog serwisu (nie bezpośrednio w warstwie), dodaj plik
                    if not (parent_name.startswith('ttom') and grandparent == parent_dir):
                        yaml_files.append(values_file)
                else:
                    # Jeśli w tym katalogu nie ma values.yaml, szukaj głębiej
                    search_recursive(item, depth + 1)

    search_recursive(parent_dir)
    return yaml_files


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '___') -> Dict[str, Any]:
    """Spłaszcza zagnieżdżony słownik do jednopoziomowego."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict[str, Any], sep: str = '___') -> Dict[str, Any]:
    """Odtwarza zagnieżdżoną strukturę słownika z spłaszczonego."""
    result = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # Jeśli napotykamy wartość skalarną w miejscu gdzie powinien być słownik,
                # to znaczy że mamy konflikt ścieżek. W takim przypadku tworzymy nowy słownik.
                current[part] = {}
            current = current[part]

        # Sprawdź czy ostatni element już istnieje i czy nie ma konfliktu
        final_key = parts[-1]
        if final_key in current and isinstance(current[final_key], dict) and not isinstance(value, dict):
            # Jeśli próbujemy nadpisać słownik wartością skalarną, pomiń
            continue
        elif final_key in current and not isinstance(current[final_key], dict) and isinstance(value, dict):
            # Jeśli próbujemy nadpisać wartość skalarną słownikiem, nadpisz
            current[final_key] = value
        else:
            current[final_key] = value
    return result


def remove_keys_from_dict(d: Dict[str, Any], keys_to_remove: Set[str], sep: str = '___') -> Dict[str, Any]:
    """Usuwa klucze ze słownika (obsługuje zagnieżdżone klucze)."""
    flat_dict = flatten_dict(d, sep=sep)

    # Usuń klucze, które są w zestawie do usunięcia
    for key in list(flat_dict.keys()):
        if key in keys_to_remove:
            del flat_dict[key]

    return unflatten_dict(flat_dict, sep=sep)


def find_common_values(yaml_files: List[Path]) -> Dict[str, Any]:
    """Znajduje wspólne wartości we wszystkich plikach YAML."""
    if not yaml_files:
        return {}

    # Wczytaj wszystkie pliki
    all_data = []
    for yaml_file in yaml_files:
        data = load_yaml_file(yaml_file)
        if data:
            flattened = flatten_dict(data)
            all_data.append(flattened)
            print(f"Plik {yaml_file.name}: {len(flattened)} kluczy")
        else:
            print(f"Ostrzeżenie: Plik {yaml_file} jest pusty lub nieprawidłowy")

    if not all_data:
        return {}

    # Znajdź wspólne klucze i wartości
    common_items = {}
    first_data = all_data[0]

    print(f"\nRozpoczynam porównywanie {len(first_data)} kluczy z pierwszego pliku...")
    print(f"Przykładowe klucze z pierwszego pliku:")
    for i, (key, value) in enumerate(first_data.items()):
        if i < 5:  # Pokaż pierwsze 5 kluczy
            print(f"  {key} = {value}")

    # Sprawdź kilka przykładowych kluczy szczegółowo
    sample_keys = list(first_data.keys())[:3]

    for key in sample_keys:
        value = first_data[key]
        print(f"\nSzczegółowa analiza klucza: '{key}' = '{value}'")

        matches = []
        for i, data in enumerate(all_data):
            if key in data:
                data_value = data[key]
                match = (data_value == value)
                matches.append(match)
                print(f"  Plik {i+1}: '{data_value}' -> Zgodny: {match}")
            else:
                matches.append(False)
                print(f"  Plik {i+1}: BRAK KLUCZA")

        all_match = all(matches)
        print(f"  Wszystkie zgodne: {all_match}")

    for key, value in first_data.items():
        # Sprawdź czy ten klucz i wartość występuje we wszystkich plikach
        if all(key in data and data[key] == value for data in all_data[1:]):
            common_items[key] = value

    print(f"\nZnaleziono {len(common_items)} wspólnych kluczy")

    if common_items:
        print("Wspólne klucze:")
        for key, value in list(common_items.items())[:10]:  # Pokaż pierwsze 10
            print(f"  {key} = {value}")

    return unflatten_dict(common_items)


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Łączy dwa słowniki, zachowując strukturę zagnieżdżoną."""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def main():
    parser = argparse.ArgumentParser(description='Przenieś wspólne wartości YAML do pliku nadrzędnego')
    parser.add_argument('parent_directory', help='Ścieżka do katalogu nadrzędnego zawierającego values.yaml')
    parser.add_argument('--dry-run', action='store_true', help='Pokaż co zostanie zmienione bez zapisywania')

    args = parser.parse_args()

    print(f"Rozpoczynam analizę katalogu: {args.parent_directory}")

    parent_dir = Path(args.parent_directory)

    print(f"Sprawdzam katalog: {parent_dir}")

    # Sprawdź czy katalog nadrzędny istnieje
    if not parent_dir.exists() or not parent_dir.is_dir():
        print(f"Błąd: Katalog {parent_dir} nie istnieje lub nie jest katalogiem!")
        sys.exit(1)

    # Znajdź plik values.yaml w katalogu nadrzędnym
    parent_yaml_path = parent_dir / "values.yaml"

    print(f"Szukam głównego pliku: {parent_yaml_path}")

    if not parent_yaml_path.exists():
        print(f"Błąd: Plik values.yaml nie został znaleziony w katalogu {parent_dir}!")
        sys.exit(1)

    print(f"Znaleziono główny plik values.yaml: {parent_yaml_path}")

    # Znajdź wszystkie pliki values.yaml w podkatalogach
    print("Rozpoczynam szukanie plików values.yaml w podkatalogach...")
    subdirectory_yaml_files = find_subdirectory_yaml_files(parent_dir)

    print(f"Znaleziono {len(subdirectory_yaml_files)} plików w podkatalogach")

    if not subdirectory_yaml_files:
        print("Nie znaleziono plików values.yaml w podkatalogach.")
        return

    print(f"Znaleziono {len(subdirectory_yaml_files)} plików values.yaml w podkatalogach:")
    for yaml_file in subdirectory_yaml_files:
        print(f"  - {yaml_file}")

    # Znajdź wspólne wartości
    print("\nSzukanie wspólnych wartości...")
    common_values = find_common_values(subdirectory_yaml_files)

    if not common_values:
        print("Nie znaleziono wspólnych wartości.")
        return

    print(f"\nZnaleziono wspólne wartości:")
    print(yaml.dump(common_values, default_flow_style=False, allow_unicode=True))

    if args.dry_run:
        print("TRYB TESTOWY - żadne pliki nie zostały zmienione.")
        return

    # Wczytaj główny plik values.yaml
    parent_data = load_yaml_file(parent_yaml_path)

    # Dodaj wspólne wartości do głównego pliku
    updated_parent_data = merge_dicts(parent_data, common_values)

    # Zapisz zaktualizowany główny plik
    save_yaml_file(parent_yaml_path, updated_parent_data)

    # Usuń wspólne wartości z plików podrzędnych
    common_keys = set(flatten_dict(common_values).keys())

    for yaml_file in subdirectory_yaml_files:
        data = load_yaml_file(yaml_file)
        updated_data = remove_keys_from_dict(data, common_keys)
        save_yaml_file(yaml_file, updated_data)

    print(f"\nPomyślnie przeniesiono wspólne wartości do {parent_yaml_path}")
    print(f"Zaktualizowano {len(subdirectory_yaml_files)} plików podrzędnych")


if __name__ == "__main__":
    main()
