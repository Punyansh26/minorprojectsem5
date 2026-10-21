"""Compact pretrained encoder and masked decision heads; no runtime downloads."""
import torch
from torch import nn
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer

from .common import INTENTS, CATEGORIES
from .english_policy import HEADS, MAX_TOKENS


class EnglishRouter(nn.Module):
    """Share one English representation across task-specific decision heads."""

    def __init__(self, encoder_path, *, frozen=False):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(str(encoder_path), local_files_only=True,
                                                trust_remote_code=False, use_safetensors=True)
        self.tokenizer = AutoTokenizer.from_pretrained(str(encoder_path), local_files_only=True,
                                                      trust_remote_code=False)
        self.frozen = frozen
        self.encoder.requires_grad_(not frozen)
        width = self.encoder.config.hidden_size
        self.heads = nn.ModuleDict({name: nn.Linear(width, count) for name, count in
                                   zip(HEADS, (len(INTENTS), len(CATEGORIES), 2, 2))})
        self.dropout = nn.Dropout(.1)

    def train(self, mode=True):
        """Frozen baselines must not acquire noisy encoder dropout during training."""
        super().train(mode)
        if self.frozen:
            self.encoder.eval()
        return self

    def token_lengths(self, messages):
        """Detect oversized messages before tokenization can silently truncate them."""
        return [len(x) for x in self.tokenizer(messages, truncation=False)["input_ids"]]

    def forward(self, messages):
        if any(n > MAX_TOKENS for n in self.token_lengths(messages)):
            raise ValueError("English router input exceeds token limit")
        device = next(self.parameters()).device
        tokens = self.tokenizer(messages, padding=True, truncation=False, return_tensors="pt").to(device)
        hidden = self.encoder(**tokens).last_hidden_state
        mask = tokens["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = F.normalize((hidden * mask).sum(1) / mask.sum(1).clamp_min(1), p=2, dim=1)
        pooled = self.dropout(pooled)
        return {name: layer(pooled) for name, layer in self.heads.items()}


def targets(rows, device):
    """Mask task labels for rejection-only examples and irrelevant category heads."""
    english = torch.tensor([r["gold"]["language"] == "english" for r in rows], device=device)
    knowledge = torch.tensor([r["gold"]["intent"] == "knowledge" for r in rows], device=device) & english
    values = {"intent": [INTENTS.index(r["gold"]["intent"]) for r in rows],
              "category": [CATEGORIES.index(r["gold"]["category"]) for r in rows],
              "rewrite": [int(r["gold"]["rewrite"]) for r in rows], "english": english.long()}
    values = {name: torch.as_tensor(value, dtype=torch.long, device=device) for name, value in values.items()}
    masks = {"intent": english, "category": knowledge, "rewrite": knowledge,
             "english": torch.ones(len(rows), dtype=torch.bool, device=device)}
    return values, masks


def masked_loss(logits, rows):
    """Avoid teaching fake intent/category targets to non-English rejection examples."""
    values, masks = targets(rows, logits["intent"].device)
    losses = [F.cross_entropy(logits[name][masks[name]], values[name][masks[name]])
              for name in HEADS if masks[name].any()]
    return torch.stack(losses).mean()


def predictions(logits, temperatures=None):
    """Use calibrated probabilities instead of a synthetic learned confidence head."""
    temperatures = temperatures or {name: 1. for name in HEADS}
    probabilities = {name: (value / temperatures[name]).softmax(-1).detach().cpu().tolist()
                     for name, value in logits.items()}
    result = []
    for i in range(len(probabilities["intent"])):
        row = {}
        for name, labels in (("intent", INTENTS), ("category", CATEGORIES)):
            distribution = probabilities[name][i]
            best = max(range(len(distribution)), key=distribution.__getitem__)
            row.update({name: labels[best], name + "_probability": distribution[best], name + "_distribution": distribution})
        english = probabilities["english"][i][1]
        row.update(language="english" if english >= .5 else "unsupported", english_probability=english,
                   rewrite_probability=probabilities["rewrite"][i][1])
        result.append(row)
    return result


def load_router(root, manifest):
    """Load only the exact local assets already validated by the worker boundary."""
    from pathlib import Path
    model = EnglishRouter(Path(root) / manifest["encoder_dir"])
    model.heads.load_state_dict(torch.load(Path(root) / manifest["heads_file"], map_location="cpu", weights_only=True), strict=True)
    return model.eval()
