# IPO Validation Pipeline

A lightweight Python-based data validation tool that compares actual usage data from Epicor ERP against forecasted usage sent to IP&O (Inventory Planning & Optimization) software. Identifies data integrity issues, forecast variances, and critical discrepancies.

## 🎯 Overview

This pipeline replaces a complex 481-line SQL view with a clean, modular Python architecture that:
- Queries raw data from `PartUsage` and `IPOValidation` tables
- Normalizes and transforms both datasets
- Performs full outer join comparison
- Categorizes variances by severity
- Exports results for analysis in Excel, Power BI, or other tools

## 📋 Features

- **Simple & Lightweight**: Minimal dependencies, straightforward logic
- **Clear Organization**: Chronological structure with well-defined sections
- **Detailed Logging**: Structured debug prints at every pipeline step
- **Configurable**: JSON-based configuration for all settings
- **Flexible Output**: CSV, Excel, or Parquet formats
- **Business Rules Built-In**: Location mapping and usage calculation logic

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Access to StoneAge Manufacturing SQL Server database
- ODBC Driver 17 for SQL Server (or compatible)

### Installation

1. **Clone or download this repository**

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify database access**
   
   The `config.json` file is pre-configured for Windows Authentication. If needed, update:
   ```json
   {
     "database": {
       "server": "SAI-AZRDW02",
       "database": "MULE_STAGE",
       "use_windows_auth": true
     }
   }
   ```

### Run the Pipeline

```bash
python main.py
```

The pipeline will execute all validation steps and save results to `validation_results.csv`.

## 📂 Project Structure

```
ipo_validation/
├── config.json          # Configuration (database, mappings, rules)
├── database.py          # Database connection and query functions
├── utils.py             # Data transformation utilities
├── main.py              # Pipeline orchestration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### File Descriptions

**`config.json`**
- Database connection settings
- Date range configuration
- Location mappings (Plant → Location name)
- Business rules (usage calculation)
- Output options

**`database.py`**
- `DatabaseConnection` class for SQL Server connectivity
- Query functions for `PartUsage`, `IPOValidation`, and metadata tables
- Connection pooling and cleanup

**`utils.py`**
- Section 1: Parsing (composite key extraction)
- Section 2: Normalization (data standardization)
- Section 3: Filtering (exclusion rules)
- Section 4: Comparison (variance calculation)
- Section 5: Categorization (variance classification)

**`main.py`**
- Pipeline orchestration (7-step process)
- Configuration loading
- Summary statistics generation
- Results export

## 🔧 Configuration

### Date Range

Set the validation period in `config.json`:

```json
"validation": {
  "start_date": "2020-01-31",
  "end_date": "2025-08-31",
  "companies": ["SAINC", "SAUK", "SANL"],
  "excluded_companies": ["SAFR"]
}
```

### Location Mappings

Plant codes are mapped to business-friendly location names:

| Company | Plant Code | Location Name |
|---------|------------|---------------|
| SAINC | SAILA | StoneAge Louisiana |
| SAINC | SAIOH, SAICTN | StoneAge Ohio |
| SAINC | SAITX | StoneAge Texas |
| SAINC | MfgSys | StoneAge, Inc. |
| SAUK | MfgSys | StoneAge Europe Ltd |
| SANL | MfgSys | StoneAge Netherlands B.V. |

### Usage Calculation Rules

- **SAINC MfgSys**: `ICUsage + IndirectUsage + DirectUsage`
- **All Other Locations**: `DirectUsage` only

These rules are defined in `config.json` under `rules.usage_calculation`.

### Exclusions (Optional)

To filter out inactive parts, non-stock items, and low-usage parts:

```json
"options": {
  "apply_exclusions": true
}
```

**Note**: Exclusions are disabled by default for simplicity. When enabled, the pipeline queries part metadata and filters based on:
- Inactive parts (`InActive = 1`)
- Runout parts (`Runout = 1`)
- Non-stock items (`NonStock = 1`)
- Raw materials or consumables (`ClassID IN ('RAW', 'CSM')`)

### Output Options

```json
"options": {
  "output_format": "csv",      // Options: "csv", "excel", "parquet"
  "output_path": "validation_results.csv"
}
```

## 📊 Pipeline Steps

The validation pipeline executes in **7 sequential steps**:

```
[STEP 1/7] DATABASE CONNECTION
    → Connect to SQL Server using config settings

[STEP 2/7] DATA EXTRACTION
    → Query PartUsage table (Epicor actual usage)
    → Query IPOValidation table (sent to IP&O)

[STEP 3/7] NORMALIZE PARTUSAGE
    → Parse company_plant_part composite keys
    → Map plant codes to location names
    → Calculate usage based on business rules
    → Normalize dates to end-of-month

[STEP 4/7] NORMALIZE IPOVALIDATION
    → Standardize column names
    → Normalize dates to end-of-month

[STEP 5/7] APPLY EXCLUSIONS (Optional)
    → Filter excluded parts (if enabled)

[STEP 6/7] COMPARE DATASETS
    → FULL OUTER JOIN on (company, location, part_num, period)
    → Calculate variance (ipo_usage - actual_usage)
    → Calculate variance percentage

[STEP 7/7] CATEGORIZE VARIANCES
    → Assign variance categories
    → Generate distribution statistics
```

## 📈 Output

### Output Columns

| Column | Description |
|--------|-------------|
| `company` | Company code (SAINC, SAUK, SANL) |
| `location` | Business-friendly location name |
| `part_num` | Part number |
| `period` | Period end date (last day of month) |
| `actual_usage` | Calculated usage from Epicor PartUsage |
| `ipo_usage` | Usage value sent to IP&O software |
| `variance` | Difference (ipo_usage - actual_usage) |
| `variance_percent` | Percentage variance (handles edge cases) |
| `absolute_variance` | Absolute value of variance |
| `variance_category` | Category classification (see below) |

### Variance Categories

| Category | Severity | Description |
|----------|----------|-------------|
| `PERFECT_MATCH` | ✅ None | Exact data alignment between systems |
| `MISSING_FROM_IPO` | ❌❌ Critical | Actual usage occurred but IP&O received zero (underforecast) |
| `MISSING_FROM_USAGE` | ❌ High | IP&O has data but no actual usage recorded (overforecast) |
| `MORE_IN_USAGE` | ⚠️ Medium | Actual usage higher than IP&O (partial underforecast) |
| `MORE_IN_IPO` | ⚠️ Low | IP&O shows higher usage than actual (partial overforecast) |

### Summary Statistics

After execution, the pipeline prints detailed summary statistics:

- Total records processed
- Variance counts and percentages
- Critical issue counts
- Breakdown by variance category
- Breakdown by company
- Date range coverage
- Variance magnitude statistics

## 🔍 Debug Output

The pipeline provides structured logging with prefixed tags:

```
[CONFIG]          - Configuration loading
[DATABASE]        - Database connection and queries
[PARSING]         - Composite key parsing
[NORMALIZE]       - Data normalization steps
[EXCLUSIONS]      - Exclusion filtering (if enabled)
[COMPARISON]      - Dataset comparison and variance calculation
[CATEGORIZATION]  - Variance categorization
[OUTPUT]          - File output operations
[SUMMARY]         - Final statistics
[METRICS]         - Performance metrics
[BREAKDOWN]       - Distribution breakdowns
```

Each step shows:
- Input/output record counts
- Processing progress
- Data quality metrics
- Timing information

## 🛠️ Troubleshooting

### Connection Issues

**Error: "Can't open lib 'ODBC Driver 17 for SQL Server'"**

Install the ODBC driver:
- Windows: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- Or update `DB_DRIVER` in `config.json` to match your installed driver

**Error: "Login failed for user"**

For Windows Authentication:
```json
"use_windows_auth": true
```

For SQL Authentication:
```json
"use_windows_auth": false,
"username": "your_username",
"password": "your_password"
```

**Error: "Invalid object name 'PartUsage'" or "'IPOValidation'"**

Ensure:
- Tables exist in the specified database
- Your user has SELECT permissions
- Database name is correct in `config.json`

### Performance Issues

**Pipeline runs slowly**

- Reduce date range in `config.json`
- Check database server performance
- Consider adding indexes to `PartUsage` and `IPOValidation` tables

**Memory errors with large datasets**

- Use Parquet output format instead of CSV
- Process data in smaller date ranges
- Increase available system memory

### Data Quality Issues

**"UNMAPPED_LOCATION_COMPANY_PLANT" appears in results**

A plant code isn't mapped in `config.json`. Add the mapping:
```json
"mappings": {
  "locations": {
    "COMPANY": {
      "PLANT": "Location Name"
    }
  }
}
```

**Unexpected variance percentages (999.99 or -999.99)**

These are flag values:
- `999.99`: Actual is zero, IPO has data (infinite variance)
- `-999.99`: IPO is zero, Actual has data (missing from IPO)

## 📊 Typical Performance

Expected performance metrics (hardware-dependent):

- **Processing Speed**: 10,000-50,000 records/second
- **5-Year Dataset**: <30 seconds total execution
- **Memory Usage**: 200-500 MB for typical datasets

## 🔄 Migration from SQL View

This Python pipeline replaces the original `vw_ipo_validation.sql` view with several advantages:

✅ **Modularity**: Each transformation step is a separate function  
✅ **Testability**: Easy to unit test individual components  
✅ **Debuggability**: Can inspect intermediate DataFrames  
✅ **Flexibility**: Easy to add new rules or modify existing logic  
✅ **Performance**: Can parallelize or optimize specific steps  
✅ **Maintainability**: Clear structure, well-documented business logic  

## 📝 Next Steps

After running the pipeline:

1. **Open results in Excel or Power BI**
   ```bash
   # Results saved to: validation_results.csv
   ```

2. **Filter by variance category** to focus on specific issues
   - Start with `MISSING_FROM_IPO` (critical issues)
   - Review `MISSING_FROM_USAGE` (overforecast issues)

3. **Sort by absolute_variance** to find largest discrepancies

4. **Analyze trends over time** using the `period` column

5. **Drill down by company or location** for targeted analysis

## 🤝 Support

For issues or questions:
- **Application issues**: Review error messages in console output
- **Data discrepancies**: Check business rules in `config.json`
- **Database access**: Contact your database administrator

## 📄 License

Internal use only - StoneAge Manufacturing

---

**Built with ❤️ for StoneAge Manufacturing**  
*Replacing bloated SQL with clean, maintainable Python*

