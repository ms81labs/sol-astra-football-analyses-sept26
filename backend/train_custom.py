from __future__ import annotations

import argparse
import csv
from pathlib import Path

from ultralytics import YOLO


DEFAULT_BASE_MODEL = "yolov10n.pt"
DEFAULT_AUGMENTATION_POLICY = {
    "degrees": 0.0,
    "translate": 0.0,
    "scale": 0.0,
    "shear": 0.0,
    "perspective": 0.0,
    "flipud": 0.0,
    "fliplr": 0.0,
    "mosaic": 0.0,
    "mixup": 0.0,
    "copy_paste": 0.0,
}


def _best_checkpoint(results_csv_path: Path) -> tuple[int | None, float | None]:
    if not results_csv_path.is_file():
        return None, None
    with results_csv_path.open(newline="", encoding="utf-8") as handle:
        rows = [{str(key).strip(): value for key, value in row.items()} for row in csv.DictReader(handle)]
    if not rows:
        return None, None

    def number(row: dict[str, str | None], key: str) -> float:
        try:
            return float(row.get(key) or 0)
        except ValueError:
            return 0.0

    def fitness(row: dict[str, str | None]) -> float:
        return number(row, "fitness") if row.get("fitness") else (
            0.1 * number(row, "metrics/mAP50(B)") + 0.9 * number(row, "metrics/mAP50-95(B)")
        )

    best = max(rows, key=fitness)
    return int(number(best, "epoch")), fitness(best)


def fine_tune(
    data_yaml: str = "review/dataset.yaml",
    model_path: str = DEFAULT_BASE_MODEL,
    epochs: int = 50,
    *,
    imgsz: int = 640,
    batch: int = 16,
    device: str = "cpu",
    project: str = "guerilla_models",
    name: str = "custom_pitch_model",
    patience: int = 10,
    workers: int = 0,
    seed: int = 42,
    augmentation_policy: dict[str, float] | None = None,
    exist_ok: bool = True,
    verbose: bool = False,
) -> dict[str, object]:
    data_path = Path(data_yaml)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset {data_yaml} not found.")

    model = YOLO(model_path)

    train_kwargs = {
        "data": str(data_path),
        "epochs": int(epochs),
        "imgsz": int(imgsz),
        "batch": int(batch),
        "device": str(device),
        "project": str(project),
        "name": str(name),
        "patience": int(patience),
        "workers": int(workers),
        "seed": int(seed),
        "exist_ok": bool(exist_ok),
        "verbose": bool(verbose),
        "plots": False,
        "save": True,
        "val": True,
    }
    train_kwargs.update(DEFAULT_AUGMENTATION_POLICY)
    if isinstance(augmentation_policy, dict):
        train_kwargs.update(augmentation_policy)

    results = model.train(**train_kwargs)
    save_dir = Path(getattr(results, "save_dir", Path(project) / name))
    weights_dir = save_dir / "weights"
    best_weights_path = weights_dir / "best.pt"
    last_weights_path = weights_dir / "last.pt"
    results_csv_path = save_dir / "results.csv"
    results_dict = getattr(results, "results_dict", {})
    metrics = dict(results_dict) if isinstance(results_dict, dict) else {}
    best_epoch, best_fitness = _best_checkpoint(results_csv_path)

    return {
        "saveDir": str(save_dir),
        "bestWeightsPath": str(best_weights_path),
        "lastWeightsPath": str(last_weights_path),
        "resultsCsvPath": str(results_csv_path),
        "metrics": metrics,
        "bestEpoch": best_epoch,
        "bestFitness": best_fitness,
        "epochs": int(epochs),
        "imgsz": int(imgsz),
        "batch": int(batch),
        "device": str(device),
        "modelPath": str(model_path),
        "trainKwargs": train_kwargs,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guerilla Analytics - Fine Tune YOLO")
    parser.add_argument("--data", type=str, default="review/dataset.yaml", help="Path to YOLO dataset YAML")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--model", type=str, default=DEFAULT_BASE_MODEL, help="Base model to start from")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--batch", type=int, default=16, help="Training batch size")
    parser.add_argument("--device", type=str, default="cpu", help="Training device")
    parser.add_argument("--project", type=str, default="guerilla_models", help="Ultralytics project output root")
    parser.add_argument("--name", type=str, default="custom_pitch_model", help="Ultralytics run name")
    parser.add_argument("--patience", type=int, default=10, help="Early stopping patience")
    parser.add_argument("--workers", type=int, default=0, help="Data loader workers")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    result = fine_tune(
        data_yaml=args.data,
        model_path=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
        workers=args.workers,
    )
    print("========================================")
    print(" Guerilla Analytics - Active Learning ")
    print("========================================")
    print(f"Training complete. Best weights: {result['bestWeightsPath']}")
    print(f"Last weights: {result['lastWeightsPath']}")
    print(f"Results CSV: {result['resultsCsvPath']}")


if __name__ == "__main__":
    main()
