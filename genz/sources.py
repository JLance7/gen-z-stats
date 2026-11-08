"""Keep source definitions and units next to the pipeline, rather than in charts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    filename: str
    url: str
    title: str
    publisher: str
    units: str
    frequency: str
    minimum_observations: int = 1


def fred(key, series, title, publisher, units, frequency, minimum):
    return Source(key, f"{series}.csv", f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd=1960-01-01",
                  title, publisher, units, frequency, minimum)


SOURCES = [
    fred("home_price", "MSPUS", "Median sales price of new houses sold", "Census / HUD via FRED", "current USD", "quarterly", 4),
    fred("income", "MEHOINUSA646N", "Median household income", "Census CPS ASEC via FRED", "current USD / household / year", "annual", 1),
    fred("cpi", "CPIAUCSL", "All-items CPI-U", "BLS via FRED", "index, 1982–84=100, seasonally adjusted", "monthly", 12),
    fred("mortgage_rate", "MORTGAGE30US", "30-year fixed mortgage rate", "Freddie Mac PMMS via FRED", "percent / year", "weekly", 50),
    fred("rent", "CUSR0000SEHA", "CPI: rent of primary residence", "BLS via FRED", "price index, seasonally adjusted", "monthly", 12),
    fred("food", "CUSR0000SAF11", "CPI: food at home", "BLS via FRED", "price index, seasonally adjusted", "monthly", 12),
    fred("energy", "CPIENGSL", "CPI: energy", "BLS via FRED", "price index, seasonally adjusted", "monthly", 12),
    fred("wage", "AHETPI", "Average hourly earnings, production and nonsupervisory employees, total private", "BLS via FRED", "current USD / hour, seasonally adjusted", "monthly", 12),
    Source("marriage_age", "ms2.xls", "https://www2.census.gov/programs-surveys/demo/tables/families/time-series/marital/ms2.xls",
           "MS-2: estimated median age at first marriage", "Census CPS / historical censuses", "years of age", "annual / historical benchmarks"),
    *[Source(f"living_{age}", f"ad3-{age}.xls", f"https://www2.census.gov/programs-surveys/demo/tables/families/time-series/adults/ad3-{age}.xls",
             f"AD-3: living arrangements, ages {age}", "Census CPS ASEC", "percent within age and sex; population in thousands", "annual / historical benchmarks")
      for age in ("18-24", "25-34")],
]

SOURCE_BY_KEY = {source.key: source for source in SOURCES}
