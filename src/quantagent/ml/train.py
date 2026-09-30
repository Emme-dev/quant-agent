"""Walk-forward training. NEVER use a random train/test split on this data --
random splits let the model train on rows from after the test dates, which
silently leaks the future and makes a backtest look far better than it is.

Walk-forward instead: pick a cutoff date, train only on rows strictly before
it, test only on rows in a window strictly after it, then roll the cutoff
forward and repeat. tests/test_train.py checks the "strictly before/after"
property directly on dates, independent of lightgbm, so it stays fast to run.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Fold:
    train_idx: np.ndarray
    test_idx: np.ndarray
    train_end_date: pd.Timestamp
    test_start_date: pd.Timestamp
    test_end_date: pd.Timestamp


def walk_forward_splits(dates: pd.Series, n_splits: int = 5,
                        min_train_days: int = 180, test_days: int = 30,
                        step_days: int | None = None) -> list[Fold]:
    """dates: the 'date' column of the training table (may repeat per symbol).
    Splits are computed on the sorted UNIQUE dates, then mapped back to row
    indices, so every symbol's rows for a given date land in the same fold
    side (never train for one symbol, test for another, on the same date)."""
    step_days = step_days or test_days
    uniq = pd.Series(pd.to_datetime(dates.unique())).sort_values().reset_index(drop=True)
    if len(uniq) < min_train_days + test_days:
        raise ValueError(
            f"Not enough distinct dates ({len(uniq)}) for min_train_days="
            f"{min_train_days} + test_days={test_days}. Backfill more history."
        )

    folds = []
    train_end_pos = min_train_days
    while len(folds) < n_splits:
        test_start_pos = train_end_pos
        test_end_pos = test_start_pos + test_days
        if test_end_pos > len(uniq):
            break
        train_end_date = uniq.iloc[train_end_pos - 1]
        test_start_date = uniq.iloc[test_start_pos]
        test_end_date = uniq.iloc[test_end_pos - 1]

        # Strict inequalities are the leakage guard: a row dated exactly on
        # train_end_date's boundary can never land in both sets.
        train_idx = np.where(pd.to_datetime(dates) <= train_end_date)[0]
        test_idx = np.where(
            (pd.to_datetime(dates) > train_end_date)
            & (pd.to_datetime(dates) <= test_end_date)
        )[0]

        folds.append(Fold(train_idx, test_idx, train_end_date, test_start_date, test_end_date))
        train_end_pos += step_days

    return folds


def _fit_lgbm(X_train, y_train, X_val=None, y_val=None):
    import lightgbm as lgb
    params = dict(
        objective="regression",
        metric="l2",
        num_leaves=31,
        learning_rate=0.05,
        min_data_in_leaf=50,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=1,
        verbosity=-1,
    )
    train_set = lgb.Dataset(X_train, label=y_train)
    valid_sets, callbacks = [train_set], []
    if X_val is not None:
        valid_sets.append(lgb.Dataset(X_val, label=y_val, reference=train_set))
        callbacks.append(lgb.early_stopping(30, verbose=False))
    model = lgb.train(params, train_set, num_boost_round=500,
                       valid_sets=valid_sets if X_val is not None else None,
                       callbacks=callbacks or None)
    return model


def evaluate_fold(model, X_test, y_test) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    pred = model.predict(X_test)
    direction_acc = float(np.mean(np.sign(pred) == np.sign(y_test)))
    return {
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
        "direction_accuracy": direction_acc,
        "n_test": int(len(y_test)),
    }


def train_walk_forward(table: pd.DataFrame, feature_columns: list[str],
                       target_col: str, n_splits: int = 5,
                       min_train_days: int = 180, test_days: int = 30) -> dict:
    """Returns {"folds": [metrics...], "final_model": <trained on ALL data>,
    "feature_columns": [...]}. final_model is what gets deployed for tomorrow's
    prediction -- it's allowed to use every row, since by then every row IS
    the past relative to tomorrow."""
    folds = walk_forward_splits(table["date"], n_splits, min_train_days, test_days)
    fold_metrics = []
    for f in folds:
        tr, te = table.iloc[f.train_idx], table.iloc[f.test_idx]
        model = _fit_lgbm(tr[feature_columns], tr[target_col])
        m = evaluate_fold(model, te[feature_columns], te[target_col])
        m["train_end_date"] = str(f.train_end_date.date())
        m["test_start_date"] = str(f.test_start_date.date())
        m["test_end_date"] = str(f.test_end_date.date())
        fold_metrics.append(m)

    final_model = _fit_lgbm(table[feature_columns], table[target_col])
    return {"folds": fold_metrics, "final_model": final_model, "feature_columns": feature_columns}


def collect_oos_predictions(table: pd.DataFrame, feature_columns: list[str],
                            target_col: str, n_splits: int = 5,
                            min_train_days: int = 180, test_days: int = 30) -> pd.DataFrame:
    """For the BACKTEST, never the in-sample final_model. Trains one model per
    fold (same as train_walk_forward) and scores only that fold's held-out
    test rows, then concatenates all folds' test predictions into one
    out-of-sample table. Every row's score comes from a model that never saw
    that row, or any row dated after it, during training."""
    folds = walk_forward_splits(table["date"], n_splits, min_train_days, test_days)
    oos_frames = []
    for f in folds:
        tr, te = table.iloc[f.train_idx], table.iloc[f.test_idx]
        if te.empty:
            continue
        model = _fit_lgbm(tr[feature_columns], tr[target_col])
        te = te.copy()
        te["score"] = model.predict(te[feature_columns])
        oos_frames.append(te[["date", "symbol", "score", target_col]])
    if not oos_frames:
        return pd.DataFrame(columns=["date", "symbol", "score", target_col])
    return pd.concat(oos_frames, ignore_index=True)
