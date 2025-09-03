# IP&O Validation System

## Overview

This system validates data integrity between StoneAge Manufacturing's Epicor ERP system (actual inventory usage) and their IP&O (Inventory Planning & Optimization) software (forecasting data). The validation prevents multi-million dollar forecasting errors by ensuring exact data alignment between systems.

## Business Problem

StoneAge discovered a 2-year bug in their IP&O software that was chronically underforecasting part usage, costing millions of dollars. The root cause was inconsistent data being fed from Epicor ERP to the IP&O system, leading to flawed forecasting models.

## Solution Architecture

The system compares two data sources:
- **PartUsage Table**: Actual part consumption from Epicor ERP (source of truth)
- **IPOValidation Table**: Data sent to IP&O software for forecasting

The main deliverable is `vw_ipo_validation_detail` - a comprehensive view designed as a Power BI data source.

## Business Rules

### Usage Calculation Rules
- **SAINC MfgSys/Durango Locations**: `CalculatedUsage = ICUsage + IndirectUsage + DirectUsage`
- **All Other Locations**: `CalculatedUsage = DirectUsage only`

### Location Mapping
- **SAINC SAILA** → `StoneAge Louisiana`
- **SAINC SAIOH** → `StoneAge Ohio`
- **SAINC SAITX** → `StoneAge Texas`
- **SAINC MfgSys/Other** → `StoneAge, Inc.`
- **SANL** → `StoneAge Netherlands B.V.`
- **SAUK** → `StoneAge Europe Ltd`

## Data Sources

### PartUsage Table (Epicor ERP Data)
- **Structure**: Composite key `company_plant_warehouse_part` format
- **Example**: `"SAINC_MfgSys_DGO01_ABX 326"`
- **Data Pattern**: Sparse (only non-zero usage records)
- **Time Range**: November 2018 - January 2025

### IPOValidation Table (IP&O Feed Data)
- **Structure**: Clean normalized fields (Company, Location, Product, Period, Qty)
- **Data Pattern**: Dense (complete part master list including zeros)
- **Time Range**: January 2020 - August 2025

## View Schema: vw_ipo_validation_detail

### Business Identity (4 columns)
- `company_code` - Company identifier (SAINC, SANL, SAUK)
- `location_name` - Full location name
- `product_code` - Part number/SKU
- `validation_date` - Month-end validation date

### Core Validation Data (5 columns)
- `actual_usage` - True usage from Epicor ERP
- `ipo_usage` - Usage sent to IP&O system
- `variance_amount` - Difference (IPO - Actual)
- `variance_percent` - Percentage variance
- `absolute_variance` - Absolute value of variance

### Classification (2 columns)
- `variance_category` - Issue classification
- `record_type` - Data availability pattern

### Boolean Flags for Power BI (3 columns)
- `is_critical_issue` - Critical data integrity problems
- `is_perfect_match` - Exact matches between systems
- `has_variance` - Any variance exists

### Debug Components (5 columns)
- `ic_usage_amount` - Inventory Control usage
- `indirect_usage_amount` - Indirect usage
- `direct_usage_amount` - Direct usage
- `rent_usage_amount` - Rental usage
- `epicor_original_key` - Source system reference

### Date Intelligence (13 columns)
**Basic Components:**
- `validation_year`, `validation_month`, `validation_quarter`, `validation_day`
- `month_name`, `month_abbreviation`

**Period Keys:**
- `period_key` - YYYYMM format (202408)
- `period_year_month` - YYYY-MM format (2024-08)
- `quarter_key` - Format: 2024Q3

**Relative Logic:**
- `is_current_month`, `is_previous_month`, `is_current_quarter`, `is_previous_quarter`, `is_current_year`
- `months_from_current`, `quarters_from_current`

**Power BI Optimization:**
- `sort_order` - Sequential numbering for proper sorting
- `is_month_complete` - Data completeness flag
- `days_in_month` - Calendar month information

## Variance Categories

- **PERFECT_MATCH** - Exact data alignment ✅
- **MATCH_ZERO** - Both systems correctly show zero ✅
- **HAS_VARIANCE** - Minor discrepancies ⚠️
- **CRITICAL_IPO_ORPHAN** - IP&O has data, no actual usage ❌
- **CRITICAL_MISSING_FROM_IPO** - Actual usage occurred, IP&O got zero ❌❌

## Record Types

- **BOTH_EXIST** - Data in both systems (normal comparison)
- **IPO_ONLY** - Only IP&O has data (expected for zero-usage parts)
- **PARTUSAGE_ONLY** - Only actual usage exists (critical missing from IP&O)

## Query Structure

### Section 1: PartUsage Normalization CTE
Transforms raw Epicor data:
- Parses composite `company_plant_warehouse_part` field
- Maps location codes to business names
- Applies usage calculation business rules
- Extracts product codes

### Section 2: IPOValidation Normalization CTE
Standardizes IP&O data:
- Normalizes date formats to month-end
- Preserves original period for debugging

### Section 3: Full Comparison Analysis CTE
Performs comprehensive comparison:
- FULL OUTER JOIN to capture all scenarios
- Calculates variances and percentages
- Categorizes issues by business impact
- Flags critical data integrity problems

### Section 4: Final Output with Power BI Schema
Delivers Power BI-ready dataset:
- snake_case column naming
- Complete date intelligence
- Boolean flags for easy filtering
- All time periods included (no date restrictions)

## Power BI Integration

The view is designed for direct Power BI consumption:
- **32 total columns** optimized for reporting
- **All historical data** included for trending
- **Dynamic date filtering** without code changes
- **Boolean flags** for easy measure creation
- **Raw variance data** for custom threshold calculations

## Data Integrity Monitoring

Critical issues to monitor:
1. **CRITICAL_MISSING_FROM_IPO** - Highest priority (underforecasting risk)
2. **CRITICAL_IPO_ORPHAN** - Medium priority (overforecasting risk)
3. **Variance patterns** - Track data quality trends over time

## Expected Results

In a healthy system:
- Majority of records show **PERFECT_MATCH** or **MATCH_ZERO**
- Critical issues are rare and investigated immediately
- Variance trends improve over time
- Data completeness flags show consistent patterns

The system successfully prevents the multi-million dollar forecasting errors that occurred due to data integrity issues between Epicor ERP and IP&O systems.
