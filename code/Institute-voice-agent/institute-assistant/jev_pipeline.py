"""Prepare, train, calibrate and evaluate local routers with explicit activation gates."""
import argparse
from pathlib import Path


def main():
    from assistant.config import settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", default=str(Path.home() / ".cache/institute-assistant/open-jev/pilot-v1"))
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--profile", choices=["pilot-v1", "english-v2", "english-v3"], default="pilot-v1")
    sub.add_parser("label")
    train_parser = sub.add_parser("train")
    train_parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    train_parser.add_argument("--resume", action="store_true", help="Resume matching English checkpoints; start if absent")
    train_parser.add_argument("--max-seconds", type=int, default=7200,
                              help="English training budget, split equally between candidates; completed epochs are resumable")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--holdout", type=Path, help="Fresh public English holdout JSON with authored labels")
    evaluate_parser.add_argument("--review", type=Path, help="Independent human review bound to dataset SHA and artifact ID")
    evaluate_parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    benchmark_parser = sub.add_parser("benchmark")
    benchmark_parser.add_argument("--quick", action="store_true", help="Diagnostic subset only; cannot satisfy activation")
    benchmark_parser.add_argument("--trials", type=int, default=3, help="Complete paired trials (default 3); quick defaults to one")
    sub.add_parser("activate")
    sub.add_parser("report", help="Print English development results without touching a final holdout")
    audit_parser = sub.add_parser("audit", help="Check frozen English thresholds on additional public development scenarios; no training or activation")
    audit_parser.add_argument("--output", required=True, type=Path)
    audit_parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    freeze_parser = sub.add_parser("freeze", help="Export passing development calibration into a separate artifact; does not activate")
    freeze_parser.add_argument("--audit", type=Path, help="Required for english-v2; v3 freezes its supported calibration")
    freeze_parser.add_argument("--output", required=True, type=Path)
    calibrate_parser = sub.add_parser("calibrate", help="Recalibrate v3 weights into a separate artifact; no retraining")
    calibrate_parser.add_argument("--output", required=True, type=Path)
    normalize_parser = sub.add_parser("normalize", help="Export a calibrated candidate with versioned institute-name normalization")
    normalize_parser.add_argument("--output", required=True, type=Path)
    extend_parser = sub.add_parser("extend", help="Copy a completed English run into a new directory with longer stopping limits")
    extend_parser.add_argument("--output", required=True, type=Path)
    extend_parser.add_argument("--epochs", type=int, default=40)
    extend_parser.add_argument("--patience", type=int, default=5)
    args = parser.parse_args()
    root = Path(args.artifacts).expanduser().resolve()
    from assistant.jev.common import read_json
    profile = read_json(root / "profile.json").get("profile") if (root / "profile.json").exists() else None
    if (args.command == "prepare" and args.profile == "english-v3") or profile == "english-v3":
        from assistant.jev import english_v3_training as v3
        if args.command == "prepare":
            if args.profile != "english-v3":
                parser.error("Use prepare --profile english-v3 for this directory")
            v3.prepare(root)
        elif args.command == "train":
            if read_json(root / "profile.json").get("stage") == "calibrated":
                parser.error("Frozen artifacts are immutable; train in the development directory")
            v3.train(root, args.device, args.resume, args.max_seconds,
                     config=read_json(root / "profile.json")["config"])
        elif args.command == "freeze":
            v3.freeze(root, args.output)
        elif args.command == "calibrate":
            v3.recalibrate(root, args.output)
        elif args.command == "evaluate" and (args.holdout or args.review):
            if not (args.holdout and args.review):
                parser.error("Final evaluation requires both --holdout and --review")
            from assistant.jev.english_holdout import evaluate_holdout
            evaluate_holdout(root, args.holdout, args.review, args.device)
        elif args.command in {"report", "evaluate"}:
            v3.report(root)
        elif args.command == "benchmark":
            from assistant.jev.evaluation import benchmark
            benchmark(root, quick=args.quick, trials=1 if args.quick else args.trials)
        elif args.command == "activate":
            from assistant.jev.evaluation import activate
            activate(root)
        else:
            parser.error("V3 supports prepare, train, freeze, report, evaluate, benchmark and activate")
        return
    if args.command == "calibrate":
        parser.error("calibrate requires an english-v3 artifact")
    if (args.command == "prepare" and args.profile == "english-v2") or profile == "english-v2":
        from assistant.jev import english_training
        if ((root / "profile.json").exists() and read_json(root / "profile.json").get("stage") == "calibrated"
                and args.command in {"prepare", "train", "extend", "audit", "freeze"}):
            parser.error("Calibrated artifacts are immutable; use the original training directory for new experiments")
        if args.command == "prepare":
            if args.profile != "english-v2":
                parser.error("This directory is English-only; use prepare --profile english-v2")
            english_training.prepare(root)
        elif args.command == "train":
            english_training.train(root, args.device, args.resume, args.max_seconds,
                                   config=read_json(root / "profile.json")["config"])
        elif args.command == "extend":
            from assistant.jev.english_continuation import extend
            extend(root, args.output, args.epochs, args.patience)
        elif args.command == "audit":
            from assistant.jev.english_audit import audit
            audit(root, args.output, args.device)
        elif args.command == "freeze":
            if not args.audit:
                parser.error("English v2 freeze requires --audit")
            from assistant.jev.english_freeze import freeze
            freeze(root, args.audit, args.output)
        elif args.command == "normalize":
            from assistant.jev.english_normalization import normalize_artifact
            normalize_artifact(root, args.output)
        elif args.command == "evaluate" and (args.holdout or args.review):
            if not (args.holdout and args.review):
                parser.error("Final evaluation requires both --holdout and --review")
            from assistant.jev.english_holdout import evaluate_holdout
            evaluate_holdout(root, args.holdout, args.review, args.device)
        elif args.command in {"report", "evaluate"}:
            from assistant.jev.runtime import checked_manifest, artifact_signature
            import json
            from assistant.jev.common import json_hash
            manifest = checked_manifest(str(root), artifact_signature(root))
            report = read_json(root / ("calibration_summary.json" if
                read_json(root / "profile.json").get("stage") == "calibrated" else "training_summary.json"))
            if report["artifact_id"] != json_hash(manifest):
                parser.error("Development summary does not match the current artifact")
            if (root / "evaluation.json").exists():
                final = read_json(root / "evaluation.json")
                if final["artifact_id"] != json_hash(manifest):
                    parser.error("Final evaluation does not match the current artifact")
                report = {**report, "final_evaluation": final}
            print(json.dumps(report, indent=2))
        elif args.command == "label":
            parser.error("English targets are prepared from reviewed scenarios; no teacher labeling is used")
        else:
            from assistant.jev import evaluation
            if args.command == "benchmark":
                evaluation.benchmark(root, quick=args.quick, trials=1 if args.quick else args.trials)
            else:
                evaluation.activate(root)
        return
    if args.command in {"report", "extend", "audit", "freeze", "normalize"}:
        parser.error(f"{args.command} requires a prepared English artifact directory")
    if args.command == "evaluate" and (args.holdout or args.review or args.device != "cpu"):
        parser.error("External holdout evaluation requires an English artifact directory")
    if args.command in {"prepare", "label", "train"}:
        from assistant.jev import training
        if args.command == "prepare":
            training.prepare(root)
        elif args.command == "label":
            training.label(root, settings)
        else:
            if args.resume or args.max_seconds != 7200:
                parser.error("--resume/--max-seconds apply to the English recovery profile")
            training.train(root, args.device)
    else:
        from assistant.jev import evaluation
        if args.command == "benchmark":
            evaluation.benchmark(root, quick=args.quick, trials=1 if args.quick else args.trials)
        else:
            getattr(evaluation, args.command)(root)


if __name__ == "__main__":
    main()
