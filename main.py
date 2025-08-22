#!/usr/bin/env python3

import sys
from ruamel.yaml import YAML
from pathlib import Path
from typing import Dict, Any, List, Set
import argparse

yaml = YAML()
yaml.preserve_quotes = True
yaml.map_indent = 2
yaml.sequence_indent = 4


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.load(file) or {}
    except Exception as e:
        print(f"Błąd podczas wczytywania {file_path}: {e}")
        return {}


def save_yaml_file(file_path: Path, data: Dict[str, Any]):
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file)
        print(f"Zapisano: {file_path}")
    except Exception as e:
        print(f"Błąd podczas zapisywania {file_path}: {e}")


def find_subdirectory_yaml_files_by_layer(parent_dir: Path) -> Dict[str, List[Path]]:
    layers = {}
    for layer_dir in parent_dir.iterdir():
        if layer_dir.is_dir() and layer_dir.name.startswith('ttom'):
            layer_name = layer_dir.name
            yaml_files = []

            # Przeszukaj katalogi serwisów w danej warstwie
            for service_dir in layer_dir.iterdir():
                if service_dir.is_dir():
                    values_file = service_dir / "values.yaml"
                    if values_file.exists():
                        yaml_files.append(values_file)

            if yaml_files:
                layers[layer_name] = yaml_files

    return layers


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '___') -> Dict[str, Any]:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict[str, Any], sep: str = '___') -> Dict[str, Any]:
    result = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        final_key = parts[-1]
        if final_key in current and isinstance(current[final_key], dict) and not isinstance(value, dict):
            continue
        elif final_key in current and not isinstance(current[final_key], dict) and isinstance(value, dict):
            current[final_key] = value
        else:
            current[final_key] = value
    return result


def remove_keys_from_dict(d: Dict[str, Any], keys_to_remove: Set[str], sep: str = '___') -> Dict[str, Any]:
    flat_dict = flatten_dict(d, sep=sep)

    for key in list(flat_dict.keys()):
        if key in keys_to_remove:
            del flat_dict[key]

    return unflatten_dict(flat_dict, sep=sep)


def remove_keys_from_yaml(data: Dict[str, Any], keys_to_remove: Set[str], sep: str = '___') -> Dict[str, Any]:
    def remove_from_nested_dict(d: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        result = type(d)()

        for key, value in d.items():
            current_path = f"{prefix}{sep}{key}" if prefix else key

            if current_path in keys_to_remove:
                continue
            if isinstance(value, dict):
                nested_result = remove_from_nested_dict(value, current_path)
                if nested_result:
                    result[key] = nested_result
            else:
                result[key] = value

        return result

    return remove_from_nested_dict(data)


def find_common_values(yaml_files: List[Path]) -> Dict[str, Any]:
    if not yaml_files:
        return {}

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

    common_items = {}
    first_data = all_data[0]

    print(f"\nRozpoczynam porównywanie {len(first_data)} kluczy z pierwszego pliku...")
    print(f"Przykładowe klucze z pierwszego pliku:")
    for i, (key, value) in enumerate(first_data.items()):
        if i < 5:  # Pokaż pierwsze 5 kluczy
            print(f"  {key} = {value}")

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
        if all(key in data and data[key] == value for data in all_data[1:]):
            common_items[key] = value

    print(f"\nZnaleziono {len(common_items)} wspólnych kluczy")

    if common_items:
        print("Wspólne klucze:")
        for key, value in list(common_items.items())[:10]:  # Pokaż pierwsze 10
            print(f"  {key} = {value}")

    return unflatten_dict(common_items)


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
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

    if not parent_dir.exists() or not parent_dir.is_dir():
        print(f"Błąd: Katalog {parent_dir} nie istnieje lub nie jest katalogiem!")
        sys.exit(1)

    print("Rozpoczynam szukanie plików values.yaml w warstwach...")
    layers_yaml_files = find_subdirectory_yaml_files_by_layer(parent_dir)

    if not layers_yaml_files:
        print("Nie znaleziono katalogów warstw (ttom*) z plikami values.yaml.")
        return

    print(f"Znaleziono {len(layers_yaml_files)} warstw:")
    for layer_name, yaml_files in layers_yaml_files.items():
        print(f"  Warstwa {layer_name}: {len(yaml_files)} plików")
        for yaml_file in yaml_files:
            print(f"    - {yaml_file.name}")

    for layer_name, yaml_files in layers_yaml_files.items():
        print(f"\n{'='*60}")
        print(f"PRZETWARZAM WARSTWĘ: {layer_name}")
        print(f"{'='*60}")

        layer_dir = parent_dir / layer_name
        layer_yaml_path = layer_dir / "values.yaml"

        print(f"Katalog warstwy: {layer_dir}")
        print(f"Plik values.yaml warstwy: {layer_yaml_path}")

        if not layer_yaml_path.exists():
            print(f"Ostrzeżenie: Plik {layer_yaml_path} nie istnieje - zostanie utworzony")
            layer_data = {}
        else:
            layer_data = load_yaml_file(layer_yaml_path)
            print(f"Wczytano istniejący plik warstwy z {len(flatten_dict(layer_data))} kluczami")

        print(f"\nSzukanie wspólnych wartości dla warstwy {layer_name}...")
        common_values = find_common_values(yaml_files)

        if not common_values:
            print(f"Nie znaleziono wspólnych wartości dla warstwy {layer_name}.")
            continue

        print(f"\nZnaleziono wspólne wartości dla warstwy {layer_name}:")
        from io import StringIO
        output = StringIO()
        yaml.dump(common_values, output)
        print(output.getvalue())

        if args.dry_run:
            print(f"TRYB TESTOWY - plik warstwy {layer_name} nie został zmieniony.")
        else:
            updated_layer_data = merge_dicts(layer_data, common_values)

            save_yaml_file(layer_yaml_path, updated_layer_data)

            common_keys = set(flatten_dict(common_values).keys())

            print(f"\nUsuwam wspólne wartości z {len(yaml_files)} plików serwisów w warstwie {layer_name}...")
            for yaml_file in yaml_files:
                data = load_yaml_file(yaml_file)
                updated_data = remove_keys_from_yaml(data, common_keys)
                save_yaml_file(yaml_file, updated_data)

            print(f"Pomyślnie przeniesiono wspólne wartości do {layer_yaml_path}")

    if args.dry_run:
        print(f"\n{'='*60}")
        print("TRYB TESTOWY - żadne pliki nie zostały zmienione.")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("ZAKOŃCZONO PRZETWARZANIE WSZYSTKICH WARSTW")
        print(f"{'='*60}")
        total_layers = len(layers_yaml_files)
        total_files = sum(len(files) for files in layers_yaml_files.values())
        print(f"Przetworzono {total_layers} warstw z łącznie {total_files} plikami serwisów")


if __name__ == "__main__":
    main()
