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


@dataclass(frozen=True)
class LocalSeries:
    key: str
    description: str
    agg: str
    notes: str | None = None


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
        key="domestic_financial_tsy_tx",
        series_id="BOGZ1FU793061105Q",
        description="Domestic Financial Sectors; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes="Quarterly Z.1 sector-total Treasury transactions for the full domestic financial block. Used in DU-side Treasury-security residual research.",
    ),
    FredSeries(
        key="domestic_financial_tsy_level",
        series_id="BOGZ1FL793061105Q",
        description="Domestic Financial Sectors; Treasury Securities; Asset, Level",
        agg="last",
        notes="Quarterly Z.1 sector-total Treasury levels for the full domestic financial block. Used in DU-side Treasury-security residual research.",
    ),
    FredSeries(
        key="domestic_nonfinancial_tsy_tx",
        series_id="BOGZ1FU383061105Q",
        description="Domestic Nonfinancial Sectors; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes="Quarterly Z.1 sector-total Treasury transactions for the domestic nonfinancial block. Used as the cleanest first-pass DU-side Treasury-security proxy.",
    ),
    FredSeries(
        key="domestic_nonfinancial_tsy_level",
        series_id="BOGZ1FL383061105Q",
        description="Domestic Nonfinancial Sectors; Treasury Securities; Asset, Level",
        agg="last",
        notes="Quarterly Z.1 sector-total Treasury levels for the domestic nonfinancial block. Used as the cleanest first-pass DU-side Treasury-security holdings proxy.",
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
        key="loans_and_leases_bank_credit",
        series_id="LOANS",
        description="Loans and Leases in Bank Credit, All Commercial Banks",
        agg="last",
        notes="Monthly H.8 component series used in Stage 1 monetary diagnostics to separate loan-driven bank-credit changes from Treasury/security-heavy balance-sheet blocks.",
    ),
    FredSeries(
        key="securities_in_bank_credit",
        series_id="INVEST",
        description="Securities in Bank Credit, All Commercial Banks",
        agg="last",
        notes="Monthly H.8 component series used in Stage 1 monetary diagnostics as the securities side of bank credit.",
    ),
    FredSeries(
        key="treasury_agency_non_mbs_bank_securities",
        series_id="TNMACBM027SBOG",
        description="Treasury and Agency Securities: Non-MBS, All Commercial Banks",
        agg="last",
        notes="Monthly H.8 component series used in Stage 1 monetary diagnostics to strip a Treasury/agency-heavy securities block out of total bank-credit controls.",
    ),
    FredSeries(
        key="retail_money_market_funds",
        series_id="RMFSL",
        description="Retail Money Market Funds",
        agg="last",
        notes="Monthly seasonally adjusted H.6 component series. Used in Stage 0 monetary diagnostics to move from the partial `M2 - currency` proxy toward a depository-style target.",
    ),
    FredSeries(
        key="small_time_deposits",
        series_id="STDSL",
        description="Small-Denomination Time Deposits: Total",
        agg="last",
        notes="Monthly seasonally adjusted H.6 component series. Used in Stage 0 monetary diagnostics as the small-time-deposit subtraction for a more liquid-deposit target.",
    ),
    FredSeries(
        key="commercial_bank_deposits",
        series_id="DPSACBM027NBOG",
        description="Deposits, All Commercial Banks",
        agg="last",
        notes="Monthly H.8/FRED bank-deposit target used as a bank-only Stage 0 cross-check.",
    ),
    FredSeries(
        key="large_time_deposits_all_commercial_banks",
        series_id="LTDACBM027SBOG",
        description="Large Time Deposits, All Commercial Banks",
        agg="last",
        notes="Monthly H.8/FRED liability series. First candidate source family for decomposing the bank-minus-liquid/perimeter wedge into a large-time or wholesale deposit component.",
    ),
    FredSeries(
        key="other_deposits_all_commercial_banks",
        series_id="ODSACBM027SBOG",
        description="Other Deposits, All Commercial Banks",
        agg="last",
        notes="Monthly seasonally adjusted H.8/FRED liability series. Best remaining public broad bank-deposit context candidate for the bank-only liquid-deposit decomposition, but still too broad to treat as a clean subcomponent because H.8 folds transaction deposits into this bucket.",
    ),
    FredSeries(
        key="reserve_balances_with_frb",
        series_id="WRESBAL",
        description="Reserve Balances with Federal Reserve Banks: Week Average",
        agg="last",
        notes="Weekly H.4.1 reserve-balance series used as a first central-bank liquidity control in monetary Stage 1 diagnostics.",
    ),
    FredSeries(
        key="term_deposits_at_fed",
        series_id="TERMT",
        description="Term Deposits Held by Depository Institutions: Wednesday Level",
        agg="last",
        notes="Weekly H.4.1 series used in Stage 1 monetary diagnostics as a Fed absorption control distinct from reserve balances and Treasury cash.",
    ),
    FredSeries(
        key="other_deposits_at_fed",
        series_id="WLODLL",
        description="Other Deposits Held by Depository Institutions: Wednesday Level",
        agg="last",
        notes="Weekly H.4.1 series used in Stage 1 monetary diagnostics as a non-reserve depository cash-at-Fed absorption control.",
    ),
    FredSeries(
        key="fed_liquidity_credit_loans_net",
        series_id="H41RESPPALDNNWW",
        description="Liquidity and Credit Facilities: Loans, Net: Wednesday Level",
        agg="last",
        notes="Weekly H.4.1 series used in Stage 1 monetary diagnostics as a first nonfiscal Fed-liquidity support control.",
    ),
    FredSeries(
        key="reverse_repo_treasury",
        series_id="RRPTSYD",
        description="Reverse Repurchase Agreements: Treasury Securities Sold by the Federal Reserve in the Temporary Open Market Operations",
        agg="last",
        notes="Daily New York Fed RRP series used as a liquidity-drain control in monetary Stage 1 diagnostics.",
    ),
    FredSeries(
        key="commercial_bank_borrowings",
        series_id="H8B3094NCBDM",
        description="Borrowings, All Commercial Banks",
        agg="last",
        notes="Monthly H.8 series used in Stage 1 monetary diagnostics as a bank-funding context term.",
    ),
    FredSeries(
        key="commercial_bank_cash_assets",
        series_id="CASACBM027SBOG",
        description="Cash Assets, All Commercial Banks",
        agg="last",
        notes="Monthly H.8 series used in Stage 1 monetary diagnostics as a bank-liquidity context term.",
    ),
    FredSeries(
        key="foreign_official_custody_treasuries",
        series_id="WMTSEC1",
        description="Custody Holdings: Marketable U.S. Treasury Securities: Week Average",
        agg="last",
        notes="Weekly H.4.1 memorandum series used in Stage 1 monetary diagnostics as a foreign-official custody context term. It is not treated as a clean signed control because of overlap risk with the ladder's own ROW Treasury channels.",
    ),
    FredSeries(
        key="foreign_related_treasury_agency_non_mbs",
        series_id="TNMFRIM027SBOG",
        description="Treasury and Agency Securities: Non-MBS, Foreign-Related Institutions",
        agg="last",
        notes="Monthly H.8 foreign-related-institutions series used in Stage 1 monetary diagnostics as a foreign / portfolio-shift context term rather than a clean signed control.",
    ),
    FredSeries(
        key="gdp_deflator",
        series_id="GDPDEF",
        description="Gross Domestic Product: Implicit Price Deflator",
        agg="last",
        notes="Quarterly price index used for the optional latest-quarter-dollar restatement in the site UI.",
    ),
    FredSeries(
        key="nominal_gdp_saar_bil",
        series_id="GDP",
        description="Gross Domestic Product, billions of dollars, seasonally adjusted annual rate",
        agg="last",
        notes="Quarterly nominal GDP level (SAAR, billions of current-dollars). Denominator for the optional 'percent of GDP' view in the site UI. To align with estimator-scale quarterly millions, use `value_millions / (nominal_gdp_saar_bil * 250)`, which equals `(value_millions * 4) / (nominal_gdp_saar_bil * 1000)`.",
    ),
    FredSeries(
        key="tga_weekly",
        series_id="WDTGAL",
        description="U.S. Treasury, General Account: Wednesday Level",
        agg="last",
        notes="TGA-only weekly diagnostic. Useful for high-frequency checks, but not a substitute for the Tier 0 Treasury operating cash term when historical Treasury Tax and Loan balances were material.",
    ),
    FredSeries(
        key="bea_row_fed_interest_paid_saar",
        series_id="B093RC1Q027SBEA",
        description="Federal government current expenditures: Interest payments: to the rest of the world",
        agg="last",
        notes="Quarterly SAAR benchmark series from BEA via FRED. Useful for unit and scale checks against the rest-of-world Treasury coupon-interest proxy.",
    ),
    FredSeries(
        key="bea_row_taxes_received_saar",
        series_id="W008RC1Q027SBEA",
        description="Federal government current tax receipts: Taxes from the rest of the world",
        agg="last",
        notes="Quarterly SAAR benchmark series from BEA via FRED. Use `billions * 250` to convert to estimator-scale quarterly millions.",
    ),
    FredSeries(
        key="bea_row_social_insurance_received_saar",
        series_id="W781RC1Q027SBEA",
        description="Federal government current receipts: Contributions for government social insurance: From the rest of the world",
        agg="last",
        notes="Quarterly SAAR benchmark series from BEA via FRED. Use `billions * 250` to convert to estimator-scale quarterly millions.",
    ),
    FredSeries(
        key="bea_row_current_transfer_receipts_received_saar",
        series_id="LA0000281Q027SBEA",
        description="Federal government current receipts: Current transfer receipts: From the rest of the world",
        agg="last",
        notes="Quarterly SAAR benchmark series from BEA via FRED. Use `billions * 250` to convert to estimator-scale quarterly millions.",
    ),
    FredSeries(
        key="federal_current_expenditures_nsa_q",
        series_id="NA000283Q",
        description="Federal Government: Current Expenditures",
        agg="last",
        notes="Quarterly BEA/FRED not-seasonally-adjusted federal current expenditures in millions. Used as the historical DU fiscal-flow total-outlay fallback before the MTS cash window.",
    ),
    FredSeries(
        key="federal_current_receipts_nsa_q",
        series_id="NA000304Q",
        description="Federal Government Current Receipts",
        agg="last",
        notes="Quarterly BEA/FRED not-seasonally-adjusted federal current receipts in millions. Used as the historical DU fiscal-flow total-receipt fallback before the MTS cash window.",
    ),
    FredSeries(
        key="federal_interest_payments_nsa_q",
        series_id="NA000308Q",
        description="Federal government current expenditures: Interest payments",
        agg="last",
        notes="Quarterly BEA/FRED not-seasonally-adjusted federal interest payments in millions. Used as the historical DU fiscal-flow coupon/debt-service fallback before the MTS cash window.",
    ),
]

LOCAL_SUPPORT_SERIES: list[LocalSeries] = [
    LocalSeries(
        key="fed_tsy_coupon_interest_proxy",
        description="Quarterly Fed Treasury coupon-interest proxy built from SOMA holdings snapshots.",
        agg="sum",
        notes="Optional local support series. This is not downloaded from FRED; it is produced locally from SOMA holdings snapshots and used for Tier 1 Fed-corrected estimator variants.",
    ),
    LocalSeries(
        key="bank_tsy_coupon_interest_proxy",
        description="Quarterly bank-sector Treasury coupon-interest proxy for the default bank perimeter.",
        agg="sum",
        notes="Optional local support series. This is not downloaded from FRED; it is produced locally and used for Tier 2 interest-corrected estimator variants. The default bank perimeter matches the Tier 0 bank-sector block: U.S.-chartered depositories, foreign banking offices in the U.S., and banks in U.S.-affiliated areas.",
    ),
    LocalSeries(
        key="row_tsy_coupon_interest_proxy",
        description="Quarterly rest-of-world Treasury coupon-interest proxy.",
        agg="sum",
        notes="Optional local support series. This is not downloaded from FRED; it is produced locally and used for Tier 2 interest-corrected estimator variants that include the rest-of-world Treasury term.",
    ),
    LocalSeries(
        key="bank_noninterest_outlay_proxy",
        description="Quarterly Treasury noninterest outlay proxy to the default bank perimeter.",
        agg="sum",
        notes="Optional local support series. Positive values represent Treasury noninterest payments to the Tier 0 bank block and are subtracted in Tier 3 fiscal-corrected variants.",
    ),
    LocalSeries(
        key="row_noninterest_outlay_proxy",
        description="Quarterly Treasury noninterest outlay proxy to the rest of world.",
        agg="sum",
        notes="Optional local support series. Positive values represent Treasury noninterest payments to the rest of world and are subtracted in Tier 3 fiscal-corrected variants that include the ROW term.",
    ),
    LocalSeries(
        key="bank_nonborrow_receipt_proxy",
        description="Quarterly Treasury nonborrow receipt proxy from the default bank perimeter.",
        agg="sum",
        notes="Optional local support series. Positive values represent Treasury nonborrow receipts from the Tier 0 bank block and are added in Tier 3 fiscal-corrected variants.",
    ),
    LocalSeries(
        key="row_nonborrow_receipt_proxy",
        description="Quarterly Treasury nonborrow receipt proxy from the rest of world.",
        agg="sum",
        notes="Optional local support series. Positive values represent Treasury nonborrow receipts from the rest of world and are added in Tier 3 fiscal-corrected variants that include the ROW term.",
    ),
    LocalSeries(
        key="mint_cb_cash_factor_proxy",
        description="Quarterly mint or central-bank cash-factor proxy.",
        agg="sum",
        notes="Optional local support series. Positive values offset Treasury operating-cash changes that did not come from deposit-user taxes or deposit-user Treasury purchases and are added in Tier 3 fiscal-corrected variants.",
    ),
    LocalSeries(
        key="credit_union_deposits",
        description="Quarterly federally insured credit-union shares and deposits bridge from NCUA Call Report ZIPs.",
        agg="last",
        notes="Optional local support series. This is a bridge-side support series for the bank-versus-broad-depository monetary diagnostic, built from NCUA quarterly Call Report `Acct_018` totals for federally insured credit unions.",
    ),
    LocalSeries(
        key="thrift_deposits",
        description="Quarterly FDIC savings-institution deposit bridge from the banks financial API.",
        agg="last",
        notes="Optional local support series. This is the thrift or savings-institution side of the bank-versus-broad-depository monetary diagnostic, built from FDIC `DEP` totals for BKCLASS `SB`, `SI`, and `SL`.",
    ),
]

TREASURY_DATASETS: list[TreasuryDataset] = [
    TreasuryDataset(
        key="dts_operating_cash_balance",
        endpoint="/v1/accounting/dts/deposits_withdrawals_operating_cash",
        description="Daily Treasury Statement deposits and withdrawals of operating cash",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="mts_receipts",
        endpoint="/v1/accounting/mts/mts_table_4",
        description="Monthly Treasury Statement receipts table",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="mts_outlays",
        endpoint="/v1/accounting/mts/mts_table_5",
        description="Monthly Treasury Statement outlays table",
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
    TreasuryDataset(
        key="revenue_collections",
        endpoint="/v2/revenue/rcm",
        description="U.S. Government Revenue Collections",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="receipts_by_department",
        endpoint="/v1/accounting/od/receipts_by_department",
        description="Receipts by Department annual account-symbol detail",
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


def all_local_support_series() -> list[LocalSeries]:
    return list(LOCAL_SUPPORT_SERIES)
