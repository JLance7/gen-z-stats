from pathlib import Path
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from genz.metrics import monthly_payment, ownership_cost, real_dollars, rebase, cohort_description
from genz.pipeline import DEFAULT_DATA, annualize, clean_fred, load_snapshot, parse_year, run_pipeline
from genz.sources import SOURCE_BY_KEY


def test_mortgage_and_cost_components():
    assert monthly_payment(240_000, 6, 30) == pytest.approx(1438.92, abs=.01)
    assert monthly_payment(120_000, 0, 30) == pytest.approx(333.3333)
    assert monthly_payment(0, 6) == 0
    assert ownership_cost(300_000, 6, down_percent=20)["PMI"] == 0
    assert ownership_cost(300_000, 6, down_percent=10)["PMI"] > 0
    with pytest.raises(ValueError):
        monthly_payment(-1, 6)


def test_inflation_and_rebasing():
    assert real_dollars(100, 100, 250) == 250
    frame = pd.DataFrame({"year": [2000, 2001], "price": [50, 75]})
    assert rebase(frame, ["price"], 2000).price.tolist() == [100, 150]
    with pytest.raises(ValueError):
        rebase(frame, ["price"], 1990)


def test_cleaning_missing_and_duplicate_dates():
    cleaned, report = clean_fred(b"observation_date,X\n2000-01-01,1\n2000-02-01,.\n2000-03-01,2\n", "example")
    assert len(cleaned) == 2 and report["missing_rows_removed"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        clean_fred(b"observation_date,X\n2000-01-01,1\n2000-01-01,2\n", "example")


def test_incomplete_year_is_not_published():
    frame = pd.DataFrame({"series": ["cpi"] * 13,
                          "date": pd.date_range("2020-01-01", periods=13, freq="MS"), "value": [100.] * 13})
    annual, excluded = annualize(frame, SOURCE_BY_KEY["cpi"], 2025)
    assert annual.index.tolist() == [2020]
    assert excluded[0]["year"] == 2021


def test_year_revisions_and_cohort_labels():
    assert parse_year("2021r") == 2021
    assert parse_year(2023.0) == 2023
    assert parse_year("1 Beginning in 2021...") is None
    assert "Gen Z" in cohort_description(2023, "18-24")
    assert "Millennials / Gen Z" in cohort_description(2023, "25-34")


def test_real_snapshot_integrity_and_weighting():
    snapshot = load_snapshot()
    assert len(snapshot["annual"]) >= 20
    assert snapshot["annual"].notna().all().all()
    living = snapshot["living"]
    subset = living.loc[(living.year == living.year.max()) & (living.age_group == "18-24")]
    sexes = subset.loc[subset.sex.isin(["Men", "Women"])]
    expected = (sexes.living_with_spouse_pct * sexes.population_thousands).sum() / sexes.population_thousands.sum()
    assert subset.loc[subset.sex == "All (weighted)", "living_with_spouse_pct"].iloc[0] == pytest.approx(expected)
    assert not living.duplicated(["year", "age_group", "sex"]).any()


def test_corrupt_artifact_is_rejected(tmp_path):
    import shutil
    processed = DEFAULT_DATA / "processed"
    run_id = json.loads((processed / "current.json").read_text())["run_id"]
    shutil.copytree(processed / "runs" / run_id, tmp_path / "processed" / "runs" / run_id)
    (tmp_path / "processed" / "current.json").write_text(json.dumps({"run_id": run_id}))
    annual = tmp_path / "processed" / "runs" / run_id / "annual.csv"
    annual.write_text("corrupted")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_snapshot(tmp_path)


def test_failed_build_does_not_publish(tmp_path):
    with pytest.raises(RuntimeError, match="no verified cache"):
        run_pipeline(tmp_path, offline=True)
    assert not (tmp_path / "processed" / "current.json").exists()


def test_dashboard_and_interactions():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45).run()
    assert not app.exception
    assert len(app.tabs) == 5
    # Exercise scenario edge case and a genuinely different age-group comparison.
    app.slider[0].set_value(0)
    age_select = next(element for element in app.selectbox if element.label == "Keep the age group fixed")
    age_select.set_value("25-34")
    app.run()
    assert not app.exception
