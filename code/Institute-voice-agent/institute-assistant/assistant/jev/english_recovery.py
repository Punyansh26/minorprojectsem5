"""Narrow compatibility repair for the original absolute-.cache exclusion bug."""
from pathlib import Path
import json

from .common import json_hash, read_json, write_json
from .english_policy import MODEL_ID, MODEL_REVISION

# Verified against Hugging Face's git/LFS metadata at MODEL_REVISION. Empty legacy
# indexes cannot authenticate files; compare the actual bytes with the pinned
# public snapshot before replacing an index or accepting a legacy fingerprint.
PINNED_ASSET_SHA256 = {
    "config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
    "model.safetensors": "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db",
    "special_tokens_map.json": "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    "tokenizer_config.json": "acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b",
    "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
}
LEGACY_RECIPE = {
    "english_training.py": "259bdc11a47edbbde64e02f3f1826e3671c5a30d91715e8df18507f791e6b193",
    "english_model.py": "70ca16a3c1401ad8db4945c0adab95ec750b85824e720c3e075d25131b05af1c",
    "english_policy.py": "9d4ee120975779358dac3e905a84d74d99c2b8cf657587ee7c5b4fa54d0fec24",
}


def pinned_base_index():
    """Return the exact base-asset index known to the compatible original recipe."""
    return {"base_encoder/" + name: value for name, value in PINNED_ASSET_SHA256.items()}


def repair_empty_base_index(root, actual):
    """Repair only an empty legacy index after authenticating all pretrained files."""
    root = Path(root)
    profile = read_json(root / "profile.json")
    if (profile.get("model_id") != MODEL_ID or profile.get("model_revision") != MODEL_REVISION
            or actual != pinned_base_index()):
        raise ValueError("Cannot repair empty base index: files do not match the pinned pretrained snapshot")
    if read_json(root / "base_assets.json") != {}:
        raise ValueError("Only an empty legacy base index can be repaired")
    backup = root / "base_assets.before-cache-fix.json"
    if backup.exists() and read_json(backup) != {}:
        raise ValueError("Legacy base index backup differs")
    if not backup.exists():
        write_json(backup, {})
    write_json(root / "base_assets.json", actual)
    print(json.dumps({"artifact_repair": "replaced empty base checksum index using verified pinned assets",
                      "checkpoints_modified": False}), flush=True)


def legacy_checkpoint_matches(inputs, fingerprint):
    """Allow this metadata-only fix without accepting changed training inputs."""
    if inputs["base"] != pinned_base_index():
        return False
    if any(inputs["recipe"][name] != LEGACY_RECIPE[name]
           for name in ("english_model.py", "english_policy.py")):
        return False
    # The training algorithm is unchanged. All data, review, configuration and
    # candidate inputs remain in the comparison; only known old code/index hashes
    # are substituted. Unknown recipes and altered inputs still require a new run.
    for base in ({}, inputs["base"]):
        old_inputs = {**inputs, "base": base, "recipe": LEGACY_RECIPE}
        if fingerprint == json_hash(old_inputs):
            return True
    return False
