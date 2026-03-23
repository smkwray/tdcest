from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FredSeries:
    key: str
    series_id: str
    description: str
    agg: str
    required: bool = False
    transform: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class TreasuryDataset:
    key: str
    endpoint: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)


BASE_FRED_SERIES: list[FredSeries] = [
    FredSeries(
        key="fed_tsy_tx",
        series_id="BOGZ1FU713061103Q",
        description="Monetary Authority; Total Treasury Securities; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="us_chartered_tsy_tx",
        series_id="BOGZ1FU763061100Q",
        description="U.S.-Chartered Depository Institutions; Treasury Securities; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="foreign_offices_tsy_tx",
        series_id="BOGZ1FU753061103Q",
        description="Foreign Banking Offices in the U.S.; Treasury Securities; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="affiliated_areas_tsy_tx",
        series_id="BOGZ1FU743061103Q",
        description="Banks in U.S.-Affiliated Areas; Treasury Securities; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="np_credit_unions_tsy_tx",
        series_id="BOGZ1FU473061103Q",
        description="Credit Unions; Treasury Securities, Excluding Corporate Credit Unions; Asset, Transactions",
        agg="sum",
        required=True,
        notes="Natural-person credit union Treasury transactions. This is the preferred credit-union series for a broad-depository TDC variant.",
    ),
    FredSeries(
        key="corp_credit_unions_tsy_tx",
        series_id="BOGZ1FU473061153Q",
        description="Credit Unions; Treasury Securities Held by Corporate Credit Unions; Asset, Transactions",
        agg="sum",
        required=True,
        notes="Corporate credit union Treasury transactions. Included as a sensitivity series rather than the default broad-depository headline.",
    ),
    FredSeries(
        key="ncua_capitalization_deposit_tx",
        series_id="BOGZ1FU473061203Q",
        description="Credit Unions; National Credit Union Administration (NCUA) Share Insurance Capitalization Deposit; Asset, Transactions",
        agg="sum",
        required=True,
        notes="This term is part of the aggregate credit-union Treasury series in Z.1 but is not treated as a headline marketable-Treasury contribution in this repo.",
    ),
    FredSeries(
        key="row_tsy_tx",
        series_id="BOGZ1FU263061105Q",
        description="Rest of the World; Treasury Securities; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="treasury_operating_cash_tx",
        series_id="BOGZ1FU313024000Q",
        description="Federal Government; Treasury Operating Cash; Asset, Transactions",
        agg="sum",
        required=True,
    ),
    FredSeries(
        key="fed_remit_or_deferred",
        series_id="RESPPLLOPNWW",
        description="Liabilities and Capital: Liabilities: Earnings Remittances Due to the U.S. Treasury: Wednesday Level",
        agg="sum",
        required=True,
        transform="clip_positive",
        notes="Positive values are weekly remittances due to Treasury. Negative values are the deferred asset and are clipped to zero in the baseline method.",
    ),
]

OPTIONAL_FRED_SERIES: list[FredSeries] = [
    FredSeries(
        key="credit_unions_total_tsy_tx",
        series_id="BOGZ1FU473061105Q",
        description="Credit Unions; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes="Aggregate credit-union Treasury series. In Z.1, this equals natural-person credit-union Treasuries plus corporate credit-union Treasuries plus the NCUA capitalization deposit.",
    ),
    FredSeries(
        key="fed_tsy_level",
        series_id="BOGZ1FL713061103Q",
        description="Monetary Authority; Total Treasury Securities; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="us_chartered_tsy_level",
        series_id="BOGZ1FL763061100Q",
        description="U.S.-Chartered Depository Institutions; Treasury Securities; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="foreign_offices_tsy_level",
        series_id="BOGZ1FL753061103Q",
        description="Foreign Banking Offices in the U.S.; Treasury Securities; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="affiliated_areas_tsy_level",
        series_id="BOGZ1FL743061103Q",
        description="Banks in U.S.-Affiliated Areas; Treasury Securities; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="np_credit_unions_tsy_level",
        series_id="BOGZ1FL473061103Q",
        description="Credit Unions; Treasury Securities, Excluding Corporate Credit Unions; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="corp_credit_unions_tsy_level",
        series_id="BOGZ1FL473061153Q",
        description="Credit Unions; Treasury Securities Held by Corporate Credit Unions; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="ncua_capitalization_deposit_level",
        series_id="BOGZ1FL473061203Q",
        description="Credit Unions; National Credit Union Administration (NCUA) Share Insurance Capitalization Deposit; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="credit_unions_total_tsy_level",
        series_id="BOGZ1FL473061105Q",
        description="Credit Unions; Treasury Securities; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="row_tsy_level",
        series_id="BOGZ1LM263061105Q",
        description="Rest of the World; Treasury Securities; Asset, Market Value Levels",
        agg="last",
    ),
    FredSeries(
        key="treasury_operating_cash_level",
        series_id="BOGZ1FL313024000Q",
        description="Federal Government; Treasury Operating Cash; Asset, Level",
        agg="last",
    ),
    FredSeries(
        key="m2",
        series_id="M2SL",
        description="M2, seasonally adjusted",
        agg="last",
    ),
    FredSeries(
        key="currency",
        series_id="CURRCIR",
        description="Currency in circulation",
        agg="last",
    ),
    FredSeries(
        key="bank_credit",
        series_id="TOTBKCR",
        description="Total bank credit, all commercial banks",
        agg="last",
    ),
    FredSeries(
        key="gdp_deflator",
        series_id="GDPDEF",
        description="Gross Domestic Product: Implicit Price Deflator",
        agg="last",
        notes="Quarterly price index used for the optional latest-quarter-dollar restatement in the site UI.",
    ),
    FredSeries(
        key="tga_weekly",
        series_id="WDTGAL",
        description="U.S. Treasury, General Account: Wednesday Level",
        agg="last",
    ),
]

TREASURY_DATASETS: list[TreasuryDataset] = [
    TreasuryDataset(
        key="dts_operating_cash_balance",
        endpoint="/v1/accounting/dts/operating_cash_balance",
        description="Daily Treasury Statement operating cash balance",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="mts_receipts",
        endpoint="/v1/accounting/mts/mts_table_4",
        description="Monthly Treasury Statement receipts table",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="mspd_marketable",
        endpoint="/v1/debt/mspd/mspd_table_3_market",
        description="Monthly Statement of the Public Debt marketable detail",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="mspd_detail",
        endpoint="/v1/debt/mspd/mspd_table_3",
        description="Monthly Statement of the Public Debt full detail",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="slgs_securities",
        endpoint="/v1/accounting/od/slgs_securities",
        description="State and Local Government Series securities (nonmarketable)",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
]

BANK_DEPOSITORY_TX_KEYS = [
    "us_chartered_tsy_tx",
    "foreign_offices_tsy_tx",
    "affiliated_areas_tsy_tx",
]

BANK_DEPOSITORY_LEVEL_KEYS = [
    "us_chartered_tsy_level",
    "foreign_offices_tsy_level",
    "affiliated_areas_tsy_level",
]

CU_COMPONENT_TX_KEYS = [
    "np_credit_unions_tsy_tx",
    "corp_credit_unions_tsy_tx",
    "ncua_capitalization_deposit_tx",
]

CU_COMPONENT_LEVEL_KEYS = [
    "np_credit_unions_tsy_level",
    "corp_credit_unions_tsy_level",
    "ncua_capitalization_deposit_level",
]


def all_fred_series(include_optional: bool = True) -> list[FredSeries]:
    if include_optional:
        return [*BASE_FRED_SERIES, *OPTIONAL_FRED_SERIES]
    return list(BASE_FRED_SERIES)
