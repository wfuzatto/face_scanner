"""Evaluate labeled score pairs; never selects or writes production thresholds."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_scores(path: Path) -> list[tuple[float, bool]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"score", "label"}.issubset(reader.fieldnames):
            raise ValueError("CSV deve possuir as colunas score,label")
        rows = []
        for row in reader:
            label = str(row["label"]).strip().lower()
            if label not in {"match", "mismatch", "1", "0", "true", "false"}:
                raise ValueError("label deve ser match/mismatch ou booleano")
            rows.append((float(row["score"]), label in {"match", "1", "true"}))
    return rows


def metrics(rows: list[tuple[float, bool]], threshold: float) -> dict[str, float | int]:
    tp = tn = fp = fn = 0
    for score, actual_match in rows:
        predicted_match = score >= threshold
        if predicted_match and actual_match: tp += 1
        elif predicted_match: fp += 1
        elif actual_match: fn += 1
        else: tn += 1
    return {"threshold": threshold, "TP": tp, "TN": tn, "FP": fp, "FN": fn, "FAR": fp / max(fp + tn, 1), "FRR": fn / max(fn + tp, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia scores/labels em thresholds informados pelo operador.")
    parser.add_argument("scores_csv", type=Path, help="CSV com score,label")
    parser.add_argument("--threshold", type=float, action="append", required=True, help="Pode ser repetido; não há escolha automática.")
    args = parser.parse_args()
    rows = read_scores(args.scores_csv)
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=["threshold", "TP", "TN", "FP", "FN", "FAR", "FRR"])
    writer.writeheader()
    for threshold in args.threshold:
        writer.writerow(metrics(rows, threshold))


if __name__ == "__main__":
    main()
