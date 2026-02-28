from civil_engineering.scoring.global_exporter import export_global_ranking
from pathlib import Path


def test_global_ranking_export():
    json_path, csv_path = export_global_ranking()

    assert Path(json_path).exists(), "Global ranking JSON not created"
    assert Path(csv_path).exists(), "Global ranking CSV not created"

    print("Global ranking export validated.")


if __name__ == "__main__":
    test_global_ranking_export()
