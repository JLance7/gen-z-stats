"""Pure calculation functions shared by charts and tests. No network or UI code."""
import pandas as pd


def monthly_payment(principal: float, annual_rate_percent: float, years: int = 30) -> float:
    """Fixed-rate amortization; explicitly handle the zero-interest case."""
    if principal < 0 or annual_rate_percent < 0 or years <= 0:
        raise ValueError("Principal/rate must be nonnegative and term must be positive.")
    months = years * 12
    rate = annual_rate_percent / 1200
    if rate == 0:
        return principal / months
    return principal * rate / (1 - (1 + rate) ** -months)


def ownership_cost(price, rate, down_percent=20, years=30, tax_percent=1.1,
                   insurance_percent=.5, maintenance_percent=1.0, pmi_percent=.5):
    """A scenario, not observed total owner costs. All recurring inputs are annual percentages."""
    if not 0 <= down_percent <= 100 or min(price, tax_percent, insurance_percent, maintenance_percent, pmi_percent) < 0:
        raise ValueError("Invalid cost assumptions.")
    loan = price * (1 - down_percent / 100)
    return {
        "Principal + interest": monthly_payment(loan, rate, years),
        "Property tax": price * tax_percent / 1200,
        "Insurance": price * insurance_percent / 1200,
        "Maintenance reserve": price * maintenance_percent / 1200,
        "PMI": loan * pmi_percent / 1200 if down_percent < 20 and loan > 0 else 0,
    }


def real_dollars(values, cpi_values, reference_cpi):
    return values * reference_cpi / cpi_values


def rebase(frame: pd.DataFrame, columns: list[str], base_year: int) -> pd.DataFrame:
    baseline = frame.loc[frame.year == base_year]
    if len(baseline) != 1 or (baseline[columns] <= 0).any().any():
        raise ValueError("A single positive baseline observation is required.")
    output = frame[["year", *columns]].copy()
    output[columns] = output[columns].div(baseline.iloc[0][columns].astype(float)) * 100
    return output


def cohort_description(year: int, age_group: str) -> str:
    """Birth spans are approximate calendar-year subtraction, not microdata cohort membership."""
    low_age, high_age = map(int, age_group.split("-"))
    earliest, latest = year - high_age, year - low_age
    definitions = [(1946, 1964, "Baby Boomers"), (1965, 1980, "Gen X"),
                   (1981, 1996, "Millennials"), (1997, 2012, "Gen Z")]
    names = [name for start, end, name in definitions if earliest <= end and latest >= start]
    label = " / ".join(names) if names else "earlier/later cohorts"
    return f"born approximately {earliest}–{latest} · {label}"
