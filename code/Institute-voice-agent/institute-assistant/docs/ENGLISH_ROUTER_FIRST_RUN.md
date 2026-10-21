# English router: first trained run and next experiment

These are development results from `~/.cache/institute-assistant/open-jev/english-v2`.
The selected artifact ID is
`de35b39c98704f7d20372354c8c201f347f734d751527fe4b47b312419510967`.
The checkpoint completed training successfully; it remains unsuitable for activation.

| Metric | Frozen encoder | Fine-tuned encoder |
| --- | ---: | ---: |
| Validation intent accuracy (60 English rows) | 70.0% | 91.7% |
| Validation category accuracy (33 English knowledge rows) | 75.8% | 69.7% |
| Best validation masked NLL | 0.8444 | 0.5809 |
| Epochs completed | 10 | 10 |
| Supported deployment thresholds | None | None |

Overall intent accuracy is not complete route accuracy. The fine-tuned model's
department predictions are still weak, especially for academic queries assigned
to `general`. On the training split, department accuracy is only 78.8%; rewrite
accuracy is 97.7%, intent accuracy 95.0%, and English/defer accuracy 100%. These
training scores suggest incomplete fitting, not demonstrated unseen accuracy.

## Why accepted coverage is reported as zero

The saved fine-tuned calibration sweep contains a promising development point:
intent/category probability at least 0.8, English probability at least 0.99 and
rewrite probability at most 0.1. It accepts 14 of 56 threshold-selection rows
with 14 correct decisions and no critical errors. Only five accepted decisions
are knowledge questions. These thresholds fail the required support of 30
accepted families and ten accepted knowledge decisions, so `supported=false`
correctly makes the published candidate defer every request.

At that exploratory threshold point, rejection reasons are:

| Reason | Rows |
| --- | ---: |
| Low category confidence | 20 |
| Non-English | 9 |
| Action language | 7 |
| Rewrite required/predicted | 5 |
| Low intent confidence | 1 |
| Accepted | 14 |

An oracle using authored labels could accept 34 distinct families on this subset,
including 24 knowledge queries. Thus the 30-family support requirement is possible
but demanding on this small calibration subset. The sweep's 14/14 result was
selected on development data; it cannot establish final accuracy or certify a model.

## Next experiment

Both candidates improved validation loss in every saved epoch. The final two
fine-tuned values were 0.6221 and 0.5809. Training stopped at the configured
ten-epoch ceiling, not at an early-stopping plateau or the compute budget.

Prepare a separate continuation to a maximum of forty total epochs with
five-epoch validation patience. Preserve the original data, pretrained weights,
optimizer settings, calibration protocol and acceptance gates. Continue both
candidates from their saved optimizer/RNG state and retain the first run intact.
This isolates the effect of allowing more optimization; improvement is not guaranteed.

The user runs this training. Inspect the extended run's `training_summary.json`
afterward. If category quality or accepted support still fails, review category
boundaries and enlarge independently authored development/calibration families
before considering another training change. Final holdout and live RAG evaluation
remain deferred; no deployed speedup or answer-quality gain has been measured.
