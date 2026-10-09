from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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


@dataclass(frozen=True)
class FiscusInput:
    """One caller-owned input acquired through a fiscus command.

    ``argv`` is the exact fiscus command after the executable name. Values are
    multiplied by ``usd_million_per_unit`` to reach USD million.
    """

    key: str
    dataset_id: str
    argv: tuple[str, ...]
    usd_million_per_unit: float
    clock: str
    description: str
    series_id: str | None = None
    snapshot_window: tuple[str, str] | None = None
    native_units: str | None = None

    @property
    def units(self) -> str:
        return self.native_units or {0.000001: "USD dollars or field-specific", 1.0: "USD million", 1000.0: "USD billion"}[self.usd_million_per_unit]


@dataclass(frozen=True)
class FiscusRegistry:
    """Named fiscus inputs exported to one directory and described by one manifest."""

    name: str
    inputs: tuple[FiscusInput, ...]
    input_dir: Path
    manifest: Path
    schema_version: str


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
        key="du_life_insurers_tsy_level",
        series_id="BOGZ1FL543061105Q",
        description="Life Insurance Companies; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU broad-sector Treasury holdings level for the DS^T_DU direct allocator.",
    ),
    FredSeries(
        key="du_noncorporate_tsy_level",
        series_id="TSABSNNB",
        description="Nonfinancial Noncorporate Business; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU narrow-sector Treasury holdings level for the DS^T_DU direct allocator.",
    ),
    FredSeries(
        key="du_private_db_pensions_tsy_level",
        series_id="BOGZ1FL573061143Q",
        description="Private Defined Benefit Pension Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU broad-sector Treasury holdings level for the DS^T_DU direct allocator.",
    ),
    FredSeries(
        key="du_private_dc_pensions_tsy_level",
        series_id="BOGZ1FL573061133Q",
        description="Private Defined Contribution Pension Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU broad-sector Treasury holdings level for the DS^T_DU direct allocator.",
    ),
    FredSeries(
        key="du_pc_insurers_tsy_level",
        series_id="BOGZ1FL513061105Q",
        description="Property-Casualty Insurance Companies; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU broad-sector Treasury holdings level for the DS^T_DU direct allocator.",
    ),
    FredSeries(
        key="du_households_tsy_level",
        series_id="HNOTSAQ027S",
        description="Households and Nonprofit Organizations; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU narrow-sector Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_nonfinancial_corporates_tsy_level",
        series_id="NCBTSAQ027S",
        description="Nonfinancial Corporate Business; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU narrow-sector Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_sl_governments_tsy_level",
        series_id="BOGZ1FL213061103Q",
        description="State and Local Governments; Treasury Securities; Asset, Level",
        agg="last",
        notes="Domestic-public DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_mutual_funds_tsy_level",
        series_id="BOGZ1FL653061105Q",
        description="Mutual Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_etf_tsy_level",
        series_id="BOGZ1FL563061103Q",
        description="Exchange-Traded Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_closed_end_funds_tsy_level",
        series_id="BOGZ1FL553061103Q",
        description="Closed-End Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_sl_governments_pensions_tsy_level",
        series_id="BOGZ1FL223061143Q",
        description="State and Local Government Employee Defined Benefit Retirement Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="Domestic-public DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_federal_db_pensions_tsy_level",
        series_id="BOGZ1FL343061165Q",
        description="Federal Government Defined Benefit Retirement Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="Domestic-public DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_federal_dc_pensions_tsy_level",
        series_id="BOGZ1FL343061113Q",
        description="Federal Government Defined Contribution Retirement Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="Domestic-public DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_brokers_dealers_tsy_level",
        series_id="BOGZ1FL663061105Q",
        description="Security Brokers and Dealers; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_holding_companies_tsy_level",
        series_id="BOGZ1FL733061103Q",
        description="Holding Companies; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator).",
    ),
    FredSeries(
        key="du_gse_tsy_level",
        series_id="BOGZ1FL403061105Q",
        description="Government-Sponsored Enterprises; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator; reserve-adjacent, review label).",
    ),
    FredSeries(
        key="du_abs_issuers_tsy_level",
        series_id="BOGZ1FL673061103Q",
        description="Issuers of Asset-Backed Securities; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator; FRED id inferred from Z.1 code).",
    ),
    FredSeries(
        key="du_other_financial_tsy_level",
        series_id="BOGZ1FL503061123Q",
        description="Other Financial Business; Treasury Securities; Asset, Level",
        agg="last",
        notes="DU allocation-universe Treasury holdings level (DS^T_DU direct allocator; FRED id inferred from Z.1 code).",
    ),
    FredSeries(
        key="all_sectors_tsy_tx",
        series_id="BOGZ1FU893061105Q",
        description="All Sectors; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes=(
            "All-sector Treasury-security asset transactions. Used to construct the residual "
            "domestic nonbank DU Treasury-security purchase term by subtracting Fed, ROW, "
            "bank, and credit-union Treasury-security transactions."
        ),
    ),
    FredSeries(
        key="credit_unions_total_tsy_tx",
        series_id="BOGZ1FU473061105Q",
        description="Credit Unions; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes="Aggregate credit-union Treasury series. In Z.1, this equals natural-person credit-union Treasuries plus corporate credit-union Treasuries plus the NCUA capitalization deposit.",
    ),
    FredSeries(
        key="mmf_tsy_level",
        series_id="BOGZ1FL633061105Q",
        description="Money Market Funds; Treasury Securities; Asset, Level",
        agg="last",
        notes="Optional Z.1 L.210/L.121 MMF Treasury-security level used as an independent scale check for OFR MMF Treasury totals.",
    ),
    FredSeries(
        key="mmf_tsy_bills_level",
        series_id="BOGZ1FL633061110Q",
        description="Money Market Funds; Treasury Bills; Asset, Level",
        agg="last",
        notes="Optional Z.1 L.210 MMF Treasury-bill level used as a bills-only scale check when MMF support files include bill detail.",
    ),
    FredSeries(
        key="gse_tsy_tx",
        series_id="BOGZ1FA403061105Q",
        description="Government-Sponsored Enterprises; Treasury Securities; Asset, Transactions",
        agg="sum",
        notes="Optional Z.1 F.210 GSE Treasury-security transactions used only for the GSE/RRP boundary diagnostic.",
    ),
    FredSeries(
        key="gse_tsy_level",
        series_id="BOGZ1FL403061105Q",
        description="Government-Sponsored Enterprises; Treasury Securities; Asset, Level",
        agg="last",
        notes="Optional Z.1 L.210 GSE Treasury-security level used only for the GSE/RRP boundary diagnostic.",
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
        notes="Quarterly Z.1 sector-total Treasury transactions for the domestic nonfinancial block. Retained as a partial-sector diagnostic only; the DU-side Treasury-security purchase term is residual-defined from all-sector transactions less Fed, ROW, banks, and credit unions.",
    ),
    FredSeries(
        key="domestic_nonfinancial_tsy_level",
        series_id="BOGZ1FL383061105Q",
        description="Domestic Nonfinancial Sectors; Treasury Securities; Asset, Level",
        agg="last",
        notes="Quarterly Z.1 sector-total Treasury levels for the domestic nonfinancial block. Retained as a partial-sector diagnostic only; it is not the full DU perimeter.",
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
        key="fed_remit_mts",
        description="Monthly Treasury Statement deposits of earnings by Federal Reserve Banks.",
        agg="sum",
        notes="Preferred Treasury cash-flow source for Federal Reserve remittances. Built from MTS Table 4 net receipts for `Deposits of earnings by Federal Reserve Banks` and used to override the H.4.1 remittances-due/deferred-asset stock series when present.",
    ),
    LocalSeries(
        key="fed_tsy_coupon_interest_proxy",
        description="Quarterly Fed Treasury coupon-interest proxy built from SOMA holdings snapshots.",
        agg="sum",
        notes="Optional local support series. This is not downloaded from FRED; it is produced locally from SOMA holdings snapshots and used for Tier 1 Fed-corrected estimator variants.",
    ),
    LocalSeries(
        key="fed_tier1_component_extension_proxy",
        description="Quarterly Fed bill-discount plus FRN-interest component extension.",
        agg="sum",
        notes=(
            "Optional staged local support series. It is exported from support__fed_treasury_interest_components.csv "
            "as exact SOMA bill-discount plus FRN interest and feeds only explicit nondefault Fed-extension "
            "component-anchored rows."
        ),
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
        key="credit_union_tsy_coupon_interest_proxy",
        description="Quarterly credit-union Treasury coupon-interest proxy.",
        agg="sum",
        notes="Optional local support series. This is not downloaded from FRED; it is produced locally and used for depository-institution Tier 2 candidates that include natural-person credit unions in the RU block.",
    ),
    LocalSeries(
        key="bank_tsy_bill_discount_interest_proxy",
        description="Quarterly bank-sector Treasury bill-discount interest robustness proxy.",
        agg="sum",
        notes="Optional local support series. Produced from WAMEST bill shares, sector levels, Treasury bill WAM support, and the Treasury curve. Used only for noncoupon Treasury-interest robustness rows.",
    ),
    LocalSeries(
        key="row_tsy_bill_discount_interest_proxy",
        description="Quarterly rest-of-world Treasury bill-discount interest robustness proxy.",
        agg="sum",
        notes="Optional local support series. Produced from WAMEST bill shares, sector levels, Treasury bill WAM support, and the Treasury curve. Used only for noncoupon Treasury-interest robustness rows.",
    ),
    LocalSeries(
        key="credit_union_tsy_bill_discount_interest_proxy",
        description="Quarterly credit-union Treasury bill-discount interest robustness proxy.",
        agg="sum",
        notes="Optional local support series. Produced from WAMEST bill shares, sector levels, Treasury bill WAM support, and the Treasury curve. Used only for depository-institution noncoupon Treasury-interest robustness rows.",
    ),
    LocalSeries(
        key="bank_tier2_component_interest_proxy",
        description="Quarterly bank-sector component-anchored Tier 2 Treasury interest proxy.",
        agg="sum",
        notes=(
            "Optional staged local support series. It is exported from the Tier 2 component candidate and "
            "includes the bank allocation of official coupon-accrual, bill-discount, and FRN interest pools. "
            "When present it feeds the promoted canonical Tier 2 rows; the WAMEST/H.15 coupon proxy remains "
            "available through explicit H15 sensitivity rows."
        ),
    ),
    LocalSeries(
        key="row_tier2_component_interest_proxy",
        description="Quarterly rest-of-world component-anchored Tier 2 Treasury interest proxy.",
        agg="sum",
        notes=(
            "Optional staged local support series. It is exported from the Tier 2 component candidate and "
            "includes the ROW allocation of official coupon-accrual, bill-discount, and FRN interest pools. "
            "When present it feeds the promoted canonical Tier 2 rows; the WAMEST/H.15 coupon proxy remains "
            "available through explicit H15 sensitivity rows."
        ),
    ),
    LocalSeries(
        key="credit_union_tier2_component_interest_proxy",
        description="Quarterly credit-union component-anchored Tier 2 Treasury interest proxy.",
        agg="sum",
        notes=(
            "Optional staged local support series. It is exported from the Tier 2 component candidate and "
            "includes the credit-union allocation of official coupon-accrual, bill-discount, and FRN interest pools. "
            "When present it feeds the promoted canonical depository-institution Tier 2 row."
        ),
    ),
    LocalSeries(
        key="gse_on_rrp",
        description="Quarter-end ON RRP accepted amount for government-sponsored enterprises.",
        agg="last",
        notes="Optional local support series built from the New York Fed reverse-repo propositions API. Used only for the GSE/RRP boundary diagnostic, not the canonical estimator.",
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
    TreasuryDataset(
        key="interest_expense",
        endpoint="/v2/accounting/od/interest_expense",
        description="Interest Expense on the Public Debt Outstanding",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
    TreasuryDataset(
        key="frn_daily_indexes",
        endpoint="/v1/accounting/od/frn_daily_indexes",
        description="Floating Rate Notes daily index and accrued interest per $100",
        params={"page[size]": "10000", "sort": "-record_date"},
    ),
]

TRC_WINDOW = ("2002-01-01", "2025-12-31")


def _window_argv(window: tuple[str, str | None]) -> tuple[str, ...]:
    start, end = window
    return ("--start", start) if end is None else ("--start", start, "--end", end)


def _fred_input(
    key: str, series_id: str, scale: float, clock: str, description: str,
    window: tuple[str, str | None] = TRC_WINDOW,
) -> FiscusInput:
    return FiscusInput(
        key=key,
        dataset_id=f"fred.{series_id.lower()}",
        argv=("get-series", f"fred.{series_id.lower()}", *_window_argv(window)),
        usd_million_per_unit=scale,
        clock=clock,
        description=description,
        series_id=series_id,
    )


def _z1_input(
    key: str, code: str, description: str, window: tuple[str, str | None] = TRC_WINDOW,
    clock: str = "z1_calendar_quarter_transactions",
) -> FiscusInput:
    return FiscusInput(
        key=key,
        dataset_id=f"z1.{code.lower().replace('.', '_')}",
        argv=("z1-series", code, code[:2], *_window_argv(window)),
        usd_million_per_unit=1.0,
        clock=clock,
        description=description,
        series_id=code,
    )


# Treasury component of reserves (TRC) inputs. The DTS key is deliberately
# distinct from `dts_operating_cash_balance` above, which names the Table II
# deposits-and-withdrawals endpoint and is left unchanged.
TRC_FISCUS_INPUTS: list[FiscusInput] = [
    FiscusInput(
        key="dts_operating_cash_balance_table_i",
        dataset_id="fiscaldata.dts_operating_cash_balance",
        argv=(
            "fiscaldata-query", "fiscaldata.dts_operating_cash_balance",
            "--param", "filter=record_date:gte:2005-10-01,record_date:lte:2025-12-31",
            "--param", "page[size]=10000", "--max-pages", "100",
        ),
        usd_million_per_unit=1.0,
        clock="dts_business_day_close",
        description="Daily Treasury Statement Table I operating cash balance by account type",
    ),
    _fred_input("h41_tga_wednesday", "WDTGAL", 1.0, "h41_wednesday_level",
                "H.4.1 U.S. Treasury General Account, Wednesday level"),
    _fred_input("h41_reserve_balances_wednesday", "WRBWFRBL", 1.0, "h41_wednesday_level",
                "H.4.1 reserve balances with Federal Reserve Banks, Wednesday level"),
    _fred_input("h41_rrp_others_wednesday", "WLRRAOL", 1.0, "h41_wednesday_level",
                "H.4.1 reverse repurchase agreements with others, Wednesday level"),
    _fred_input("h41_rrp_foreign_official_wednesday", "WLRRAFOIAL", 1.0, "h41_wednesday_level",
                "H.4.1 reverse repurchase agreements with foreign official and international accounts, Wednesday level"),
    _fred_input("h41_foreign_official_deposits_wednesday", "WDFOL", 1.0, "h41_wednesday_level",
                "H.4.1 foreign official deposits with Federal Reserve Banks, Wednesday level"),
    _fred_input("h41_custody_marketable_treasury_wednesday", "WMTSECL1", 1.0, "h41_wednesday_level",
                "H.4.1 marketable Treasury securities held in custody for foreign official and international accounts, Wednesday level"),
    _fred_input("h3_total_reserves_monthly", "TOTRESNS", 1000.0, "h3_monthly_average",
                "H.3 total reserves of depository institutions, monthly average, billions"),
    _z1_input("z1_reserves_transactions", "FU713113003.Q",
              "Central bank; depository institution reserves, excluding FHLB deposits; liability, transactions"),
    _z1_input("z1_sfp_transactions", "FU713123043.Q",
              "Central bank; deposits in Treasury temporary supplementary financing account; liability, transactions"),
    _z1_input("z1_us_chartered_reserves_transactions", "FU763013005.Q",
              "U.S.-chartered depository institutions; depository institution reserves; asset, transactions"),
]
TRC_REGISTRY = FiscusRegistry(
    name="trc", inputs=tuple(TRC_FISCUS_INPUTS), input_dir=Path("data/raw/fiscus"),
    manifest=Path("data/raw/fiscus/trc_inputs_manifest.json"), schema_version="trc_fiscus_inputs_v1",
)


@dataclass(frozen=True)
class H41Row:
    """One H.4.1 Table 1 row, Wednesday level, USD million.

    ``parent`` places the row in the published Table 1 hierarchy. ``role`` is
    ``factor`` (enters the signed ledger), ``check`` (a published parent or total
    that only verifies its factor descendants), ``memo`` (a published child of a
    factor, displayed but never summed), or ``outcome`` (reserve balances).
    ``introduced`` dates a row that enters Table 1 after the ledger start;
    ``discontinued`` marks a source series that ends before the latest
    Wednesday; ``terminal_nonzero`` explains a removed row whose last published
    value is not zero.
    """

    key: str
    series_id: str
    label: str
    parent: str | None
    role: str
    introduced: str | None = None
    discontinued: bool = False
    terminal_nonzero: str | None = None


H41_LEDGER_START = "2002-12-18"
_SUPPLY, _ABSORB, _RBC, _SHO = "total_supplying", "total_absorbing", "reserve_bank_credit", "securities_held_outright"
_DEP = "deposits_other_than_reserve_balances"
H41_TABLE1_ROWS: tuple[H41Row, ...] = (
    H41Row("total_supplying", "WTFSRFL", "Total factors supplying reserve funds", None, "check"),
    H41Row("total_absorbing", "WTFORBAFL", "Total factors, other than reserve balances, absorbing reserve funds",
           None, "check"),
    H41Row("reserve_balances", "WRBWFRBL", "Reserve balances with Federal Reserve Banks", None, "outcome"),
    H41Row(_RBC, "WOFSRBRBC", "Reserve Bank credit", _SUPPLY, "check"),
    H41Row(_SHO, "WSHOSHO", "Securities held outright", _RBC, "check"),
    H41Row("treasury_securities", "WSHOTSL", "U.S. Treasury securities", _SHO, "factor"),
    H41Row("treasury_inflation_compensation", "WSHOICL", "U.S. Treasury securities: inflation compensation",
           "treasury_securities", "memo"),
    H41Row("federal_agency_debt", "WSHOFADSL", "Federal agency debt securities", _SHO, "factor"),
    H41Row("mortgage_backed_securities", "WSHOMCB", "Mortgage-backed securities", _SHO, "factor"),
    H41Row("unamortized_premiums", "WUPSHO", "Unamortized premiums on securities held outright", _RBC, "factor"),
    H41Row("unamortized_discounts", "WUDSHO", "Unamortized discounts on securities held outright", _RBC, "factor"),
    H41Row("repurchase_agreements", "WORAL", "Repurchase agreements", _RBC, "factor"),
    H41Row("term_auction_credit", "RESPPALTNWW", "Term auction credit", _RBC, "factor"),
    H41Row("loans", "WLCFLL", "Loans", _RBC, "factor"),
    H41Row("cpff_llc", "H0RESPPAACHNWW", "Net portfolio holdings of Commercial Paper Funding Facility LLC", _RBC,
           "factor", discontinued=True),
    H41Row("mmiff_llcs", "H0RESPPAAMMIHNWW",
           "Net portfolio holdings of LLCs funded through the Money Market Investor Funding Facility", _RBC, "factor",
           discontinued=True),
    H41Row("maiden_lane_llc", "WAML1L", "Net portfolio holdings of Maiden Lane LLC", _RBC, "factor",
           discontinued=True),
    H41Row("maiden_lane_ii_llc", "WAML2L", "Net portfolio holdings of Maiden Lane II LLC", _RBC, "factor",
           discontinued=True),
    H41Row("maiden_lane_iii_llc", "WAML3L", "Net portfolio holdings of Maiden Lane III LLC", _RBC, "factor",
           discontinued=True),
    H41Row("talf_llc", "H0RESPPAATALHNWW", "Net portfolio holdings of TALF LLC", _RBC, "factor", discontinued=True,
           terminal_nonzero="Row removed after 2014-11-05 at USD 24 million; published totals close with zero thereafter"),
    H41Row("aia_alico_preferred_interests", "H0RESPPAAAAAINWW",
           "Preferred interests in AIA Aurora LLC and ALICO Holdings LLC", _RBC, "factor", discontinued=True,
           terminal_nonzero="Row removed after 2011-01-12 with the AIG recapitalization; published totals close with zero thereafter"),
    H41Row("cpff_ii_llc", "H41RESPPAAC2HNWW", "Net portfolio holdings of Commercial Paper Funding Facility II LLC",
           _RBC, "factor", discontinued=True),
    H41Row("corporate_credit_facilities_llc", "H41RESPPAABNWW", "Net portfolio holdings of Corporate Credit Facilities LLC",
           _RBC, "factor", discontinued=True),
    H41Row("municipal_liquidity_facility_llc", "H41RESPPAADHNWW",
           "Net portfolio holdings of Municipal Liquidity Facility LLC", _RBC, "factor", discontinued=True),
    H41Row("ms_facilities_llc", "H41RESPPAAENWW",
           "Net portfolio holdings of MS Facilities LLC (Main Street Lending Program)", _RBC, "factor"),
    H41Row("talf_ii_llc", "H41RESPPAATAL2HNWW", "Net portfolio holdings of TALF II LLC", _RBC, "factor",
           discontinued=True),
    H41Row("float", "WOFSRBFL", "Float", _RBC, "factor"),
    H41Row("central_bank_liquidity_swaps", "SWPT", "Central bank liquidity swaps", _RBC, "factor"),
    H41Row("other_federal_reserve_assets", "WOFRAL", "Other Federal Reserve assets", _RBC, "factor"),
    H41Row("foreign_currency_denominated_assets", "WFCDA", "Foreign currency denominated assets", _SUPPLY, "factor"),
    H41Row("gold_stock", "WOFSRBGSL", "Gold stock", _SUPPLY, "factor"),
    H41Row("sdr_certificate_account", "WOSDRL", "Special drawing rights certificate account", _SUPPLY, "factor"),
    H41Row("treasury_currency_outstanding", "WTCOL", "Treasury currency outstanding", _SUPPLY, "factor"),
    H41Row("currency_in_circulation", "WCICL", "Currency in circulation", _ABSORB, "factor"),
    H41Row("reverse_repurchase_agreements", "WLRRAL", "Reverse repurchase agreements", _ABSORB, "check"),
    H41Row("rrp_foreign_official", "WLRRAFOIAL", "Reverse repurchase agreements: foreign official and international accounts",
           "reverse_repurchase_agreements", "factor"),
    H41Row("rrp_others", "WLRRAOL", "Reverse repurchase agreements: others", "reverse_repurchase_agreements", "factor"),
    H41Row("treasury_cash_holdings", "WOFDRBTHL", "Treasury cash holdings", _ABSORB, "factor"),
    H41Row(_DEP, "WOFDRBORBL", "Deposits with F.R. Banks, other than reserve balances", _ABSORB, "check"),
    H41Row("term_deposits", "TERMT", "Term deposits held by depository institutions", _DEP, "factor"),
    H41Row("treasury_general_account", "WDTGAL", "U.S. Treasury, General Account", _DEP, "factor"),
    H41Row("supplementary_financing_account", "WDSFAL", "U.S. Treasury, Supplementary Financing Account", _DEP,
           "factor", introduced="2008-09-17", discontinued=True),
    H41Row("foreign_official_deposits", "WDFOL", "Foreign official", _DEP, "factor"),
    H41Row("service_related_deposits", "H0RESPPLLDDSNWW", "Service-related", _DEP, "factor", discontinued=True,
           terminal_nonzero="Row removed after 2012-07-11 with the end of required clearing balances; published totals close with zero thereafter"),
    H41Row("other_deposits", "WLODL", "Other", _DEP, "factor"),
    H41Row("aig_disposition_funds_held_as_agent", "H0RESPPLLANWW",
           "Funds from American International Group, Inc. asset dispositions, held as agent", _ABSORB, "factor",
           discontinued=True,
           terminal_nonzero="Row removed after 2011-01-12 with the AIG recapitalization; published totals close with zero thereafter"),
    H41Row("treasury_contributions_to_credit_facilities", "H41RESH4ENWW", "Treasury contributions to credit facilities",
           _ABSORB, "factor"),
    H41Row("other_liabilities_and_capital", "WOLCL", "Other liabilities and capital", _ABSORB, "factor"),
)
H41_LEDGER_FISCUS_INPUTS: list[FiscusInput] = [
    *(_fred_input(row.key, row.series_id, 1.0, "h41_wednesday_level", f"H.4.1 Table 1: {row.label}, Wednesday level",
                  window=(H41_LEDGER_START, None)) for row in H41_TABLE1_ROWS),
    _z1_input("z1_reserves_level", "FL713113003.Q",
              "Central bank; depository institution reserves, excluding FHLB deposits; liability, level",
              window=(TRC_WINDOW[0], None), clock="z1_calendar_quarter_end_level"),
    _z1_input("z1_reserves_transactions", "FU713113003.Q",
              "Central bank; depository institution reserves, excluding FHLB deposits; liability, transactions",
              window=(TRC_WINDOW[0], None)),
]
H41_LEDGER_REGISTRY = FiscusRegistry(
    name="h41-ledger", inputs=tuple(H41_LEDGER_FISCUS_INPUTS), input_dir=Path("data/raw/fiscus/h41_ledger"),
    manifest=Path("data/raw/fiscus/h41_ledger/inputs_manifest.json"), schema_version="h41_ledger_fiscus_inputs_v1",
)
# Weekly inputs retain event clocks; monthly fund positions never enter this registry.
WEEKLY_TRC_WINDOW = ("2003-07-02", "2025-12-31")
WEEKLY_TRC_OVERLAY = Path("config/fiscus_weekly_trc.yml")
# Event crosswalk only where a dated Treasury statement independently names facility cash.
# The DTS row must still match the amount/account/date; factor residuals stay candidate-only.
WEEKLY_TRC_INTERNAL_MATCHES = (
    {"date": "2020-05-11", "transaction_type": "Withdrawals", "amount": "37500",
     "source_url": "https://home.treasury.gov/news/press-releases/sm1007",
     "meaning": "Treasury's May 12 statement identifies 37.5 billion transmitted the preceding day to the corporate-credit SPV"},
)
WEEKLY_TRC_REGISTRY = FiscusRegistry(
    name="weekly-trc", input_dir=Path("data/raw/fiscus/weekly_trc"),
    manifest=Path("data/raw/fiscus/weekly_trc/inputs_manifest.json"),
    schema_version="weekly_trc_fiscus_inputs_v1",
    inputs=(
        FiscusInput("soma", "soma.treasury_holdings", ("soma-holdings",), 0.000001,
                    "wednesday_asof_snapshot", "CUSIP-level SOMA par and inflation compensation",
                    snapshot_window=WEEKLY_TRC_WINDOW),
        FiscusInput("auctions", "fiscaldata.auctions_query", (
            "fiscaldata-query", "fiscaldata.auctions_query", "--param",
            "filter=issue_date:gte:1979-11-01,issue_date:lte:2025-12-31",
            "--param", "page[size]=10000", "--max-pages", "100"),
            0.000001, "issue_and_maturity_date", "Auction allotments and security schedules"),
        FiscusInput("remittances", "fiscaldata.dts_deposits_withdrawals", (
            "fiscaldata-query", "fiscaldata.dts_deposits_withdrawals", "--param",
            "filter=record_date:gte:2005-10-03,record_date:lte:2025-12-31,transaction_catg:eq:Federal Reserve Earnings",
            "--param", "page[size]=10000", "--max-pages", "100"),
            1.0, "dts_record_date", "DTS Table II Federal Reserve Earnings cash deposits"),
        FiscusInput("internal_dts", "fiscaldata.dts_deposits_withdrawals", (
            "fiscaldata-query", "fiscaldata.dts_deposits_withdrawals", "--param",
            "filter=record_date:gte:2020-01-01,record_date:lte:2025-12-31,transaction_catg:eq:ESF - Economic Recovery Programs",
            "--param", "page[size]=10000", "--max-pages", "100"),
            1.0, "dts_record_date", "Dated ESF cash candidates for Treasury-Fed facility matching"),
        FiscusInput("frn", "fiscaldata.frn_daily_indexes", (
            "fiscaldata-query", "fiscaldata.frn_daily_indexes", "--param",
            "filter=record_date:lte:2025-12-31", "--param", "page[size]=10000",
            "--max-pages", "100"), 0.000001, "daily_accrual_date", "FRN coupon rates by accrual day",
            native_units="interest per USD 100 and field-specific rates"),
        _fred_input("on_rrp", "RRPONTSYD", 1000.0, "business_day_take_up", "ON RRP daily take-up",
                    window=("2003-06-25", "2025-12-31")),
        FiscusInput("cpi", "fred.cpiaucns", ("get-series", "fred.cpiaucns", "--start", "1996-01-01", "--end", "2025-12-31"),
                    1.0, "monthly_reference_cpi", "CPI-U NSA for TIPS index ratios", series_id="CPIAUCNS",
                    native_units="index 1982-1984=100, not seasonally adjusted"),
    ),
)
FISCUS_REGISTRIES = {registry.name: registry for registry in (TRC_REGISTRY, H41_LEDGER_REGISTRY, WEEKLY_TRC_REGISTRY)}

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
