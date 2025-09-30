# IP&O Validation System

## Overview

This system validates data integrity between StoneAge Manufacturing's Epicor ERP system (actual inventory usage) and their IP&O (Inventory Planning & Optimization) software (forecasting data). The validation prevents multi-million dollar forecasting errors by ensuring exact data alignment between systems.

The system was created to solve a critical 2-year bug in StoneAge's IP&O software that was chronically underforecasting part usage, costing millions of dollars due to inconsistent data being fed from Epicor ERP to the IP&O system.

## Data Sources

### PartUsage Table (Epicor ERP Data)
- **Structure**: Composite key `company_plant_part` format (e.g., `"SAINC_MfgSys_ABX 326"`)
- **Data Pattern**: Sparse (only non-zero usage records)
- **Time Range**: November 2018 - August 2025
- **Source**: Epicor ERP system (source of truth for actual inventory usage)

### IPOValidation Table (IP&O Feed Data)
- **Structure**: Clean normalized fields (Company, Location, Product, Period, Qty)
- **Data Pattern**: Dense (complete part master list including zeros)
- **Time Range**: January 2020 - August 2025
- **Source**: Data sent to IP&O software for forecasting

## Core Functionality

The system performs comprehensive comparison analysis using a FULL OUTER JOIN to identify:
- **Perfect matches** between systems (including zero-to-zero matches)
- **Data missing** from either system
- **Over-forecasting** (IP&O shows higher usage than actual)
- **Under-forecasting** (actual usage higher than IP&O data)

## Query Versions

The system includes two SQL query versions:

### vw_ipo_validation_detail.sql (Production View)
- **Purpose**: Complete historical dataset for Power BI
- **Data Range**: All periods from January 2020 - August 2025
- **Structure**: Enhanced with Plant field for improved exclusion logic
- **Use Case**: Power BI data source with full date intelligence for trending and analysis

### test.sql (Single Period Query)
- **Purpose**: Focused validation for specific month
- **Data Range**: Filtered to August 2025 only (`WHERE Period = '2025-08-31'`)
- **Use Case**: Quick validation checks and ad-hoc analysis

Both queries implement identical business logic for exclusions, usage calculations, and variance categorization. The only differences are:
1. Date filtering (all periods vs. single month)
2. Plant field extraction in normalization CTEs (vw_ipo_validation_detail.sql only)

## Comprehensive Part Exclusion System

The system implements multiple layers of business rules to exclude parts that should not be included in IPO validation:

### 1. IPOMethod-Based Exclusions
Parts are excluded if they have specific IP&O processing methods:
- **Exception**: Parts requiring special handling or manual review
- **Min/Max**: Parts managed by minimum/maximum inventory levels
- **New- No History**: Parts with less than 16 months of usage history

### 2. Part Status Exclusions
Parts are excluded based on their lifecycle status in Epicor:
- **NonStock**: Parts marked as non-stock items
- **InActive**: Parts marked as inactive in the system
- **Runout**: Parts that have been run out or discontinued

### 3. Material Classification Exclusions
- **RAW Materials**: Parts with ClassID = 'RAW' (raw materials that don't need forecasting)
- **CSM Materials**: Parts with ClassID = 'CSM' (consumable materials that don't need forecasting)

### 4. Data Quality Exclusions
- **Question Mark Parts**: Parts with question marks (?) in their part numbers (typically test or placeholder parts)

### 5. Usage-Based Exclusions
- **Low Usage Parts**: Parts with ≤ 2 total usage over the past 12 months are automatically excluded from IPO validation

### 6. Geographic Exclusions
- **SAFR (StoneAge France)**: Currently excluded because France is not yet integrated with the IP&O system

## Business Rules

### Usage Calculation Logic
The system applies different usage calculation rules based on location:

**SAINC Manufacturing Locations (MfgSys)**:
```
CalculatedUsage = ICUsage + IndirectUsage + DirectUsage
```

**All Other Locations**:
```
CalculatedUsage = DirectUsage
```

### Location Name Mapping
The system maps Epicor plant codes to business-friendly location names:
- `SAINC_SAILA` → `StoneAge Louisiana`
- `SAINC_SAIOH/SAICTN` → `StoneAge Ohio`
- `SAINC_SAITX` → `StoneAge Texas`
- `SAINC_MfgSys/Other` → `StoneAge, Inc.`
- `SANL` → `StoneAge Netherlands B.V.`
- `SAUK` → `StoneAge Europe Ltd`
- `SAFR` → `StoneAge France` (excluded from validation)

## Output Schema

The following schema applies to both query versions (38 total columns):

### Business Identity (4 columns)
- `company_code` - Company identifier (SAINC, SANL, SAUK)
- `location_name` - Full business location name
- `product_code` - Part number/SKU
- `validation_date` - Month-end validation date

### Core Validation Data (5 columns)
- `actual_usage` - True usage from Epicor ERP
- `ipo_usage` - Usage sent to IP&O system
- `variance_amount` - Difference (IPO - Actual)
- `variance_percent` - Percentage variance calculation
- `absolute_variance` - Absolute value of variance

### Issue Classification (1 column)
- `variance_category` - Categorizes data integrity issues

### Power BI Boolean Flags (3 columns)
- `is_critical_issue` - Flags MISSING_FROM_USAGE and MISSING_FROM_IPO issues
- `is_perfect_match` - Flags exact matches between systems
- `has_variance` - Flags any variance between systems

### Debug Components (6 columns)
- `ic_usage_amount` - Inventory Control usage component
- `indirect_usage_amount` - Indirect usage component
- `direct_usage_amount` - Direct usage component
- `rent_usage_amount` - Rental usage component
- `epicor_original_key` - Original Epicor composite key for traceability
- `ipo_method` - IPOMethod classification for debugging exclusion logic

### Date Intelligence (19 columns)
**Calendar Components (6 columns):**
- `validation_year`, `validation_month`, `validation_quarter`, `validation_day`
- `month_name`, `month_abbreviation`

**Period Formatting (3 columns):**
- `period_key` - YYYYMM format (202408)
- `period_year_month` - YYYY-MM format (2024-08)
- `quarter_key` - Format: 2024Q3

**Relative Date Logic (7 columns):**
- `is_current_month`, `is_previous_month`, `is_current_quarter`, `is_previous_quarter`, `is_current_year`
- `months_from_current`, `quarters_from_current`

**Data Completeness (3 columns):**
- `sort_order` - Sequential numbering for proper sorting
- `is_month_complete` - Data completeness flag
- `days_in_month` - Calendar month information

## Variance Categories

- **PERFECT_MATCH** ✅ - Exact data alignment (including both systems showing zero)
- **MORE_IN_IPO** ⚠️ - IP&O shows higher usage than actual (overforecasting risk)
- **MORE_IN_USAGE** ⚠️ - Actual usage higher than IP&O (underforecasting risk)
- **MISSING_FROM_USAGE** ❌ - IP&O has data, no actual usage
- **MISSING_FROM_IPO** ❌❌ - Actual usage occurred, IP&O got zero (highest priority issue)

## Data Processing Flow

### Step 1: Comprehensive Part Exclusion
- Query multiple Epicor tables to identify parts meeting exclusion criteria
- Apply all 8 exclusion rules simultaneously
- Create exclusion list for filtering PartUsage data

### Step 2: PartUsage Normalization
- Parse composite `company_plant_part` keys
- Map plant codes to business location names
- Apply usage calculation business rules
- Filter out excluded parts and SAFR data
- Standardize dates to month-end format

### Step 3: IPOValidation Normalization
- Standardize IP&O data to match PartUsage format
- Normalize dates to month-end
- Preserve original data for debugging

### Step 4: Full Comparison Analysis
- Perform FULL OUTER JOIN to capture all data scenarios
- Calculate variances and percentages
- Categorize issues by business impact
- Flag critical data integrity problems

### Step 5: Power BI Schema Generation
- Transform to snake_case column naming
- Add comprehensive date intelligence
- Generate boolean flags for easy filtering
- Include all historical data for trending analysis

## Data Integrity Priority System

The system prioritizes data integrity issues by business impact:

1. **MISSING_FROM_IPO** (Critical) - Complete underforecasting, highest priority
2. **MISSING_FROM_USAGE** (High) - Complete overforecasting, high priority
3. **MORE_IN_USAGE** (Medium) - Partial underforecasting, medium priority
4. **MORE_IN_IPO** (Lower) - Partial overforecasting, lower priority

## Expected System Behavior

In a healthy, well-integrated system:
- **Majority of records show PERFECT_MATCH**
- **Critical issues are rare** and investigated immediately
- **Variance trends improve over time** as data quality increases
- **Data completeness flags show consistent patterns**
- **No multi-million dollar forecasting errors** due to data integrity issues

## System Impact

This validation system successfully prevents the multi-million dollar forecasting errors that previously occurred due to data integrity issues between Epicor ERP and IP&O systems, providing StoneAge Manufacturing with confidence in their inventory forecasting and planning decisions.
