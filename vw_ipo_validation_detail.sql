-- =====================================================
-- IP&O Validation Detail View - Power BI Data Source
-- =====================================================
-- Purpose: Comprehensive data source for Power BI validation reports
-- Contains: All part/location/period combinations with validation results
-- 
-- SCHEMA DESIGN:
-- - snake_case column naming for Power BI compatibility
-- - All time periods included (no date filtering)
-- - Raw variance data (thresholds calculated in Power BI)
-- - Complete date intelligence for flexible filtering
-- - Debug columns included for troubleshooting
-- =====================================================

CREATE VIEW vw_ipo_validation_detail AS

-- =====================================================
-- SECTION 1: PartUsage Normalization CTE
-- Transform raw PartUsage data into standardized format
-- =====================================================
WITH PartUsage_Normalized AS (
    SELECT 
        -- Extract Company from composite field (everything before first underscore)
        LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) as Company,
        
        -- Parse and map Location from Plant/Warehouse codes
        CASE 
            -- SAINC Location Mapping
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAINC'
                 AND SUBSTRING(company_plant_warehouse_part, 
                              CHARINDEX('_', company_plant_warehouse_part) + 1, 
                              CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'SAILA'
            THEN 'StoneAge Louisiana'
            
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAINC'
                 AND SUBSTRING(company_plant_warehouse_part, 
                              CHARINDEX('_', company_plant_warehouse_part) + 1, 
                              CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'SAIOH'
            THEN 'StoneAge Ohio'
            
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAINC'
                 AND SUBSTRING(company_plant_warehouse_part, 
                              CHARINDEX('_', company_plant_warehouse_part) + 1, 
                              CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'SAITX'
            THEN 'StoneAge Texas'
            
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAINC'
            THEN 'StoneAge, Inc.'
            
            -- SANL Location Mapping
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SANL'
            THEN 'StoneAge Netherlands B.V.'
            
            -- SAUK Location Mapping
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAUK'
            THEN 'StoneAge Europe Ltd'
            
            ELSE 'UNMAPPED_LOCATION'
        END as Location,
        
        -- Extract Product (everything after the last underscore)
        SUBSTRING(
            company_plant_warehouse_part, 
            LEN(company_plant_warehouse_part) - CHARINDEX('_', REVERSE(company_plant_warehouse_part)) + 2, 
            LEN(company_plant_warehouse_part)
        ) as Product,
        
        -- Standardize date to month-end format for comparison
        EOMONTH(endOfMonth) as Period,
        
        -- Apply Business Rules for Usage Calculation
        CASE 
            -- SAINC Manufacturing Locations (MfgSys or Durango): ICUsage + IndirectUsage + DirectUsage
            WHEN LEFT(company_plant_warehouse_part, CHARINDEX('_', company_plant_warehouse_part + '_') - 1) = 'SAINC'
                 AND SUBSTRING(company_plant_warehouse_part, 
                              CHARINDEX('_', company_plant_warehouse_part) + 1, 
                              CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'MfgSys'
            THEN ICUsage + IndirectUsage + DirectUsage
            
            -- All Other Locations: DirectUsage only
            ELSE DirectUsage
        END as CalculatedUsage,
        
        -- Include raw usage components for debugging/analysis
        ICUsage,
        IndirectUsage, 
        DirectUsage,
        RentUsage,
        
        -- Include transaction counts for analysis
        ICTranCount,
        IndirectTranCount,
        DirectTranCount,
        RentTranCount,
        
        -- Keep original composite field for debugging
        company_plant_warehouse_part as OriginalKey
        
    FROM PartUsage
    WHERE 
        -- Focus on data validation period (overlapping with IPOValidation)
        endOfMonth >= '2020-01-31'  -- IPOValidation starts Jan 2020
        AND endOfMonth <= '2025-08-31'  -- Current data through Aug 2025
        -- Include all records for comprehensive validation (including zeros)
        -- AND (ICUsage <> 0 OR IndirectUsage <> 0 OR DirectUsage <> 0 OR RentUsage <> 0)
),

-- =====================================================
-- SECTION 2: IPOValidation Normalization CTE
-- Standardize IPOValidation data format for comparison
-- =====================================================
IPOValidation_Normalized AS (
    SELECT 
        Company,
        Location,
        Product,
        
        -- Standardize date to month-end format to match PartUsage
        EOMONTH(Period) as Period,
        
        -- IPOValidation quantity (should match PartUsage CalculatedUsage)
        Qty as IPOUsage,
        
        -- Keep original period for debugging
        Period as OriginalPeriod
        
    FROM IPOValidation
    WHERE 
        -- Focus on data validation period (overlapping with PartUsage)
        Period >= '2020-01-01'  -- Start of overlapping period
        AND Period <= '2025-08-31'  -- Current data through Aug 2025
),

-- =====================================================
-- SECTION 3: Full Comparison Analysis
-- FULL OUTER JOIN to identify matches, mismatches, and missing records
-- =====================================================
Comparison_Results AS (
    SELECT 
        -- Coalesce to get values from either source
        COALESCE(pu.Company, ipo.Company) as Company,
        COALESCE(pu.Location, ipo.Location) as Location,
        COALESCE(pu.Product, ipo.Product) as Product,
        COALESCE(pu.Period, ipo.Period) as Period,
        
        -- Usage values from both sources
        pu.CalculatedUsage as PartUsage_Actual,
        ipo.IPOUsage as IPOValidation_Sent,
        
        -- Calculate variance and percentage variance
        ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0) as Variance,
        
        CASE 
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) = 0 
            THEN 0
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) <> 0
            THEN 999.99  -- IPO has data, PartUsage doesn't (infinite variance)
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND ISNULL(ipo.IPOUsage, 0) = 0
            THEN -999.99  -- PartUsage has data, IPO doesn't (negative infinite variance)
            ELSE 
                ROUND(
                    ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) * 100.0 / 
                    NULLIF(ISNULL(pu.CalculatedUsage, 0), 0), 
                    2
                )
        END as VariancePercent,
        
        -- Categorize the record type
        CASE 
            WHEN pu.CalculatedUsage IS NOT NULL AND ipo.IPOUsage IS NOT NULL 
            THEN 'BOTH_EXIST'
            WHEN pu.CalculatedUsage IS NOT NULL AND ipo.IPOUsage IS NULL 
            THEN 'PARTUSAGE_ONLY'
            WHEN pu.CalculatedUsage IS NULL AND ipo.IPOUsage IS NOT NULL 
            THEN 'IPO_ONLY'
            ELSE 'ERROR'
        END as RecordType,
        
        -- Flag significant variances (raw categorization for Power BI)
        CASE 
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) = 0 
            THEN 'MATCH_ZERO'
            WHEN ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) = 0
            THEN 'PERFECT_MATCH'
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) <> 0
            THEN 'CRITICAL_IPO_ORPHAN'
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND ISNULL(ipo.IPOUsage, 0) = 0
            THEN 'CRITICAL_MISSING_FROM_IPO'
            ELSE 'HAS_VARIANCE'
        END as VarianceCategory,
        
        -- Include raw components for debugging
        pu.ICUsage,
        pu.IndirectUsage, 
        pu.DirectUsage,
        pu.RentUsage,
        pu.OriginalKey as PartUsage_OriginalKey
        
    FROM PartUsage_Normalized pu
    FULL OUTER JOIN IPOValidation_Normalized ipo
        ON pu.Company = ipo.Company
        AND pu.Location = ipo.Location  
        AND pu.Product = ipo.Product
        AND pu.Period = ipo.Period
)

-- =====================================================
-- SECTION 4: Final View Output with Power BI Schema
-- All records with snake_case naming and date intelligence
-- =====================================================
SELECT 
    -- Business Identity (snake_case)
    Company as company_code,
    Location as location_name, 
    Product as product_code,
    Period as validation_date,
    
    -- Core validation data (snake_case)
    PartUsage_Actual as actual_usage,
    IPOValidation_Sent as ipo_usage,
    Variance as variance_amount,
    VariancePercent as variance_percent,
    ABS(ISNULL(Variance, 0)) as absolute_variance,
    
    -- Classification (snake_case)
    VarianceCategory as variance_category,
    RecordType as record_type,
    
    -- Boolean flags for Power BI
    CASE WHEN VarianceCategory IN ('CRITICAL_IPO_ORPHAN', 'CRITICAL_MISSING_FROM_IPO') THEN 1 ELSE 0 END as is_critical_issue,
    CASE WHEN VarianceCategory IN ('PERFECT_MATCH', 'MATCH_ZERO') THEN 1 ELSE 0 END as is_perfect_match,
    CASE WHEN ABS(ISNULL(Variance, 0)) > 0 THEN 1 ELSE 0 END as has_variance,
    
    -- Debug components (snake_case)
    ICUsage as ic_usage_amount,
    IndirectUsage as indirect_usage_amount,
    DirectUsage as direct_usage_amount,
    RentUsage as rent_usage_amount,
    PartUsage_OriginalKey as epicor_original_key,
    
    -- Date Intelligence - Basic Components (Calendar Year)
    YEAR(Period) as validation_year,
    MONTH(Period) as validation_month,
    DATEPART(QUARTER, Period) as validation_quarter,
    DAY(Period) as validation_day,
    DATENAME(MONTH, Period) as month_name,
    LEFT(DATENAME(MONTH, Period), 3) as month_abbreviation,
    
    -- Date Intelligence - Period Keys for Filtering/Sorting
    FORMAT(Period, 'yyyyMM') as period_key,
    FORMAT(Period, 'yyyy-MM') as period_year_month,
    CAST(YEAR(Period) AS VARCHAR(4)) + 'Q' + CAST(DATEPART(QUARTER, Period) AS VARCHAR(1)) as quarter_key,
    
    -- Date Intelligence - Relative Date Logic (Mountain Time / Server Date)
    CASE WHEN EOMONTH(GETDATE()) = Period THEN 1 ELSE 0 END as is_current_month,
    CASE WHEN EOMONTH(DATEADD(MONTH, -1, GETDATE())) = Period THEN 1 ELSE 0 END as is_previous_month,
    CASE WHEN DATEPART(QUARTER, GETDATE()) = DATEPART(QUARTER, Period) 
              AND YEAR(GETDATE()) = YEAR(Period) THEN 1 ELSE 0 END as is_current_quarter,
    CASE WHEN DATEPART(QUARTER, DATEADD(QUARTER, -1, GETDATE())) = DATEPART(QUARTER, Period) 
              AND YEAR(DATEADD(QUARTER, -1, GETDATE())) = YEAR(Period) THEN 1 ELSE 0 END as is_previous_quarter,
    CASE WHEN YEAR(GETDATE()) = YEAR(Period) THEN 1 ELSE 0 END as is_current_year,
    
    -- Date Intelligence - Relative Calculations  
    DATEDIFF(MONTH, Period, EOMONTH(GETDATE())) as months_from_current,
    DATEDIFF(QUARTER, Period, GETDATE()) as quarters_from_current,
    
    -- Date Intelligence - Power BI Optimization
    DATEDIFF(MONTH, '2020-01-31', Period) as sort_order,  -- Sequential numbering from start
    CASE WHEN Period < EOMONTH(GETDATE()) THEN 1 ELSE 0 END as is_month_complete,
    DAY(EOMONTH(Period)) as days_in_month
    
FROM Comparison_Results;
