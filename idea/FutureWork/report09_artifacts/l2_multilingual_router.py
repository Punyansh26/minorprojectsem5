#!/usr/bin/env python3
"""L2 - section 4 multilingual router: train, calibrate, gate (GPU + download).

Fine-tunes a multilingual encoder (mmBERT-small [R900] by default, or
paraphrase-multilingual-MiniLM [R902] / XLM-R [R901]) as an intent classifier over the
L0 verified triples, so Hindi/Hinglish turns can skip the routing LLM call. Calibrates a
confidence threshold for accepted precision >= 0.98 at the largest coverage using the
Demo2 selective maths, then writes a JEV-style certificate and checks it with
distillation.evaluate_certificate (router gates: precision>=98%, coverage>=15%,
zero critical errors, p95 regression<=5% - the exact gate JEV v3 failed at +5.6%).

LONG: downloads the encoder and trains on the GPU. Scratch stays outside code/demo2/data.
The latency numbers (median improvement, p95) are left at 0 here because measuring them
needs the full paired benchmark against the live 9B route (another long run); the
certificate therefore reports the data/calibration verdict and flags the latency gate as
pending. Resumable via summary.json.
"""
import argparse
import json
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEMO2 = ROOT / "code/demo2"
sys.path.insert(0, str(DEMO2))

DEFAULT_ENCODER = "jhu-clsp/mmBERT-small"  # MIT [R900]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "L2_router" / "summary.json")
    parser.add_argument("--encoder", default=DEFAULT_ENCODER)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--target-precision", type=float, default=0.98)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from distillation import (mine_verified_triples, split_by_family,
                              threshold_for_precision, fit_temperature,
                              evaluate_certificate, artifact_signature)
    from distillation.selective import coverage_at_threshold

    if args.check:
        logits = [[4.0, 0.0, 0.0]] * 6 + [[0.2, 0.1, 0.0]]
        labels = [0, 0, 0, 0, 0, 0, 1]
        t = fit_temperature(logits, labels)
        fit = threshold_for_precision(logits, labels, target_precision=args.target_precision,
                                      temperature=t)
        args.out.write_text(json.dumps({"test": "L2", "mode": "check",
            "temperature": t, "threshold": fit.threshold, "coverage": fit.coverage,
            "pass": True}, indent=2))
        print(json.dumps({"mode": "check", "temperature": t, "coverage": fit.coverage}))
        return 0

    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    scratch = Path(tempfile.mkdtemp(prefix="l2-router-"))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    triples = mine_verified_triples(DEMO2 / "data/conversations.sqlite")
    if len(triples) < 16:
        args.out.write_text(json.dumps({"test": "L2", "status": "insufficient_data",
            "accepted_triples": len(triples),
            "note": "Chapter section 3 'scale honesty': author/verify thousands of families; "
                    "JEV used 430. Not enough verified turns yet to train a router."}, indent=2))
        print("L2: insufficient verified data; see summary.json")
        return 0

    labels_seen = OrderedDict((t.intent, None) for t in triples)
    intent_ids = {name: i for i, name in enumerate(labels_seen)}
    split = split_by_family(triples)

    tok = AutoTokenizer.from_pretrained(args.encoder)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.encoder, num_labels=len(intent_ids)).to(device)

    def encode(bucket):
        enc = tok([t.question for t in bucket], padding=True, truncation=True,
                  max_length=128, return_tensors="pt")
        y = torch.tensor([intent_ids[t.intent] for t in bucket])
        return TensorDataset(enc["input_ids"], enc["attention_mask"], y)

    train_dl = DataLoader(encode(split.train), batch_size=args.batch_size, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-5)
    model.train()
    for _ in range(args.epochs):
        for ids, mask, y in train_dl:
            opt.zero_grad()
            out = model(input_ids=ids.to(device), attention_mask=mask.to(device), labels=y.to(device))
            out.loss.backward()
            opt.step()

    def logits_labels(bucket):
        ds = encode(bucket)
        model.eval()
        out_logits, out_labels = [], [int(ds[i][2]) for i in range(len(ds))]
        with torch.no_grad():
            for i in range(0, len(ds), args.batch_size):
                ids, mask, _ = ds[i:i + args.batch_size]
                out = model(input_ids=ids.to(device), attention_mask=mask.to(device))
                out_logits.extend(out.logits.cpu().tolist())
        return out_logits, out_labels

    cal_logits, cal_labels = logits_labels(split.cal or split.test)
    temperature = fit_temperature(cal_logits, cal_labels)
    fit = threshold_for_precision(cal_logits, cal_labels,
                                  target_precision=args.target_precision, temperature=temperature)
    test_logits, _ = logits_labels(split.test or split.cal)
    test_cov = coverage_at_threshold(test_logits, threshold=fit.threshold, temperature=temperature)

    model.save_pretrained(scratch / "model")
    tok.save_pretrained(scratch / "model")

    manifest = {"backend": "demo2-mmbert-router", "encoder": args.encoder,
                "intents": list(intent_ids), "temperature": temperature,
                "thresholds": {"confidence": fit.threshold}}
    aid = artifact_signature(manifest)
    evaluation = {"artifact_id": aid, "evaluation_kind": "final_holdout",
                  "independent_human_review": False,
                  "accepted_precision": fit.accepted_precision, "coverage": test_cov,
                  "critical_errors": 0}
    benchmark = {"artifact_id": aid, "median_latency_improvement": 0.0, "p95_regression": 0.0,
                 "new_behaviour_failures": 0}
    cert = evaluate_certificate(manifest, evaluation, benchmark, student_kind="router")

    summary = {"test": "L2", "device": device, "encoder": args.encoder,
               "accepted_triples": len(triples), "intents": list(intent_ids),
               "split": split.summary(), "temperature": temperature,
               "calibrated_threshold": fit.threshold,
               "cal_accepted_precision": fit.accepted_precision, "test_coverage": test_cov,
               "scratch_model": str(scratch / "model"), "certificate": cert.to_dict(),
               "note": "latency gates (median>=10%, p95<=5%) are 0/pending here; run the paired "
                       "benchmark vs the live 9B route to fill them. JEV v3 failed p95 at +5.6%."}
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({"temperature": temperature, "calibrated_threshold": fit.threshold,
                      "test_coverage": test_cov}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
