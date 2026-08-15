---
name: e46-m3-market
description: Re-run Justin's BMW E46 M3 market analysis and re-value his 2004 Carbon Black / Cinnamon 6MT against Bring a Trailer sold data. Use for the monthly market check-in, or whenever he asks what his M3 is worth, what the E46 M3 market is doing, whether values are up or down, whether to sell now, how a specific car or listing compares, or refers to the BaT dataset, the hedonic model, or "the E46 analysis."
---

# E46 M3 market analysis

Recurring analysis of the BMW E46 M3 coupe secondary market, and a standing valuation
of Justin's car. Runs monthly. The point of each run is **what changed since last month**,
not a fresh essay — lead with the delta.

## The subject car

2004 M3 Coupe, VIN `WBSBL934X4PN58673`. Carbon Black Metallic over Cinnamon Nappa,
factory 6-speed manual (never converted), glass electric sunroof (option 0402 — **not**
a slicktop). 27,000 miles as of 2026-08-12, ~490 mi/yr under current ownership.
Three owners, zero accidents, clean continuous Carfax, 21 service records.
Rod bearings, RACP/subframe and VANOS all **not done** — subframe *inspected* only, 2016.

Full provenance, option codes and the sale-listing angle: `references/car.md`.

## Data

The source file is `E46_M3_BaT_Sold_Listings.xlsx`, which Justin refreshes periodically.

Get it in this order:

1. **Google Drive** (preferred — works unattended, no laptop required).
   File ID `1KzLo_3_s3_K-R61bWljvKx_j4FBVrVXp`, in `My Drive/Car/E46/`.
   Search `title contains 'E46_M3_BaT_Sold_Listings'` if the ID has gone stale.
2. **Device bridge** — `G:\My Drive\Car\E46\` on device `ser9pro-6r8efrj`. Only available
   when his desktop app is open, so never rely on it for a scheduled run.

Check the README sheet's pull date. If it has not moved since the last run, say so plainly
and skip the re-fit — an unchanged file means an unchanged answer, and a report implying
otherwise is worse than no report.

## Running it

```bash
python3 scripts/analyze.py <path-to-xlsx> \
    --asof <YYYY-MM-DD> \
    --mileage <current miles> \
    --baseline references/baseline.json
```

Emits JSON: coefficients with p-values, the valuation with prediction intervals,
sell-through by year, data-quality counters, and a `vs_baseline` block with the
month-over-month move. **Read the JSON before writing anything.**

After a run that you and Justin agree is sound, overwrite `references/baseline.json`
with the new output so next month diffs against it.

On the 2026-08-13 file the script reproduces the published v2 model exactly: n=651,
R²=0.807, point estimate $58,445. If a run deviates from that on unchanged data, the
script or the data changed — investigate before reporting.

## Model

OLS on log sale price, **v2 as of 2026-08-13**. Sample: BaT **sold** coupes with mileage from
the `All Listings` sheet (n=651), excluding modified, supercharged, swapped and track cars.

```
lnp ~ cr(lnm, df=4) + manual + zcp + C(color_grp) + C(int_grp)
      + racp_done + vanos_done + rb_done + no_res + C(yr) + slick + slick_unknown
```

Baselines: Titanium Silver paint, Black interior, moonroof confirmed present.
R² 0.807, cross-validated median absolute error 12.6%.

Three things changed at v2 and they matter:

- **Read the `All Listings` sheet, not `Detailed Sample (200)`.** Since the August 2026
  re-scrape both sheets carry the full schema, but the 200-row sheet is a recent-sales
  subset. Fitting on it discards three-quarters of the data and inflates several
  coefficients. The script picks the right sheet; don't override it.
- **Cubic spline in log-mileage.** The old log-linear form overpredicted sub-25k cars by
  ~9% and underpredicted the 25–40k band by ~6% — and Justin's car sits in that band.
  The spline flattens residuals to under ±2% across every mileage bin.
- **Year fixed effects, not a single exponential trend.** The market was not a smooth
  compounding curve. Indexed to 2017 (pre-2017 years are folded into it — too few sales
  to support their own effects): 2021 and 2022 boomed to 1.64 and 1.79, 2023–25 plateaued
  at 1.67–1.71, and 2026 set a new high at 1.93. A constant trend forces a straight line
  through that and leaves systematic residuals. AIC improves by 65 points.

**Always report a range, never a bare point estimate.** BaT results on one car genuinely
swing 20%+ night to night — the file identifies 44 relists proving it, e.g. a 47k-mile ZCP
that made $66,000 in May 2024 and $51,000 three months later.

## Reading the results

Things that are easy to get wrong, several learned by getting them wrong:

- **Never read raw medians as effects.** Preventive work looks *negative* in raw medians
  because owners do it on high-mileage cars. Only the regression separates that.
- **`rb_done` is not causal** (−1.9%, p≈0.31). A disclosed rod-bearing job marks a
  harder-used car. Report it as "no reliable effect," never as a discount.
- **Carbon Black is neutral** (−1.5%, p≈0.65) despite enthusiast lore. Justin's premium
  comes from Cinnamon and the odometer, not the paint.
- **Cinnamon is +16.7%, not +35%.** The August 2026 v1 figure came from 22 Cinnamon cars
  in a 27-month window. With 55 across 12 years it settles near +17%. A recent-window
  refit still shows ~+31%, but a formal interaction test cannot confirm a structural
  break (p=0.19) and the gradient sits within noise. **Use the full-sample figure** and
  note the uncertainty; do not quote the narrow-window number as fact.
- **Slicktop is worth nothing measurable** (−0.2%, p≈0.97). The v1 +14.8% was an artifact
  of a roof column that only recorded *advertised* slicktops. Once 781 cars were
  positively confirmed as having moonroofs, the premium vanished. v1 called that estimate
  a floor that would rise with better data — it was wrong in both size and direction.
- **ZCP verified from options is +19.8%**, versus +23% when inferred from the title. Title
  mentions overstate it; prefer `zcp_verified`.
- **The year index is the headline market number**, not a growth rate. Watch the current
  year's level against last year's. 2026 at 1.93 vs 2025 at 1.67 is a ~15% year-over-year
  step and the strongest reading in the series.
- **Thin categories.** Phoenix Yellow n=18, Mystic Blue n=13, Steel Grey n=22. If n<25,
  say so rather than quoting the coefficient as fact.
- **Every figure quoted in this file comes from `references/baseline.json`.** If a run
  disagrees with the prose here, trust the JSON — it is regenerated each month, this text
  is not.
- **The accident term is gone.** BaT renders its Carfax widget in client-side JS, so the
  column is uniformly "Not Mentioned" and carries no information. Do NOT read that as
  "no accidents reported" — it means unknown. The v1 −16.8% accident penalty is no
  longer estimable from this data.

## Reporting

Deliver a self-contained HTML report via `SendUserFile`, then persist it with
`create_artifact` so it accumulates month over month rather than being buried in chat.
Read the `dataviz` skill before building charts. Structure that works:

1. **Headline delta** — valuation now vs last month, in dollars and percent, one sentence
   on why (market drift? new comps? mileage?).
2. **What moved** — only coefficients that shifted ≥2 points. If nothing moved, say
   "nothing moved" and keep it short. A quiet month is a legitimate finding.
3. **New comps** — sales added since last run, especially Cinnamon, low-mileage, or
   Carbon Black cars. These are the ones that actually update the estimate.
4. **Valuation** — range first, point estimate second, scenarios (VANOS done, reserve
   vs no-reserve) third.
5. **Data quality** — flag anything from the `data_quality` block that got worse.

## Known data issues

The 2026-08-13 full re-scrape fixed all five v1 extraction bugs and extended coverage to
all 937 rows. Verified independently: the three known-bad colours now return real paint
names, snippets no longer cut mid-word (2 of 1,082 edge cases remain), and the
`transmission_conversion_note` false positives are gone.

What is still worth knowing:

- **Carfax fields are empty for all 937 rows** — a genuine source-access gap, not an
  extraction failure. Treat as unknown, never as "no accidents."
- **Mileage is now mostly rounded** (94% land on a round thousand, up from 87%) because
  exact Carfax odometer readings came from the same unavailable widget. Slightly coarser
  input to the model's most important variable.
- **39 rows have no mileage anywhere** and drop out of the fit.
- **109 sold cars have no interior colour**, carried as an explicit `Unknown` level rather
  than dropped — it prices about 9% below Black, which is a listing-quality signal, not a
  trim effect.
- **`Slicktop` = "No Mention"** still exists on 67 cars in the model set, held as its own
  control so that confirmed-moonroof cars form a clean baseline.
- One cosmetic README error: it describes the 200-row sheet as covering "Sep 2025 back to
  Aug 2026". It is actually May 2024 to Aug 2026. Harmless — use the full sheet anyway.
- Two rows show small sold_price revisions traced to BaT's own feed, not the scraper.
