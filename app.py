"""Gen Z Lens — a local, source-transparent dashboard. Run: streamlit run app.py."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from genz.metrics import cohort_description, ownership_cost, real_dollars, rebase
from genz.pipeline import DEFAULT_DATA, load_snapshot, run_pipeline

st.set_page_config(page_title="Gen Z Lens", page_icon="◒", layout="wide")
st.markdown("""<style>
.block-container {padding-top:2rem; max-width:1450px;}
h1 {letter-spacing:-.045em; font-weight:800 !important;}
div[data-testid="stMetric"] {background:#152231; border:1px solid #293e4e; border-radius:14px; padding:18px;}
.eyebrow {font-size:12px;letter-spacing:3px;color:#76dac1;font-weight:700;}
.deck {color:#afc1ca; font-size:18px;max-width:850px;line-height:1.6;}
div[data-testid="stTabs"] button {font-weight:600;}
</style>""", unsafe_allow_html=True)

COLORS = ["#76DAC1", "#FFA38D", "#C3B1FF", "#F2CF7E", "#8DBCE9", "#B9CCAD"]
LABELS = {"home_price": "New-home price", "income": "Household income", "cpi": "All-items CPI",
          "rent": "Rent index", "food": "Groceries index", "energy": "Energy index", "wage": "Hourly earnings"}


def chart(figure, y_title=None):
    figure.update_layout(template="plotly_dark", colorway=COLORS, paper_bgcolor="rgba(0,0,0,0)",
                         plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=20, t=35, b=15),
                         font=dict(family="Arial", color="#d6e1e4"), hovermode="x unified",
                         legend=dict(orientation="h", y=1.16, title=None), height=380)
    figure.update_xaxes(title=None, showgrid=False)
    figure.update_yaxes(title=y_title, gridcolor="#263746")
    st.plotly_chart(figure, width="stretch")


def lines(frame, columns, labels=None, y_title=None):
    labels = labels or LABELS
    tidy = frame.melt(id_vars="year", value_vars=columns, var_name="series", value_name="value")
    tidy["series"] = tidy.series.map(lambda key: labels.get(key, key))
    figure = px.line(tidy, x="year", y="value", color="series", color_discrete_sequence=COLORS)
    figure.update_traces(line_width=3)
    chart(figure, y_title)


def money(value):
    return f"${value:,.0f}"


def comparison_metric(column, title, before, after, formatter=lambda x: f"{x:,.1f}", suffix=""):
    with column:
        st.metric(title, formatter(after) + suffix, f"{(after / before - 1) * 100:+.1f}% vs baseline", delta_color="off")


with st.sidebar:
    st.markdown("### ◒ Gen Z Lens")
    st.caption("THE COST OF COMING OF AGE")
    st.divider()
    st.write("**United States · national data**")
    st.caption("Public sources. Local files. No account or API key required.")
    if st.button("Refresh public data", width="stretch"):
        try:
            with st.spinner("Downloading, cleaning, and validating sources…"):
                run_pipeline()
            st.success("A new snapshot is ready.")
        except Exception as error:
            st.error(f"Refresh failed; the last published snapshot is retained. {error}")
    st.caption("A failed source refresh may use its verified cache. See Data room for status.")

try:
    snapshot = load_snapshot()
except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as error:
    st.error(str(error))
    st.code("python -m genz.pipeline")
    st.stop()

annual, marriage, living = snapshot["annual"], snapshot["marriage"], snapshot["living"]
manifest = snapshot["manifest"]
years = annual.year.astype(int).tolist()
with st.sidebar:
    start = st.selectbox("Baseline year", years[:-1], index=years[:-1].index(2000) if 2000 in years[:-1] else 0)
    end_options = [year for year in years if year > start]
    end = st.selectbox("Comparison year", end_options, index=len(end_options) - 1)
    st.caption(f"Common complete economic years: {years[0]}–{years[-1]}. Current and incomplete years are excluded.")
    st.caption("Later releases remain available below. Missing monthly values can exclude a past year too; see the quality report.")
    st.divider()
    st.caption("Gen Z convention used here: born 1997–2012. Age tables are repeated snapshots, not a panel tracking the same people.")

baseline = annual.loc[annual.year == start].iloc[0]
current = annual.loc[annual.year == end].iloc[0]
selected = annual.loc[annual.year.between(start, end)].copy()
inflation_multiplier = current.cpi / baseline.cpi

st.markdown('<div class="eyebrow">GEN Z LENS / A PUBLIC DATA OBSERVATORY</div>', unsafe_allow_html=True)
st.title("Coming of age, priced differently.")
st.markdown('<div class="deck">Explore what changed in housing, everyday prices, and the timing of adult life. '
            'Compare the dollars, control for inflation, and keep the age groups in view.</div>', unsafe_allow_html=True)
st.caption(f"Economics: {start} → {end} · Marriage-age data through {manifest['marriage_latest']} · "
           f"Age-specific living arrangements through {manifest['living_latest']} · Snapshot {manifest['run_id']}")
for warning in snapshot["quality"]["warnings"]:
    st.warning(warning)

overview, housing, costs, relationships, data_room = st.tabs(
    ["The big picture", "Housing lab", "Cost of living", "Marriage & home", "Data room"])

with overview:
    with st.expander("Latest source observations · separate from the matched-year comparisons"):
        recent = snapshot["observations"].sort_values("date").groupby("series").tail(1).copy()
        recent["Dataset"] = recent.series.map(lambda key: LABELS.get(key, "30-year mortgage rate"))
        recent["Units"] = recent.series.map(lambda key: manifest["sources"][key]["units"])
        st.dataframe(recent[["Dataset", "date", "value", "Units"]].rename(columns={"date": "Observation date", "value": "Source value"}), hide_index=True, width="stretch")
        st.caption("These are monthly, quarterly, weekly, and annual observations with different reference periods. They are not combined into a same-year affordability ratio.")
    st.subheader(f"Then and now: {start} → {end}")
    cards = st.columns(4)
    comparison_metric(cards[0], "New-home price / income", baseline.price_to_income, current.price_to_income, lambda x: f"{x:.2f}", "×")
    comparison_metric(cards[1], f"New-home price · {end}", baseline.home_price, current.home_price, money)
    comparison_metric(cards[2], "Overall price level", 1, inflation_multiplier, lambda x: f"{x:.2f}", "×")
    comparison_metric(cards[3], "Median household income", baseline.income, current.income, money)
    st.caption("New-home price is the annual mean of quarterly median sale prices. Income covers all households, not Gen Z specifically. "
               "Their ratio is a national indicator, not a matched household affordability measure.")
    st.subheader("Did prices outrun income—or inflation?")
    indexed = rebase(selected, ["home_price", "income", "cpi", "wage"], start)
    lines(indexed, ["home_price", "income", "cpi", "wage"], y_title=f"Index · {start} = 100")
    excess = ((current.home_price / baseline.home_price) / inflation_multiplier - 1) * 100
    st.info(f"The inflation-adjusted new-home price changed by {excess:+.1f}% over this window. "
            "This describes national price changes; it does not identify why they changed or what a specific generation paid.")
    left, right = st.columns(2)
    with left:
        st.subheader("The home-price / income gap")
        chart(px.area(selected, x="year", y="price_to_income", color_discrete_sequence=COLORS), "Price / annual household income")
    with right:
        st.subheader("Borrowing costs changed, too")
        lines(selected, ["mortgage_rate"], {"mortgage_rate": "30-year fixed rate"}, "Annual-average mortgage rate (%)")
    st.caption("Sources: Census/HUD new residential sales, Census CPS ASEC income, BLS price/earnings series, and Freddie Mac PMMS, distributed by FRED. "
               "All source links, cleaning choices, and publication dates are in Data room.")

with housing:
    st.subheader("What would ownership cost under the same assumptions?")
    st.caption("A transparent scenario using each year's national new-home price and average mortgage rate. Change the assumptions; inspect the pieces.")
    settings = st.columns(3)
    down = settings[0].slider("Down payment (%)", 0, 100, 20, 5)
    term = settings[1].selectbox("Loan term (years)", [15, 20, 30], index=2)
    household_income = settings[2].number_input("Your scenario: annual gross household income ($)", min_value=1000, max_value=2_000_000, value=int(current.income), step=1000)
    assumptions = st.columns(4)
    tax = assumptions[0].number_input("Property tax (% of price / year)", min_value=0.0, max_value=10.0, value=1.1, step=.1)
    insurance = assumptions[1].number_input("Insurance (% of price / year)", min_value=0.0, max_value=10.0, value=.5, step=.1)
    maintenance = assumptions[2].number_input("Maintenance reserve (% / year)", min_value=0.0, max_value=10.0, value=1.0, step=.1)
    pmi = assumptions[3].number_input("PMI (% of loan / year below 20% down)", min_value=0.0, max_value=5.0, value=.5, step=.1)
    rows = []
    for _, row in selected.iterrows():
        components = ownership_cost(row.home_price, row.mortgage_rate, down, term, tax, insurance, maintenance, pmi)
        rows.append({"year": int(row.year), **components, "Total": sum(components.values()),
                     "national_income_share": sum(components.values()) / (row.income / 12) * 100})
    model = pd.DataFrame(rows)
    latest_cost = model.iloc[-1]
    first_cost = model.iloc[0]
    tiles = st.columns(4)
    tiles[0].metric(f"Modeled monthly total · {end}", money(latest_cost.Total))
    tiles[1].metric("Share of your gross income", f"{latest_cost.Total / (household_income / 12) * 100:.1f}%")
    tiles[2].metric("Down payment needed", money(current.home_price * down / 100))
    tiles[3].metric(f"{start} monthly cost in {end} dollars", money(first_cost.Total * inflation_multiplier))
    component_names = ["Principal + interest", "Property tax", "Insurance", "Maintenance reserve", "PMI"]
    chart(px.area(model, x="year", y=component_names, color_discrete_sequence=COLORS), "Modeled monthly dollars, nominal")
    st.caption("Tax, insurance, maintenance and PMI percentages are user assumptions held constant across years, not historical observations. "
               "Excludes HOA, utilities, closing costs, transaction costs, tax benefits, regional variation, and individual loan terms. "
               "Maintaining a reserve is not the same as actual monthly maintenance spending. Income shares use gross income before tax.")
    with st.expander("Inspect the scenario table and formulas"):
        st.dataframe(model, hide_index=True, width="stretch")
        st.code("loan = price × (1 − down_payment / 100)\nmonthly_rate = annual_rate_percent / 1200\nP&I = loan × monthly_rate / (1 − (1 + monthly_rate)^(-12 × years))\nannual percentage costs / month = price × percentage / 1200")
        st.download_button("Download housing scenario CSV", model.to_csv(index=False), "housing_scenario.csv", "text/csv")

with costs:
    st.subheader("Different parts of the budget moved differently")
    st.caption("These are price indices, not dollar spending estimates or a personalized cost-of-living basket.")
    cost_columns = st.multiselect("Compare price and earnings series", ["cpi", "rent", "food", "energy", "wage"],
                                  default=["cpi", "rent", "food", "wage"], format_func=lambda key: LABELS[key])
    if cost_columns:
        lines(rebase(selected, cost_columns, start), cost_columns, y_title=f"Index · {start} = 100")
    mode = st.radio("Show dollar trends as", ["Nominal dollars", f"Inflation-adjusted {end} dollars"], horizontal=True)
    dollar_frame = selected[["year", "home_price", "income"]].copy()
    if mode != "Nominal dollars":
        for column in ("home_price", "income"):
            dollar_frame[column] = real_dollars(selected[column], selected.cpi, current.cpi)
    left, right = st.columns(2)
    with left:
        lines(dollar_frame, ["home_price"], y_title=mode)
    with right:
        lines(dollar_frame, ["income"], y_title=mode)
    st.caption("CPI-U measures a broad urban-consumer basket. Rent is the rent-of-primary-residence price index, not asking rents or median rent. "
               "Hourly earnings cover private production/nonsupervisory employees, not all workers or specifically young adults. "
               "Index growth is comparable after rebasing; index levels from different series are not directly comparable before rebasing.")

with relationships:
    st.subheader("Marriage timing, and life at the same age")
    st.caption("The long-run marriage chart covers adults nationally. The age-group comparisons below are the direct young-adult evidence.")
    chart(px.line(marriage, x="year", y="median_age", color="sex", markers=True, color_discrete_sequence=COLORS), "Estimated median age at first marriage")
    st.caption("Census MS-2: early historical benchmarks are decennial censuses; later observations are CPS. "
               "The x-axis reflects actual observed years. Connecting lines do not create annual observations. Census definitions and population controls changed over time.")
    left, middle, right = st.columns(3)
    age = left.selectbox("Keep the age group fixed", ["18-24", "25-34"])
    sex = middle.selectbox("Population", ["All (weighted)", "Men", "Women"])
    metric = right.selectbox("Living arrangement", ["living_with_spouse_pct", "child_of_householder_pct", "living_with_partner_pct", "living_alone_pct"],
                             format_func=lambda key: {"living_with_spouse_pct": "Living with a spouse", "child_of_householder_pct": "Child of the householder", "living_with_partner_pct": "Living with an unmarried partner", "living_alone_pct": "Living alone"}[key])
    age_data = living.loc[(living.age_group == age) & (living.sex == sex)].sort_values("year")
    age_years = age_data.year.astype(int).tolist()
    compare = st.columns(2)
    earlier = compare[0].selectbox("Earlier year · same age group", age_years[:-1], index=age_years[:-1].index(1990) if 1990 in age_years[:-1] else 0)
    later_years = [year for year in age_years if year > earlier]
    later = compare[1].selectbox("Later year · same age group", later_years, index=len(later_years) - 1)
    before_row = age_data.loc[age_data.year == earlier].iloc[0]
    after_row = age_data.loc[age_data.year == later].iloc[0]
    cards = st.columns(3)
    cards[0].metric(f"{earlier} · ages {age}", f"{before_row[metric]:.1f}%" if pd.notna(before_row[metric]) else "Unavailable")
    cards[1].metric(f"{later} · ages {age}", f"{after_row[metric]:.1f}%" if pd.notna(after_row[metric]) else "Unavailable")
    difference = after_row[metric] - before_row[metric]
    cards[2].metric("Change in percentage points", f"{difference:+.1f} pp" if pd.notna(difference) else "Unavailable")
    st.write(f"**{earlier}:** {cohort_description(earlier, age)}")
    st.write(f"**{later}:** {cohort_description(later, age)}")
    chart(px.line(age_data, x="year", y=metric, markers=True, color_discrete_sequence=COLORS), "Percent within the selected age group")
    st.info("Living with a spouse is not the same statistic as 'currently married' or 'ever married'. "
            "Child of the householder is the source's relationship category, not a complete measure of everyone living with parents. "
            "Age-25–34 observations can span Millennials and Gen Z; the dashboard does not label a mixed age band as entirely Gen Z.")
    st.caption("Source: Census AD-3. Combined percentages are weighted by each sex's population in the same year and age group. "
               "Published percentages are rounded; combined estimates inherit that rounding. Missing partner values remain missing. "
               "The underlying workbooks contain definition, questionnaire and population-control revisions, including revised duplicate years. "
               "This is a repeated cross-section, not a causal or longitudinal generational comparison.")

with data_room:
    st.subheader("Every number has a trail")
    st.write("**Download → content-addressed raw cache → cleaning → validation → versioned CSVs → atomic snapshot pointer → dashboard.**")
    source_rows = []
    for key, source in manifest["sources"].items():
        source_rows.append({"Dataset": source["title"], "Publisher": source["publisher"], "Units": source["units"],
                            "Last observation": str(source.get("coverage", {}).get("last", "See table")),
                            "Fetched UTC": source["fetched_at"], "Status": source["status"], "Download URL": source["url"], "SHA-256": source["sha256"]})
    st.dataframe(pd.DataFrame(source_rows), hide_index=True, width="stretch")
    st.write("**Known coverage differences**")
    st.write(f"Economic comparison: {years[0]}–{years[-1]}; first-marriage ages through {manifest['marriage_latest']}; "
             f"age-specific arrangements through {manifest['living_latest']}. Newer source observations remain in the raw/long tables but incomplete years are not used for annual comparisons.")
    with st.expander("Cleaning rules, formulas, and comparability"):
        st.markdown("""
- Parse dates and numeric fields; remove missing FRED observations; reject duplicate dates and nonpositive levels.
- Annual means require 4 quarterly prices, 12 monthly observations, at least 50 weekly rates, or one annual income observation. The current calendar year is excluded.
- A mean of quarterly medians is **not** an annual median. Different household/transaction populations are not matched.
- Compare only complete years common to all economic series; never forward-fill income or interpolate demographic gaps.
- Real dollars = nominal dollars × reference-year CPI / observation-year CPI. Rebased index = level / baseline level × 100.
- Historical Census row suffixes mark revised/control-adjusted alternatives. Keep the first published row per year/sex and retain its source label; alternate rows removed are counted in quality.json.
- National income covers all households; household composition and survey methods change. Age-group living-arrangement statistics are the only direct young-adult comparison here.
- Mortgage rates are annual averages of national survey observations; the PMMS methodology changed in November 2022. Tax, insurance, maintenance and PMI are scenarios, not observed historical costs.
- Statistics are descriptive, not evidence that inflation or housing caused a change in marriage behavior. Read the footnotes in the preserved Census workbooks before making fine-grained comparisons.
""")
    for name in ("annual", "marriage", "living", "observations"):
        st.download_button(f"Download cleaned {name} CSV", snapshot[name].to_csv(index=False), f"{name}.csv", "text/csv", key=f"download_{name}")
    st.download_button("Download provenance manifest", json.dumps(manifest, indent=2), "manifest.json", "application/json")
    st.json(snapshot["quality"], expanded=False)
    with st.expander("Preview annual data"):
        st.dataframe(annual, hide_index=True, width="stretch")
    st.markdown("Sources: [FRED](https://fred.stlouisfed.org/) · [Census marital tables](https://www.census.gov/data/tables/time-series/demo/families/marital.html) · "
                "[Census living arrangements](https://www.census.gov/data/tables/time-series/demo/families/adults.html). Data-provider terms and source notes apply; no government endorsement is implied.")
