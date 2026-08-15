#!/usr/bin/env python3
"""
E46 M3 market model — reproducible monthly pipeline.  v2 (2026-08-13)

Usage:
    python3 analyze.py <path-to-xlsx> [--baseline references/baseline.json]
                       [--asof YYYY-MM-DD] [--mileage N]

v2 changes, after the full 937-row re-scrape:
  * reads the "All Listings" sheet, NOT the 200-row convenience view
  * cubic spline in log-mileage (log-linear misfit the tails by up to 9%)
  * year fixed effects instead of a single exponential trend (AIC -65)
  * uses zcp_verified / transmission_type / Slicktop NO-YES where present
  * drops the accident term — BaT's Carfax widget is client-side JS and
    is no longer scrapable, so the column is uniformly "Not Mentioned"
"""
import sys, json, argparse, warnings
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

SUBJECT = dict(
    label="2004 M3 Coupe — Carbon Black / Cinnamon 6MT",
    vin="WBSBL934X4PN58673",
    mileage=27000, mileage_asof="2026-08-12",
    manual=1, zcp=0, slick=0, slick_unknown=0, no_res=0,
    color_grp="Carbon Black", int_grp="Cinnamon",
    rb_done=0, racp_done=0, vanos_done=0,
)

CTRL = (' + manual + zcp + C(color_grp, Treatment("Titanium Silver"))'
        ' + C(int_grp, Treatment("Black"))'
        ' + racp_done + vanos_done + rb_done + no_res + C(yr) + slick + slick_unknown')
MODEL = 'lnp ~ cr(lnm, df=4)' + CTRL

MODIFIED_RE = r"Modified|Supercharged|Turbo|Widebody|Track|Race|CSL-Style|\bLS\d?\b"
COLOR_MAP = [
    ("laguna", "Laguna Seca Blue"), ("phoenix", "Phoenix Yellow"),
    ("imola", "Imola Red"), ("japan red", "Imola Red"),
    ("interlagos", "Interlagos Blue"), ("carbon black", "Carbon Black"),
    ("titanium silver", "Titanium Silver"), ("silver gr", "Silver Grey"),
    ("steel gr", "Steel Grey"), ("metallic gray", "Steel Grey"),
    ("jet black", "Jet Black"), ("alpine", "Alpine White"),
    ("mystic", "Mystic Blue"), ("topaz", "Other Blue"),
    ("midnight", "Other Blue"), ("estoril", "Other Blue"),
]
# guard against the old wrong-bullet bug; harmless once the scraper is clean.
# NOTE: matched only when no real paint name is present, so values like
# "Imola Red II w/Vinyl Graphics" still classify correctly.
NON_COLOR = ("diffuser", "graphics", "block-off", "spoiler", "plastidip",
             "sunroof panel", "front seats")


def _s(x) -> str:
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x).lower()


def color_group(s) -> str:
    s = _s(s)
    for k, v in COLOR_MAP:          # real paint name wins over the junk guard
        if k in s:
            return v
    if any(k in s for k in NON_COLOR):
        return "Other/Unknown"
    if s.strip() == "black":
        return "Jet Black"
    return "Other/Unknown"


def interior_group(s) -> str:
    s = _s(s)
    if "cinnamon" in s: return "Cinnamon"
    if "imola" in s:    return "Imola Red"
    if "grey" in s or "gray" in s: return "Grey"
    if "black" in s:    return "Black"
    if not s.strip():   return "Unknown"
    return "Other"


def load(path):
    """Prefer the full sheet. The 200-row view is a subset kept for continuity."""
    xl = pd.ExcelFile(path)
    full = next((s for s in xl.sheet_names if "All Listings" in s), None)
    if full is None:
        full = next(s for s in xl.sheet_names if "Detailed" in s)
        print(f"WARNING: no 'All Listings' sheet; falling back to {full!r}", file=sys.stderr)
    return xl.parse(full), xl


def prepare(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    t = d["title"].fillna("")
    d["modified"] = t.str.contains(MODIFIED_RE, case=False, regex=True).astype(int)

    if "zcp_verified" in d.columns:
        d["zcp"] = (d["zcp_verified"].astype(str).str.upper() == "TRUE").astype(int)
    else:
        d["zcp"] = t.str.contains("Competition|ZCP", case=False).astype(int)

    sl = d["Slicktop"].astype(str).str.upper() if "Slicktop" in d.columns else pd.Series("", index=d.index)
    d["slick"] = (sl == "YES").astype(int)
    # roof genuinely unknown — kept as its own control so "NO" is a clean baseline
    d["slick_unknown"] = sl.isin(["NO MENTION", "AFTERMARKET"]).astype(int)

    d["date"] = pd.to_datetime(d["sold_date"], errors="coerce")
    d["yr"] = d["date"].dt.year

    if "transmission_type" in d.columns:
        d["manual"] = (d["transmission_type"].astype(str).str.strip().str.lower() == "manual").astype(int)
    else:
        ct = d["current_transmission"].fillna("").str.replace("‑", "-", regex=False)
        d["manual"] = (ct.str.contains("Manual|Gearbox", case=False)
                       & ~ct.str.contains("SMG", case=False)).astype(int)

    d["color_grp"] = d.get("exterior_color", pd.Series(dtype=str)).map(color_group)
    d["int_grp"] = d.get("interior_color", pd.Series(dtype=str)).map(interior_group)
    for col, name in [("rod_bearing_flag", "rb"), ("racp_subframe_flag", "racp"),
                      ("vanos_flag", "vanos")]:
        d[name + "_done"] = (d.get(col) == "Mentioned - Appears Done").astype(int)
    d["no_res"] = d["no_reserve"].astype(bool).astype(int)
    return d


def fit(d):
    m = d[(d.modified == 0) & (d.status == "Sold")
          & d.sold_price.notna() & d.mileage.notna()].copy()
    m["lnp"] = np.log(m.sold_price)
    m["lnm"] = np.log(m.mileage.clip(lower=1000))
    # thin year cells break the fixed effects; fold pre-2017 into 2017
    m.loc[m.yr < 2017, "yr"] = 2017
    return smf.ols(MODEL, data=m).fit(), m


def value_subject(res, m, mileage=None, year=None):
    yr = year or int(m.yr.max())
    row = pd.DataFrame([dict(
        lnm=np.log(mileage or SUBJECT["mileage"]), yr=yr,
        **{k: SUBJECT[k] for k in ("manual", "zcp", "slick", "slick_unknown",
                                   "color_grp", "int_grp", "racp_done",
                                   "vanos_done", "rb_done", "no_res")})])
    out = {}
    for alpha, lab in [(0.32, "p68"), (0.20, "p80")]:
        f = res.get_prediction(row).summary_frame(alpha=alpha)
        out[lab] = [float(np.exp(f["obs_ci_lower"][0])), float(np.exp(f["obs_ci_upper"][0]))]
    out["point"] = float(np.exp(res.get_prediction(row).summary_frame()["mean"][0]))
    for lab, kw in [("with_vanos", dict(vanos_done=1)),
                    ("with_vanos_racp", dict(vanos_done=1, racp_done=1)),
                    ("no_reserve", dict(no_res=1))]:
        r2 = row.copy()
        for k, v in kw.items():
            r2[k] = v
        out[lab] = float(np.exp(res.get_prediction(r2).summary_frame()["mean"][0]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--baseline")
    ap.add_argument("--asof", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--mileage", type=float, default=None)
    a = ap.parse_args()

    raw, xl = load(a.xlsx)
    d = prepare(raw)
    res, m = fit(d)
    val = value_subject(res, m, a.mileage)

    coefs = {k: round((np.exp(v) - 1) * 100, 1) for k, v in res.params.items()
             if k != "Intercept" and not k.startswith("cr(")}
    yi = {k[-5:-1]: round(float(np.exp(v)), 3) for k, v in res.params.items() if k.startswith("C(yr)")}

    sold = raw[raw.status.isin(["Sold", "RNM"])].copy()
    sold["y"] = pd.to_datetime(sold.sold_date, errors="coerce").dt.year
    health = (sold.assign(s=(sold.status == "Sold").astype(int))
              .groupby("y").agg(n=("s", "size"), sell_through=("s", "mean"))
              .round(3).tail(4).to_dict("index"))

    out = dict(
        run_date=a.asof, source=a.xlsx, model_version=2,
        n_model=int(res.nobs), r2=round(float(res.rsquared), 3),
        resid_sd=round(float(np.std(res.resid, ddof=1)), 3),
        rows_all=int(len(raw)),
        coefficients_pct=coefs,
        pvalues={k: round(float(p), 4) for k, p in res.pvalues.items() if not k.startswith("cr(")},
        year_index=yi,
        subject=dict(SUBJECT, mileage=a.mileage or SUBJECT["mileage"]),
        valuation=val,
        market_health={str(k): v for k, v in health.items()},
        data_quality=dict(
            unknown_color=int(m.color_grp.eq("Other/Unknown").sum()),
            unknown_interior=int(m.int_grp.eq("Unknown").sum()),
            blank_mileage=int(raw.mileage.isna().sum()),
            modified_excluded=int(d.modified.sum()),
            carfax_populated=int(raw.get("carfax_snapshot_raw", pd.Series(dtype=object)).notna().sum()),
            roof_unknown=int(m.slick_unknown.sum()),
        ),
    )

    if a.baseline:
        try:
            b = json.load(open(a.baseline))
            out["vs_baseline"] = dict(
                baseline_date=b.get("run_date"),
                baseline_model_version=b.get("model_version", 1),
                point_change=round(val["point"] - b["valuation"]["point"]),
                point_change_pct=round((val["point"] / b["valuation"]["point"] - 1) * 100, 1),
                n_change=int(res.nobs) - b.get("n_model", 0),
                coef_moves={k: round(coefs[k] - b["coefficients_pct"][k], 1)
                            for k in coefs if k in b.get("coefficients_pct", {})
                            and abs(coefs[k] - b["coefficients_pct"][k]) >= 2.0},
            )
            if b.get("model_version", 1) != 2:
                out["vs_baseline"]["WARNING"] = (
                    "Baseline used model v1 (log-linear mileage, linear trend, n=177). "
                    "Differences are partly a model change, not a market move — say so.")
        except Exception as e:
            out["vs_baseline"] = {"error": str(e)}

    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
