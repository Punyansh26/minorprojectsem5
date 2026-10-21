"""A small shared encoder predicts an executable query strategy, never answer text."""
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F

from .common import INTENTS, CATEGORIES
from .english_model import EnglishRouter
from .english_normalization import normalize_message
from .english_v3_policy import HEADS, QUERY_ACTIONS


class QueryRouter(EnglishRouter):
    """Reuse the pinned encoder and pooling while keeping v2 weights compatible."""
    def __init__(self, encoder_path, *, frozen=False):
        super().__init__(encoder_path, frozen=frozen)
        width = self.encoder.config.hidden_size
        self.heads = nn.ModuleDict({name: nn.Linear(width, count) for name, count in
                                   zip(HEADS, (len(INTENTS), len(CATEGORIES), len(QUERY_ACTIONS), 2))})

    def forward(self, messages):
        return super().forward([normalize_message(message) for message in messages])

    def token_lengths(self, messages):
        return super().token_lengths([normalize_message(message) for message in messages])


def targets(rows, device):
    """Learn query preparation only on English knowledge examples."""
    english = torch.tensor([r["gold"]["language"] == "english" for r in rows], device=device)
    knowledge = torch.tensor([r["gold"]["intent"] == "knowledge" for r in rows], device=device) & english
    values = {"intent": [INTENTS.index(r["gold"]["intent"]) for r in rows],
              "category": [CATEGORIES.index(r["gold"]["category"]) for r in rows],
              "query_action": [QUERY_ACTIONS.index(r["gold"]["query_action"]) for r in rows],
              "english": english.long()}
    values = {name: torch.as_tensor(value, dtype=torch.long, device=device) for name, value in values.items()}
    # A scope head trained only on college questions cannot learn to defer trivia.
    masks = {"intent": english, "category": knowledge, "query_action": english,
             "english": torch.ones(len(rows), dtype=torch.bool, device=device)}
    return values, masks


def masked_loss(logits, rows):
    """Avoid misleading task targets on unsupported-language examples."""
    values, masks = targets(rows, logits["intent"].device)
    return torch.stack([F.cross_entropy(logits[name][masks[name]], values[name][masks[name]])
                        for name in HEADS if masks[name].any()]).mean()


def predictions(logits, temperatures=None):
    """Return calibrated probabilities for the shared runtime and evaluator."""
    temperatures = temperatures or {name: 1. for name in HEADS}
    probabilities = {name: (value / temperatures[name]).softmax(-1).detach().cpu().tolist()
                     for name, value in logits.items()}
    result = []
    for i in range(len(probabilities["intent"])):
        row = {}
        for name, labels in (("intent", INTENTS), ("category", CATEGORIES), ("query_action", QUERY_ACTIONS)):
            distribution = probabilities[name][i]
            best = max(range(len(distribution)), key=distribution.__getitem__)
            row.update({name: labels[best], name + "_probability": distribution[best], name + "_distribution": distribution})
        english = probabilities["english"][i][1]
        row.update(language="english" if english >= .5 else "unsupported", english_probability=english)
        result.append(row)
    return result


def load_router(root, manifest):
    """Runtime loads only local, previously checksum-validated assets."""
    model = QueryRouter(Path(root) / manifest["encoder_dir"])
    model.heads.load_state_dict(torch.load(Path(root) / manifest["heads_file"], map_location="cpu", weights_only=True), strict=True)
    return model.eval()
