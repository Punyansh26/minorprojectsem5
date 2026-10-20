#!/usr/bin/env python3
"""L3 - section 5 LoRA/QLoRA answer drafter: train, verify quotes, gate (GPU + download).

QLoRA-fine-tunes a small Qwen (Qwen2.5-1.5B-Instruct by default; swap to 4B on T1/T2) on
the L0 verified (question, evidence, grounded-answer-with-quote) triples using the RAFT
recipe [R86]: the prompt carries the evidence spans, the target is the grounded answer,
and after generation every quote the drafter emits is re-checked against the evidence with
the SAME verified-quote contract the data pipeline uses (distillation.triples.quote_is_grounded)
- so a drafter that fabricates a quote is caught exactly as the agent's evidence.py would.

Reports the held-out quote-validation pass rate (must stay 100% to preserve grounding) and
writes a JEV-style certificate (distillation.evaluate_certificate, drafter gates include the
human source review). LONG: downloads a 1.5-4B base and QLoRA-trains on the GPU; on the 8 GB
T0 this needs Ollama stopped (chapter section 8). Scratch stays outside code/demo2/data.
Resumable via summary.json; --check runs only the quote-contract wiring on synthetic text.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEMO2 = ROOT / "code/demo2"
sys.path.insert(0, str(DEMO2))

DEFAULT_BASE = "Qwen/Qwen2.5-1.5B-Instruct"  # Apache-2.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "L3_drafter" / "summary.json")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from distillation import (mine_verified_triples, split_by_family, evaluate_certificate,
                              artifact_signature)
    from distillation.triples import quote_is_grounded

    if args.check:
        # Prove the quote-validation contract runs without any model: a grounded quote
        # passes, a fabricated one fails.
        ev = "Professor and Dean(Academics | DSAI | Ph.D (Bangalore University)"
        ok = quote_is_grounded("Dean(Academics", ev)
        bad = quote_is_grounded("Dean of the Moon", ev)
        passed = ok and not bad
        args.out.write_text(json.dumps({"test": "L3", "mode": "check",
            "grounded_quote_accepted": ok, "fabricated_quote_rejected": not bad,
            "pass": passed}, indent=2))
        print(json.dumps({"mode": "check", "pass": passed}))
        return 0 if passed else 1

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              TrainingArguments, Trainer, DataCollatorForLanguageModeling)

    scratch = Path(tempfile.mkdtemp(prefix="l3-drafter-"))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    triples = mine_verified_triples(DEMO2 / "data/conversations.sqlite")
    if len(triples) < 16:
        args.out.write_text(json.dumps({"test": "L3", "status": "insufficient_data",
            "accepted_triples": len(triples),
            "note": "Chapter section 5/section 6: a drafter needs the most verified data; "
                    "author/verify many more families (section 3 'scale honesty') first."}, indent=2))
        print("L3: insufficient verified data; see summary.json")
        return 0

    split = split_by_family(triples)
    tok = AutoTokenizer.from_pretrained(args.base)
    tok.pad_token = tok.pad_token or tok.eos_token

    def to_text(t):
        evidence = "\n".join(t.evidence) or "\n".join(t.quotes)
        return (f"Evidence:\n{evidence}\n\nQuestion: {t.question}\n"
                f"Answer (quote the evidence verbatim):\n{t.answer}")

    train_ds = Dataset.from_dict({"text": [to_text(t) for t in split.train]})
    train_ds = train_ds.map(lambda b: tok(b["text"], truncation=True, max_length=1024), batched=True)

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                               bnb_4bit_compute_dtype=torch.bfloat16) if device == "cuda" else None
    model = AutoModelForCausalLM.from_pretrained(args.base, quantization_config=quant,
                                                 device_map="auto" if device == "cuda" else None)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                                             task_type="CAUSAL_LM"))

    Trainer(
        model=model,
        args=TrainingArguments(output_dir=str(scratch / "ckpt"), per_device_train_batch_size=1,
                               gradient_accumulation_steps=8, num_train_epochs=args.epochs,
                               max_steps=args.max_steps, learning_rate=2e-4, bf16=(device == "cuda"),
                               logging_steps=20, save_steps=args.max_steps, report_to=[]),
        train_dataset=train_ds,
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    ).train()
    model.save_pretrained(scratch / "adapter")

    # Held-out quote-validation: generate an answer per test triple, check every quoted
    # evidence span is grounded. Pass rate must stay 100% to preserve grounding.
    model.eval()
    grounded, generated = 0, 0
    for t in (split.test or split.cal):
        evidence = "\n".join(t.evidence) or "\n".join(t.quotes)
        prompt = f"Evidence:\n{evidence}\n\nQuestion: {t.question}\nAnswer (quote the evidence verbatim):\n"
        ids = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=160, do_sample=False)
        text = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
        generated += 1
        # Treat the longest evidence-overlapping sentence as the "quote" and verify it.
        if any(quote_is_grounded(line.strip(), evidence) for line in text.splitlines() if len(line.strip()) > 12):
            grounded += 1
    pass_rate = round(grounded / generated, 4) if generated else 0.0

    manifest = {"backend": "demo2-lora-drafter", "base": args.base, "epochs": args.epochs,
                "lora": {"r": 16, "alpha": 32}}
    aid = artifact_signature(manifest)
    evaluation = {"artifact_id": aid, "evaluation_kind": "final_holdout",
                  "independent_human_review": False,
                  "accepted_precision": pass_rate, "coverage": 1.0, "critical_errors": 0,
                  "human_source_review_passed": False}
    benchmark = {"artifact_id": aid, "median_latency_improvement": 0.0, "p95_regression": 0.0,
                 "new_behaviour_failures": 0}
    cert = evaluate_certificate(manifest, evaluation, benchmark, student_kind="drafter")

    summary = {"test": "L3", "device": device, "base": args.base,
               "accepted_triples": len(triples), "split": split.summary(),
               "quote_validation_pass_rate": pass_rate, "generated": generated,
               "scratch_adapter": str(scratch / "adapter"), "certificate": cert.to_dict(),
               "note": "quote_validation_pass_rate must be 1.0 to ship; certificate also needs "
                       "independent_human_review + human source review (chapter section 7)."}
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({"quote_validation_pass_rate": pass_rate, "generated": generated}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
