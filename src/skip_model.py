"""Step 4: a logistic regression for question 1 (what predicts a skip?).

Rate tables (sql/01_skips.sql) show each factor alone. This model separates them,
because factors overlap (for example, shuffle is used more on the phone).

Outputs three tables in the database:
  m_skip_model       odds ratios with 95% intervals (fit on all eligible streams)
  m_skip_ablation    how much out-of-time AUC drops when one factor group is removed
  m_skip_model_meta  sample sizes, base rate and the full-model AUC
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import rankdata

from src.db import connect

warnings.filterwarnings("ignore")

GROUPS = {
    "time of day": "C(daypart, Treatment('evening'))",
    "weekend": "is_weekend",
    "platform": "C(platform_grp, Treatment('{ref_platform}'))",
    "shuffle": "shuffle",
    "how it started": "C(reason_start_grp, Treatment('trackdone'))",
    "familiarity": "new_track + log_prior",
}


def auc(y: np.ndarray, score: np.ndarray) -> float:
    ranks = rankdata(score)
    pos = y == 1
    n_pos, n_neg = pos.sum(), (~pos).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def load() -> pd.DataFrame:
    con = connect(read_only=True)
    df = con.execute(
        """
        SELECT start_ts, hour_local, is_weekend, platform_family, shuffle,
               reason_start, prior_plays, CAST(is_skip AS INT) AS y
        FROM m_skips
        WHERE eligible
        ORDER BY start_ts
        """
    ).df()
    con.close()

    df["daypart"] = pd.cut(
        df["hour_local"], bins=[-1, 5, 11, 17, 23],
        labels=["night", "morning", "afternoon", "evening"],
    ).astype(str)
    share = df["platform_family"].value_counts(normalize=True)
    keep = share[share >= 0.01].index
    df["platform_grp"] = np.where(df["platform_family"].isin(keep), df["platform_family"], "other")
    df["reason_start_grp"] = np.where(
        df["reason_start"].isin(["trackdone", "fwdbtn", "clickrow"]), df["reason_start"], "other"
    )
    df["shuffle"] = df["shuffle"].astype(int)
    df["is_weekend"] = df["is_weekend"].astype(int)
    df["new_track"] = (df["prior_plays"] == 0).astype(int)
    df["log_prior"] = np.log1p(df["prior_plays"])
    return df


def formula_for(groups: list[str], ref_platform: str) -> str:
    terms = [GROUPS[g].replace("{ref_platform}", ref_platform) for g in groups]
    return "y ~ " + " + ".join(terms)


def fit(formula: str, data: pd.DataFrame):
    model = smf.logit(formula, data=data)
    try:
        return model.fit(disp=False, maxiter=200)
    except Exception:
        return model.fit(disp=False, maxiter=500, method="bfgs")


def holdout_auc(formula: str, train: pd.DataFrame, test: pd.DataFrame) -> float:
    res = fit(formula, train)
    for col in ["daypart", "platform_grp", "reason_start_grp"]:
        test = test[test[col].isin(train[col].unique())]
    return auc(test["y"].to_numpy(), np.asarray(res.predict(test)))


def run() -> None:
    df = load()
    if len(df) < 500 or df["y"].nunique() < 2:
        print("Not enough eligible streams or no variation in skips; skipping the model.")
        return

    ref_platform = df["platform_grp"].value_counts().index[0]
    all_groups = list(GROUPS)
    full_formula = formula_for(all_groups, ref_platform)

    # 1) coefficients on all data
    res = fit(full_formula, df)
    conf = res.conf_int()
    coefs = pd.DataFrame({
        "term": res.params.index,
        "odds_ratio": np.exp(res.params.values),
        "ci_low": np.exp(conf[0].values),
        "ci_high": np.exp(conf[1].values),
        "p_value": res.pvalues.values,
    })
    coefs = coefs[coefs["term"] != "Intercept"].reset_index(drop=True)
    coefs["term"] = (
        coefs["term"]
        .str.replace(r"C\(daypart, Treatment\('evening'\)\)\[T\.(\w+)\]", r"daypart: \1 vs evening", regex=True)
        .str.replace(r"C\(platform_grp, Treatment\('(\w+)'\)\)\[T\.(\w+)\]", r"platform: \2 vs \1", regex=True)
        .str.replace(r"C\(reason_start_grp, Treatment\('trackdone'\)\)\[T\.(\w+)\]", r"started by: \1 vs trackdone", regex=True)
        .str.replace("new_track", "first listen of the track")
        .str.replace("log_prior", "log(1 + earlier plays of the track)")
        .str.replace("is_weekend", "weekend")
    )

    # 2) out-of-time evaluation: train on the first 80%, test on the last 20%
    cut = int(len(df) * 0.8)
    train, test = df.iloc[:cut], df.iloc[cut:]
    auc_full = holdout_auc(full_formula, train, test)

    ablation = []
    for group in all_groups:
        rest = [g for g in all_groups if g != group]
        auc_without = holdout_auc(formula_for(rest, ref_platform), train, test)
        ablation.append({
            "feature_group": group,
            "auc_without": auc_without,
            "auc_drop": auc_full - auc_without,
        })
    ablation = pd.DataFrame(ablation).sort_values("auc_drop", ascending=False)

    meta = pd.DataFrame([{
        "n_streams": len(df),
        "n_train": len(train),
        "n_test": len(test),
        "base_rate": float(df["y"].mean()),
        "auc_full_holdout": auc_full,
        "reference_platform": ref_platform,
        "pseudo_r2": float(res.prsquared),
    }])

    con = connect()
    for name, frame in [("m_skip_model", coefs), ("m_skip_ablation", ablation), ("m_skip_model_meta", meta)]:
        con.register("tmp_df", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    con.close()

    print(f"Skip model: n={len(df):,}, base rate={df['y'].mean():.1%}, "
          f"out-of-time AUC={auc_full:.3f}")
    print(ablation.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    run()
