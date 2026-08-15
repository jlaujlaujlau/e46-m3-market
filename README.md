# BMW E46 M3 — market analysis and valuation

A hedonic price model for the BMW E46 M3 coupe, built on every US Bring a Trailer
auction of the model (937 listings, 2014–2026), and a standing valuation of one car:
a 2004 Carbon Black Metallic / Cinnamon Nappa 6-speed with 27,000 miles.

**Current estimate: $58,445** · 68% likely hammer range **$47,800 – $71,400** ·
model v2, 13 August 2026.

## What drives E46 M3 prices

From an OLS regression on log sale price, n=651 non-modified sold coupes.
Every figure holds all other attributes constant.

| Factor | Effect | p |
|---|---:|---:|
| Laguna Seca Blue paint | +57.6% | <0.001 |
| 6-speed manual vs SMG | +26.6% | <0.001 |
| Competition Package (verified from options) | +19.8% | <0.001 |
| Interlagos Blue paint | +18.6% | <0.001 |
| Cinnamon Nappa interior | +16.7% | <0.001 |
| Alpine White paint | +16.3% | 0.007 |
| Imola Red paint | +14.3% | <0.001 |
| RACP / subframe work disclosed | +7.4% | <0.001 |
| VANOS work disclosed | +4.1% | 0.020 |
| Carbon Black paint | −1.5% | 0.647 |
| Slicktop (no moonroof) | −0.2% | 0.967 |
| Rod bearings disclosed | −1.9% | 0.306 |
| No-reserve auction | −5.1% | 0.011 |
| Doubling the mileage | −25.1% | <0.001 |

Mileage dominates everything else. Colour matters, but not the way forum consensus
suggests: Laguna Seca Blue is in a class of its own, while Carbon Black — widely
described as a premium colour — is statistically indistinguishable from Titanium Silver.

### The market

Quality-adjusted price index, 2017 = 100. Holding mileage, spec, colour and
condition constant:

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| 100 | 108 | 115 | 127 | 164 | 179 | 168 | 171 | 167 | **193** |

A sharp 2021–22 run, a three-year plateau, and a 2026 breakout — currently ~15%
above 2025 and the strongest reading in the series.

## Three findings that only appear once you control properly

**Preventive maintenance looks negative in raw medians.** Owners overwhelmingly do
rod bearings, subframe and VANOS work on high-mileage cars, so the unconditional
median for "work done" sits below "work not mentioned." Only the regression separates
the effect of the work from the effect of the miles.

**A disclosed rod-bearing job is not a discount.** It measures −1.9% (p=0.31) — no
reliable effect. The disclosure marks a harder-used car; it does not destroy value.

**The slicktop premium was a measurement artifact.** An earlier version of this model
put it at +14.8% and called that a floor. Once the dataset positively confirmed
moonroofs on 781 cars — rather than only flagging *advertised* slicktops against a
contaminated comparison group — the premium vanished to −0.2%. The v1 estimate was
wrong in both magnitude and direction of correction.

## Method

```
lnp ~ cr(lnm, df=4) + manual + zcp + C(color_grp) + C(int_grp)
      + racp_done + vanos_done + rb_done + no_res + C(yr) + slick + slick_unknown
```

Baselines: Titanium Silver paint, Black interior, moonroof confirmed present.
R² 0.807, 5-fold cross-validated median absolute error 12.6%. Coefficients confirmed
against a Huber robust re-fit with negligible movement. Modified, supercharged,
engine-swapped and track cars are excluded — they trade on different logic.

Two specification choices matter and are documented in `analysis/SKILL.md`:

- **Cubic spline in log-mileage.** A log-linear term overpredicted sub-25k cars by
  ~9% and underpredicted the 25–40k band by ~6%. The spline flattens residuals to
  under ±2% across every mileage bin.
- **Year fixed effects, not a constant trend.** The market was not a smooth
  compounding curve, and forcing one leaves systematic residuals. AIC improves by 65.

### Reading the numbers honestly

Cross-validated error is 12.6%, and single Bring a Trailer results on the *same
physical car* swing more than that — the dataset contains 44 relists, including a
47k-mile Competition Package that made $66,000 in May 2024 and $51,000 three months
later. **The range is the answer; the point estimate is not.**

## Repository layout

```
report/
  E46_M3_Valuation_v2.pdf     10-page report, sized 6×9in for phone reading
  E46_M3_Valuation_v2.html    same report, with interactive chart tooltips
analysis/
  analyze.py                  the full pipeline — load, clean, fit, value, diff
  baseline.json               model v2 coefficients and valuation, for month-over-month diffing
  SKILL.md                    model spec, interpretation guidance, known data issues
  car.md                      subject-car provenance, options, mechanical status
  E46_scraper_prompt.md       the data-collection spec, including five extraction-bug fixes
```

## Reproducing

Requires the source spreadsheet (`E46_M3_BaT_Sold_Listings.xlsx`, not included —
it republishes scraped Bring a Trailer listing data).

```bash
pip install pandas numpy statsmodels openpyxl
python3 analysis/analyze.py E46_M3_BaT_Sold_Listings.xlsx \
    --asof 2026-08-13 --mileage 27000 --baseline analysis/baseline.json
```

On the 13 August 2026 data this reproduces exactly: n=651, R²=0.807, point estimate
$58,445. Any deviation on unchanged data means the script or the data changed.

## Data caveats

- **Carfax fields are empty on all 937 rows.** Bring a Trailer renders that widget in
  client-side JavaScript, so a bulk scrape cannot see it. Blanks mean *unknown*, never
  "no accidents reported." An accident term was estimable in v1 (−16.8%) and is not
  estimable now.
- **Mileage is mostly rounded** — 94% of values land on a round thousand, since exact
  odometer readings came from the same unavailable widget.
- **Mechanical-work fields are seller free text**, not verified checkboxes. "Not
  mentioned" does not mean not done. Treat them as weak signals.
- **Thin categories.** Phoenix Yellow n=18, Mystic Blue n=13, Steel Grey n=22.
  Coefficients on these are indicative, not firm.
