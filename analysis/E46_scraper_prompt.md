# Scraper task: fix field-extraction bugs and extend detail coverage to all 937 listings

## Context

You are updating `E46_M3_BaT_Sold_Listings.xlsx` — a dataset of every BMW E46 M3 **coupe** auction on
Bring a Trailer (US location, convertibles and parts-only listings excluded). The file has three sheets:

- `README` — provenance and caveats
- `All Listings (937)` — every auction; only title/price/date/status fields are populated
- `Detailed Sample (200)` — the 200 most recent **sold** listings, with per-listing-page fields

The dataset feeds a hedonic regression that estimates what drives E46 M3 sale prices. Field accuracy
matters more than coverage speed: one wrong value in a categorical column silently biases a coefficient.

There are two jobs. **Do Part A before Part B** — do not scale up an extractor that is still wrong.

---

## PART A — Fix five extraction bugs

### Bug 1 (confirmed): `exterior_color` and `interior_color` grab the wrong equipment-list bullet

BaT listing pages carry a bulleted equipment list. The current extractor appears to take a positional
bullet rather than matching on meaning, so on listings where modification bullets are listed first it
returns a part name instead of a colour.

Confirmed failures — use these as regression tests:

| URL | Currently returns | Should return |
|---|---|---|
| `bringatrailer.com/listing/2004-bmw-m3-coupe-243/` | `Carbon-Fiber Rear Diffuser` | the actual paint colour |
| `bringatrailer.com/listing/2004-bmw-m3-coupe-214-2/` | `Tri-Color Graphics` | the actual paint colour |
| `bringatrailer.com/listing/2004-bmw-m3-coupe-201/` | `Carbon-Fiber Sunroof Block-Off Panel` | the actual paint colour |

The same three rows have suspect `interior_color` values (`Cloth-Trimmed Sparco Front Seats`,
`Single Recaro Black Cloth Driver's Seat`) — those may be *correct* for a stripped track car, but
verify rather than assume.

Also blank on four listings, all of which do state a colour somewhere on the page:
`2001-bmw-m3-coupe-37`, `2001-bmw-m3-coupe-38`, `2002-bmw-m3-coupe-100`, `2006-bmw-m3-coupe-163`.

**Required fix.** Extract colour by *semantics*, not bullet position:

1. Prefer BaT's structured "Listing Details" / essentials block if the page exposes one.
2. Otherwise match the equipment bullet against a known BMW E46 paint vocabulary: Alpine White,
   Titanium Silver, Steel Grey/Gray, Silver Grey/Gray, Jet Black, Carbon Black, Imola Red, Laguna Seca
   Blue, Interlagos Blue, Phoenix Yellow, Mystic Blue, Topaz Blue, Estoril Blue, Midnight Blue, Oxford
   Green, Sterling Grey, plus the Individual programme colours.
3. If the car is repainted, keep the descriptive string as-is (`Refinished in British Racing Green` is
   a *correct* value, not an error) but set the new `color_is_factory` flag to `FALSE`.
4. If no colour can be determined, write `Unknown` — **never** write a non-colour string.

Add these two columns:

- `exterior_color_raw` — the verbatim source string
- `color_is_factory` — `TRUE` / `FALSE` / `Unknown`

### Bug 2 (confirmed): `transmission_conversion_note` fires on any occurrence of "convert"

It currently matches unrelated text. Real examples now in the file:

- `...ourtesy lights have been converted to LED units...` (interior lighting)
- `...features a wheel stud conversion, Koni dampers...` (wheel studs — appears 3+ times)
- `...fitted with a wet-sump conversion along with a Tremec T56...` (oil system)

**Required fix.** Only populate this field when the conversion refers to the **transmission**. Require
the match to be in a sentence that also contains a gearbox term (`transmission`, `gearbox`, `SMG`,
`manual`, `six-speed`, `6-speed`). Explicitly exclude matches whose nearest noun is `stud`, `LED`,
`light`, `wet-sump`, `sump`, `brake`, `bushing`, or `suspension`.

Add a companion column `transmission_converted` with values `SMG to Manual` / `Manual to SMG` /
`Other` / `No`, so the analysis can use a clean categorical instead of parsing free text.

### Bug 3 (confirmed): all `*_snippet` fields are cut mid-word

Snippets are fixed-width character slices. Current values begin and end mid-token, e.g.
`ved replacing all 12 S54 rod bearing shells in addition to the rod bolts, double-VANOS system g`.

**Required fix.** Expand each snippet to **complete sentence boundaries** — from the start of the
sentence containing the match to the end of that sentence, plus one sentence either side for context.
Cap at ~500 characters at a sentence boundary rather than mid-word. Applies to `rod_bearing_snippet`,
`racp_subframe_snippet`, `vanos_snippet`, and any new snippet columns.

### Bug 4 (design flaw): `Slicktop` has no way to say "moonroof confirmed present"

The README already concedes this: `No Mention` is an unknown bucket, and `NO` never occurs. That
forces every analysis to treat "definitely has a sunroof" and "roof status unknown" as the same thing,
which biases the slicktop coefficient toward zero.

**Required fix.** Populate `NO` positively when the listing gives affirmative evidence of a
moonroof — the description mentions a sunroof/moonroof as present, the equipment list includes
`Glass Electric Sunroof` or option code `0402`, a window sticker or BMW build sheet is shown, or the
photos clearly show a moonroof panel. Final vocabulary:

- `YES` — factory no-cost sunroof delete (BaT "Slicktop")
- `NO` — moonroof affirmatively confirmed present
- `Aftermarket` — factory moonroof later blocked off or removed
- `No Mention` — genuinely indeterminate

Add `slicktop_evidence` naming what the call was based on (`title`, `description`, `option code 0402`,
`window sticker`, `photos`, `none`).

### Bug 5 (consistency): `current_transmission` vocabulary is not normalized

Twelve distinct strings describe what are really two transmissions — `Six-Speed` vs `6-Speed`,
`Transmission` vs `Gearbox`, and at least one entry using a Unicode non-breaking hyphen
(`Six‑Speed SMG Sequential Transmission`), which will not match a plain-hyphen string comparison.

**Required fix.** Keep the verbatim string in `current_transmission_raw` and add a normalized
`transmission_type` with exactly three values: `Manual`, `SMG`, `Other`. Normalize all Unicode
dashes/hyphens to ASCII before matching.

---

## PART B — Extend detail coverage from 200 to all 937 listings

Detail fields currently exist only for the 200 most recent sold listings (Aug 2026 back to May 2024).
Scrape the same per-listing-page fields for the remaining ~737 rows so every row in
`All Listings (937)` carries the full schema.

**Include RNM (reserve-not-met) and Unknown-status listings**, not just sold ones. They have no sale
price, but their specs are still informative about what fails to sell and at what bid level — capture
`high_bid` for them (see below).

Fields to populate for every row (same definitions and vocabularies as the existing sheet, plus the
Part A additions): `mileage`, `mileage_source`, `exterior_color`, `exterior_color_raw`,
`color_is_factory`, `interior_color`, `current_transmission_raw`, `transmission_type`,
`transmission_converted`, `transmission_conversion_note`, `Slicktop`, `slicktop_evidence`,
`carfax_accidents_flag`, `carfax_accidents_detail`, `carfax_previous_owners`,
`carfax_service_records`, `carfax_snapshot_raw`, `rod_bearing_flag`, `rod_bearing_snippet`,
`racp_subframe_flag`, `racp_subframe_snippet`, `vanos_flag`, `vanos_snippet`.

Add four low-cost columns available on the same page you are already loading:

- `high_bid` — final bid amount, populated for **all** listings including RNM
- `zcp_verified` — `TRUE` / `FALSE` / `Unknown`. Competition Package confirmed from the description,
  option list, or window sticker rather than inferred from the title. The title is currently the only
  source and it is not always accurate.
- `is_relist` — `TRUE` where the URL slug carries a `-2` / `-3` suffix indicating the same car
  returning to auction (20 such URLs already present, e.g. `2004-bmw-m3-coupe-214-2`)
- `relist_of` — the base listing URL when `is_relist` is `TRUE`, so repeat sales of one car can be
  linked

### Preserve existing behaviour

- Keep all current column names and their existing value vocabularies unchanged — downstream analysis
  depends on exact strings like `Mentioned - Appears Done`, `Confirmed No Accidents (Carfax)`,
  `Listing Essentials`, `Carfax Odometer`.
- Keep the `*_flag` / `*_snippet` / `*_raw` split. Flags stay a first-pass heuristic; raw text stays
  available for reclassification.
- Do **not** drop or reorder existing columns. Append new ones at the end.
- Keep `id` and `url` stable so the new file can be diffed against the current one.

### Re-verify, do not assume

The 200 existing detailed rows should be **re-scraped**, not carried over — Bugs 1–5 affect them too,
and the whole point is one consistently-extracted dataset rather than two vintages of extraction logic
in one file.

---

## Output and QA

Write `E46_M3_BaT_Sold_Listings.xlsx` with the same three sheets. Update the `README` sheet to record
the new pull date, the schema additions, and the corrected caveats — in particular, the existing
Slicktop caveat about `NO` never occurring is now obsolete and must be rewritten.

Before delivering, run and report these checks:

1. **No non-colour strings in `exterior_color`.** Every value is a recognised paint name, a repaint
   description, or `Unknown`. Confirm the three known-bad URLs above now return real colours.
2. **Coverage.** Report populated counts per column out of 937. Flag any column below 80% and say why
   (genuine source gap vs extraction failure) — e.g. the Carfax snapshot widget is legitimately absent
   from most listings and was populated on only 32 rows before.
3. **`transmission_conversion_note` precision.** Report how many rows are populated and spot-check 10.
   Zero should be about wheel studs, LEDs, or sumps.
4. **Snippet integrity.** Confirm no snippet begins or ends mid-word.
5. **Vocabulary drift.** List every distinct value in each categorical column and confirm it matches
   the documented vocabulary. Flag anything new.
6. **Sanity vs the old file.** For the 200 rows that already had detail, diff old vs new and report
   every changed cell. Large numbers of changes in `mileage` or `sold_price` mean something regressed —
   those fields were not part of this task and should be near-identical.
