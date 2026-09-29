# RCA Methodology

## Goal

Answer "what changed, and which segments moved with it?" — from an aggregate KPI
movement to the contributing dimensions — **without claiming causality**.

## Procedure

1. **Period selection.** Current period vs an equal-length previous period
   immediately before it. The default window is the latest 2 weeks vs the prior
   2 weeks (`_latest_two_weeks`).

2. **Merchant-level movement.**
   ```
   overall_delta_pp = overall_SR_current − overall_SR_previous
   ```

3. **Per-dimension segment aggregation.** For each dimension in
   `payment_method, payment_type, card_type, issuer_bank, device, platform,
   error_category, industry, mcc, country`, aggregate eligible/authorized counts
   per segment value in each period.

4. **Per-segment metrics.**
   - `current_sr`, `previous_sr`, `delta_pp = current − previous`
   - `volume_current`, `volume_previous`

5. **Contribution.**
   ```
   contribution_s = previous_volume_share_s × delta_pp_s
   ```
   where `previous_volume_share_s = volume_previous_s / total_volume_previous`.
   Positive contribution = moved the metric up; negative = moved it down.

6. **Share of decline** (within a dimension):
   ```
   share_of_decline_s = |contribution_s| / Σ_segments |contribution_s|
   ```

7. **Ranking.** Contributors are ranked by absolute contribution, restricted to
   those moving in the same direction as the overall delta. Dimensions that are
   constant per merchant (country, mcc, industry for a single merchant) are
   excluded from the top list — they merely echo the total.

## Error-category handling

Error categories are failures, so their within-category SR is always 0%. Instead
the metric is the **failure share**: `category_failures / total_eligible × 100`.
A rising failure share reduces overall SR, so its contribution is
`−(current_share − previous_share)`.

## Guardrails

- Segments with < 50 eligible transactions in either period are flagged
  `low_sample` and should be interpreted cautiously.
- Contribution is a **decomposition heuristic**; it assumes a roughly stable mix
  and does not attribute causation even when a single segment explains most of
  the movement.

## Language rules

Used: **contributor**, **associated movement**, **concentrated decline**,
**observed pattern**, **major contributor**.

Avoided: **caused by**, **root cause**, **because of** — unless causal evidence
exists (it does not, in this observational synthetic dataset).

## Worked example (Nova Fashion, M0013)

```
Overall: 97.07% → 91.49%   (−5.58 pp)
Contributors:
  platform = Android          delta −5.73 pp   (major contributor)
  payment_method = Debit Card delta −6.82 pp   (worst method)
  issuer_bank = HDFC          delta −7.37 pp   (elevated)
  error_category = Issuer Decline share 1.72% → 3.81% (elevated)
```

Interpretation: the movement is **concentrated** on Android and Debit Card, and
an issuer/error pattern is **associated** with it. Recommended next step:
investigate issuer/error-category performance for the Android debit-card
segment. No causal claim is made.
