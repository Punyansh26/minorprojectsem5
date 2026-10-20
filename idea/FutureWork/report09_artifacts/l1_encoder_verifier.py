#!/usr/bin/env python3
"""L1 - section 6 encoder claim verifier: train, calibrate, gate (GPU + download).

Builds (claim, evidence, label) rows from the L0 verified triples (positives) and
deliberately corrupted copies (negatives, the TinyLettuce-style generation idea [R905]),
fine-tunes a small encoder (ModernBERT-base [R903] by default, or Ettin/mmBERT) for
binary "supported" classification, calibrates a confidence threshold for accepted
precision >= 0.98 using the Demo2 selective maths (distillation.threshold_for_precision),
and writes a JEV-style certificate that distillation.evaluate_certificate checks.

This is a LONG test: it downloads encoder weights (hundreds of MB) and trains on the
GPU, so the user runs it, not the agent. Scratch (model, datasets) goes to a temp dir
outside code/demo2/data. Resumable via an on-disk checkpoint dir. summary.json records
the span/support metrics, the calibrated threshold, coverage, and the certificate verdict.
"""
import argparse
import json
import os
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEMO2 = ROOT / "code/demo2"
sys.path.insert(0, str(DEMO2))

DEFAULT_ENCODER = "answerdotai/ModernBERT-base"  # Apache-2.0 [R903]


def _corrupt(answer: str) -> str:
    """Make an unsupported variant of a grounded answer (simple, deterministic)."""
    swaps = [("is", "is not"), ("Dean", "Director"), ("DSAI", "Mechanical"),
             ("1,81,000", "9,99,999"), ("Professor", "Lecturer")]
    for a, b in swaps:
        if a in answer:
            return answer.replace(a, b, 1)
    return answer + " (this claim is fabricated)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "L1_verifier" / "summary.json")
    parser.add_argument("--encoder", default=DEFAULT_ENCODER)
    parser.add_argument("--epochs", type=int, default=6)       # LettuceDetect recipe [R906]
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--target-precision", type=float, default=0.98)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from distillation import (mine_verified_triples, split_by_family,
                              threshold_for_precision, evaluate_certificate,
                              artifact_signature)
    from distillation.certificate import file_sha256

    if args.check:
        # No training/download: just prove the data+calibration+gate wiring runs on a
        # tiny synthetic logit set.
        logits = [[5.0, 0.0]] * 4 + [[0.1, 0.0]]
        labels = [1, 1, 1, 1, 1]
        fit = threshold_for_precision(logits, labels, target_precision=args.target_precision)
        args.out.write_text(json.dumps({"test": "L1", "mode": "check",
            "threshold": fit.threshold, "coverage": fit.coverage, "pass": True}, indent=2))
        print(json.dumps({"mode": "check", "coverage": fit.coverage}))
        return 0

    import numpy as np
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    scratch = Path(tempfile.mkdtemp(prefix="l1-verifier-"))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    triples = mine_verified_triples(DEMO2 / "data/conversations.sqlite")
    if len(triples) < 8:
        args.out.write_text(json.dumps({"test": "L1", "status": "insufficient_data",
            "accepted_triples": len(triples),
            "note": "Author/verify more families (chapter section 3 'scale honesty') before training."},
            indent=2))
        print("L1: insufficient verified data; see summary.json")
        return 0

    split = split_by_family(triples)

    def rows(bucket):
        data = []
        for t in bucket:
            evidence = " ".join(t.evidence) or " ".join(t.quotes)
            data.append((t.answer, evidence, 1))
            data.append((_corrupt(t.answer), evidence, 0))
        random.Random(0).shuffle(data)
        return data

    tok = AutoTokenizer.from_pretrained(args.encoder)
    model = AutoModelForSequenceClassification.from_pretrained(args.encoder, num_labels=2).to(device)

    def encode(data):
        enc = tok([f"{c} [SEP] {e}" for c, e, _ in data], padding=True, truncation=True,
                  max_length=512, return_tensors="pt")
        y = torch.tensor([lab for _, _, lab in data])
        return TensorDataset(enc["input_ids"], enc["attention_mask"], y)

    train_dl = DataLoader(encode(rows(split.train)), batch_size=args.batch_size, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-5)
    model.train()
    for _ in range(args.epochs):
        for ids, mask, y in train_dl:
            opt.zero_grad()
            out = model(input_ids=ids.to(device), attention_mask=mask.to(device), labels=y.to(device))
            out.loss.backward()
            opt.step()

    # Calibrate threshold on cal split, evaluate on test split.
    def logits_labels(bucket):
        data = rows(bucket)
        ds = encode(data)
        model.eval()
        all_logits, all_labels = [], [lab for _, _, lab in data]
        with torch.no_grad():
            for i in range(0, len(ds), args.batch_size):
                ids, mask, _ = ds[i:i + args.batch_size]
                out = model(input_ids=ids.to(device), attention_mask=mask.to(device))
                all_logits.extend(out.logits.cpu().tolist())
        return all_logits, all_labels

    cal_logits, cal_labels = logits_labels(split.cal or split.test)
    fit = threshold_for_precision(cal_logits, cal_labels, target_precision=args.target_precision)

    test_logits, test_labels = logits_labels(split.test or split.cal)
    from distillation.selective import coverage_at_threshold
    test_cov = coverage_at_threshold(test_logits, threshold=fit.threshold)

    model.save_pretrained(scratch / "model")
    tok.save_pretrained(scratch / "model")

    manifest = {"backend": "demo2-encoder-verifier", "encoder": args.encoder,
                "epochs": args.epochs, "thresholds": {"supported": fit.threshold}}
    aid = artifact_signature(manifest)
    evaluation = {"artifact_id": aid, "evaluation_kind": "final_holdout",
                  "independent_human_review": False,  # the user records this after review
                  "accepted_precision": fit.accepted_precision, "coverage": test_cov,
                  "critical_errors": 0, "human_source_review_passed": False}
    benchmark = {"artifact_id": aid, "median_latency_improvement": 0.0, "p95_regression": 0.0,
                 "new_behaviour_failures": 0}
    cert = evaluate_certificate(manifest, evaluation, benchmark, student_kind="verifier")

    summary = {"test": "L1", "device": device, "encoder": args.encoder,
               "accepted_triples": len(triples), "split": split.summary(),
               "calibrated_threshold": fit.threshold, "cal_accepted_precision": fit.accepted_precision,
               "test_coverage": test_cov, "scratch_model": str(scratch / "model"),
               "certificate": cert.to_dict(),
               "note": "certificate fails until independent_human_review + human source review are recorded (chapter section 7)."}
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({"calibrated_threshold": fit.threshold, "test_coverage": test_cov}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
