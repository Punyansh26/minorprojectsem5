# Open Jev provenance

Source: https://github.com/kyegomez/open-jev
Revision: 93843ef288f3d35fd91263377c40b6f917d77da0
File: open_jev/main.py, copied unchanged as model.py.
License: Apache-2.0 (LICENSE alongside this file).

This is an unofficial research reconstruction, not TypeSafe's production model.
Upstream comments about calibration/performance describe design intentions, not
measured guarantees. Our adapter supplies a trained byte-level BPE tokenizer and
uses the differentiable `logits` interface. No upstream weights are supplied.
