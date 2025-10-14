-- =============================================================================
-- IP&O Validation Detail View - Power BI Data Source
-- =============================================================================
-- Purpose: Comprehensive data source for Power BI validation reports
-- Contains: All part/location/period combinations with validation results
-- 
-- SCHEMA DESIGN:
-- - snake_case column naming for Power BI compatibility
-- - All time periods included (no date filtering)
-- - Raw variance data (thresholds calculated in Power BI)
-- - Complete date intelligence for flexible filtering
-- - Debug columns included for troubleshooting
-- =============================================================================

-- =============================================================================
-- CTE: DateBoundaries
-- Purpose: Centralize date range configuration for the entire query
-- Logic: Define validation period boundaries in one place for easy maintenance
-- =============================================================================
WITH DateBoundaries AS (
    SELECT 
        '2020-01-31' as StartDate,
        '2025-08-31' as EndDate,
        MAX(EOMONTH(Period)) as MaxValidationPeriod
    FROM IPOValidation
),

-- =============================================================================
-- CTE: ParsedKeys
-- Purpose: Parse composite company_plant_part field ONCE to eliminate repetition
-- Logic: Extract Company, Plant, and PartNum from "COMPANY_PLANT_PART" format
-- Example: "SAINC_MfgSys_ABX 326" → Company: SAINC, Plant: MfgSys, Part: ABX 326
-- =============================================================================
ParsedKeys AS (
    SELECT 
        company_plant_part,
        endOfMonth,
        ICUsage,
        IndirectUsage,
        DirectUsage,
        RentUsage,
        ICTranCount,
        IndirectTranCount,
        DirectTranCount,
        RentTranCount,
        
        -- Extract Company (everything before first underscore)
        LEFT(company_plant_part, CHARINDEX('_', company_plant_part + '_') - 1) as Company,
        
        -- Extract Plant (between first and second underscore)
        SUBSTRING(
            company_plant_part,
            CHARINDEX('_', company_plant_part) + 1,
            CHARINDEX('_', company_plant_part + '_', CHARINDEX('_', company_plant_part) + 1) - CHARINDEX('_', company_plant_part) - 1
        ) as Plant,
        
        -- Extract PartNum (everything after second underscore)
        SUBSTRING(
            company_plant_part,
            CHARINDEX('_', company_plant_part + '_', CHARINDEX('_', company_plant_part) + 1) + 1,
            LEN(company_plant_part)
        ) as PartNum
        
    FROM dbo.PartUsage
    CROSS JOIN DateBoundaries
    WHERE endOfMonth >= DateBoundaries.StartDate 
      AND endOfMonth <= DateBoundaries.EndDate
),

-- =============================================================================
-- CTE: LowUsagePartsPreCalc
-- Purpose: Pre-calculate parts with low usage (≤ 2 units over past 12 months)
-- Logic: Avoid expensive correlated subquery by calculating once upfront
-- =============================================================================
LowUsagePartsPreCalc AS (
    SELECT DISTINCT
        pk.Company,
        pk.PartNum
    FROM ParsedKeys pk
    CROSS JOIN DateBoundaries db
    WHERE pk.endOfMonth >= DATEADD(MONTH, -12, db.MaxValidationPeriod)
    GROUP BY pk.Company, pk.PartNum
    HAVING SUM(pk.ICUsage + pk.IndirectUsage + pk.DirectUsage) <= 2
),

-- =============================================================================
-- CTE: ExcludedByIPOMethod
-- Purpose: Identify parts excluded due to special IPO processing methods
-- Exclusions: Exception, Min/Max, New- No History
-- =============================================================================
ExcludedByIPOMethod AS (
    SELECT DISTINCT
        p.PartNum,
        p.Plant,
        p.Company,
        c.CodeDesc as IPOMethod
    FROM sai_dw.Erp.PartPlant p
    JOIN sai_dw.Erp.PartPlant_UD u ON p.SysRowID = u.ForeignSysRowID
    JOIN sai_dw.Ice.UDCodes c ON p.Company = c.Company
        AND u.Number02 = c.CodeID
        AND c.CodeTypeID = 'IPOMethods'
    WHERE c.CodeDesc IN ('Exception', 'Min/Max', 'New- No History')
      AND p.Company IN ('SAINC', 'SAUK', 'SANL')
),

-- =============================================================================
-- CTE: ExcludedByPartStatus
-- Purpose: Identify parts excluded due to their lifecycle status
-- Exclusions: NonStock parts, InActive parts, Runout parts
-- =============================================================================
ExcludedByPartStatus AS (
    SELECT DISTINCT
        p.PartNum,
        pp.Plant,
        p.Company,
        CASE 
            WHEN pp.NonStock = 1 THEN 'NonStock'
            WHEN p.InActive = 1 THEN 'InActive'
            WHEN p.Runout = 1 THEN 'Runout'
        END as IPOMethod
    FROM sai_dw.Erp.Part p
    JOIN sai_dw.Erp.PartPlant pp ON p.Company = pp.Company AND p.PartNum = pp.PartNum
    WHERE (pp.NonStock = 1 OR p.InActive = 1 OR p.Runout = 1)
      AND p.Company IN ('SAINC', 'SAUK', 'SANL')
),

-- =============================================================================
-- CTE: ExcludedByClassification
-- Purpose: Identify parts excluded due to material classification
-- Exclusions: RAW (raw materials), CSM (consumable materials)
-- =============================================================================
ExcludedByClassification AS (
    SELECT DISTINCT
        p.PartNum,
        pp.Plant,
        p.Company,
        'ClassID: ' + p.ClassID as IPOMethod
    FROM sai_dw.Erp.Part p
    JOIN sai_dw.Erp.PartPlant pp ON p.Company = pp.Company AND p.PartNum = pp.PartNum
    WHERE p.ClassID IN ('RAW', 'CSM')
      AND p.Company IN ('SAINC', 'SAUK', 'SANL')
),

-- =============================================================================
-- CTE: ExcludedByDataQuality
-- Purpose: Identify parts excluded due to data quality issues
-- Exclusions: Parts with question marks (?) - typically test/placeholder parts
-- =============================================================================
ExcludedByDataQuality AS (
    SELECT DISTINCT
        p.PartNum,
        pp.Plant,
        p.Company,
        'Data Quality Issue' as IPOMethod
    FROM sai_dw.Erp.Part p
    JOIN sai_dw.Erp.PartPlant pp ON p.Company = pp.Company AND p.PartNum = pp.PartNum
    WHERE p.PartNum LIKE '%?%'
      AND p.Company IN ('SAINC', 'SAUK', 'SANL')
),

-- =============================================================================
-- CTE: ExcludedByLowUsage
-- Purpose: Identify parts excluded due to insufficient usage history
-- Exclusions: Parts with ≤ 2 total usage over past 12 months
-- =============================================================================
ExcludedByLowUsage AS (
    SELECT DISTINCT
        lup.PartNum,
        pp.Plant,
        lup.Company,
        'Low Usage (≤2 units/12mo)' as IPOMethod
    FROM LowUsagePartsPreCalc lup
    JOIN sai_dw.Erp.PartPlant pp ON lup.Company = pp.Company AND lup.PartNum = pp.PartNum
    WHERE lup.Company IN ('SAINC', 'SAUK', 'SANL')
),

-- =============================================================================
-- CTE: ExcludedParts
-- Purpose: Consolidate all exclusion logic into single list
-- Logic: UNION ALL results from all exclusion CTEs
-- =============================================================================
ExcludedParts AS (
    SELECT * FROM ExcludedByIPOMethod
    UNION ALL
    SELECT * FROM ExcludedByPartStatus
    UNION ALL
    SELECT * FROM ExcludedByClassification
    UNION ALL
    SELECT * FROM ExcludedByDataQuality
    UNION ALL
    SELECT * FROM ExcludedByLowUsage
),

-- =============================================================================
-- CTE: PartUsage_Normalized
-- Purpose: Transform raw PartUsage data into standardized business format
-- Logic: Map plant codes to locations, apply usage calculation rules
-- =============================================================================
PartUsage_Normalized AS (
    SELECT
        pk.Company,
        
        -- Map Plant codes to business-friendly Location names
        CASE
            -- SAINC Locations
            WHEN pk.Company = 'SAINC' AND pk.Plant = 'SAILA' THEN 'StoneAge Louisiana'
            WHEN pk.Company = 'SAINC' AND pk.Plant IN ('SAIOH', 'SAICTN') THEN 'StoneAge Ohio'
            WHEN pk.Company = 'SAINC' AND pk.Plant = 'SAITX' THEN 'StoneAge Texas'
            WHEN pk.Company = 'SAINC' THEN 'StoneAge, Inc.'
            
            -- International Locations
            WHEN pk.Company = 'SANL' THEN 'StoneAge Netherlands B.V.'
            WHEN pk.Company = 'SAUK' THEN 'StoneAge Europe Ltd'
            WHEN pk.Company = 'SAFR' THEN 'StoneAge France'
            
            ELSE 'UNMAPPED_LOCATION'
        END as Location,
        
        pk.PartNum as Product,
        pk.Plant,
        
        EOMONTH(pk.endOfMonth) as Period,
        
        -- Apply business rules for usage calculation
        CASE
            -- SAINC MfgSys: Sum IC + Indirect + Direct
            WHEN pk.Company = 'SAINC' AND pk.Plant = 'MfgSys' 
            THEN pk.ICUsage + pk.IndirectUsage + pk.DirectUsage
            
            -- All other locations: Direct usage only
            ELSE pk.DirectUsage
        END as CalculatedUsage,
        
        -- Include raw usage components for debugging
        pk.ICUsage,
        pk.IndirectUsage,
        pk.DirectUsage,
        pk.RentUsage,
        
        -- Include transaction counts for analysis
        pk.ICTranCount,
        pk.IndirectTranCount,
        pk.DirectTranCount,
        pk.RentTranCount,
        
        -- Keep original composite field for debugging
        pk.company_plant_part as OriginalKey

    FROM ParsedKeys pk
    
    -- Exclude parts that shouldn't be validated
    WHERE NOT EXISTS (
        SELECT 1
        FROM ExcludedParts ep
        WHERE pk.Company = ep.Company
          AND pk.Plant = ep.Plant
          AND pk.PartNum = ep.PartNum
    )
    
    -- *** SAFR EXCLUSION - REMOVE THIS LINE WHEN SAFR IS ADDED TO IP&O ***
    -- Currently excluding SAFR (StoneAge France) because it's not in IP&O system yet
    -- TO ENABLE SAFR: Simply remove or comment out the line below
    AND pk.Company NOT IN ('SAFR')
    -- *** END SAFR EXCLUSION ***
),

-- =============================================================================
-- CTE: IPOValidation_Normalized
-- Purpose: Standardize IPOValidation data format for comparison
-- Logic: Normalize dates and add Plant field for exclusion logic
-- =============================================================================
IPOValidation_Normalized AS (
    SELECT
        Company,
        Location,
        Product,
        
        EOMONTH(Period) as Period,
        Qty as IPOUsage,
        Period as OriginalPeriod,
        
        -- Reverse-map Location to Plant for exclusion joins
        CASE
            WHEN Company = 'SAINC' AND Location = 'StoneAge Louisiana' THEN 'SAILA'
            WHEN Company = 'SAINC' AND Location = 'StoneAge Ohio' THEN 'SAIOH'
            WHEN Company = 'SAINC' AND Location = 'StoneAge Texas' THEN 'SAITX'
            WHEN Company = 'SAINC' AND Location = 'StoneAge, Inc.' THEN 'MfgSys'
            WHEN Company = 'SAUK' THEN 'MfgSys'
            WHEN Company = 'SANL' THEN 'MfgSys'
            WHEN Company = 'SAFR' THEN 'MfgSys'
            ELSE 'MfgSys'
        END as Plant

    FROM IPOValidation
    CROSS JOIN DateBoundaries
    WHERE Period >= DateBoundaries.StartDate 
      AND Period <= DateBoundaries.EndDate
),

-- =============================================================================
-- CTE: Comparison_Results
-- Purpose: Compare PartUsage vs IPOValidation to identify data integrity issues
-- Logic: FULL OUTER JOIN to catch missing data on either side, calculate variances
-- =============================================================================
Comparison_Results AS (
    SELECT 
        -- Coalesce to get values from either source (handles FULL OUTER JOIN nulls)
        COALESCE(pu.Company, ipo.Company) as Company,
        COALESCE(pu.Location, ipo.Location) as Location,
        COALESCE(pu.Product, ipo.Product) as Product,
        COALESCE(pu.Period, ipo.Period) as Period,
        
        -- Usage values from both sources
        pu.CalculatedUsage as PartUsage_Actual,
        ipo.IPOUsage as IPOValidation_Sent,
        
        -- Calculate variance (IPO - Actual)
        ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0) as Variance,
        
        -- Calculate percentage variance with special handling for edge cases
        CASE 
            -- Both zero: Perfect match, 0% variance
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) = 0 
            THEN 0
            
            -- Actual is zero, IPO has data: Infinite variance (999.99 = flag value)
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) <> 0
            THEN 999.99
            
            -- IPO is zero, Actual has data: Negative infinite variance (-999.99 = flag value)
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND ISNULL(ipo.IPOUsage, 0) = 0
            THEN -999.99
            
            -- Normal case: Calculate percentage variance
            ELSE ROUND(
                ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) * 100.0 / 
                NULLIF(ISNULL(pu.CalculatedUsage, 0), 0), 
                2
            )
        END as VariancePercent,
        
        -- Categorize variance type for Power BI filtering
        CASE
            -- Exact match (including 0 = 0)
            WHEN ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) = 0
            THEN 'PERFECT_MATCH'
            
            -- IPO has data but no actual usage recorded (possible overforecast)
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) <> 0
            THEN 'MISSING_FROM_USAGE'
            
            -- Actual usage occurred but IPO got zero (CRITICAL: underforecast)
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND ISNULL(ipo.IPOUsage, 0) = 0
            THEN 'MISSING_FROM_IPO'
            
            -- IPO shows higher usage than actual (overforecast)
            WHEN ISNULL(ipo.IPOUsage, 0) > ISNULL(pu.CalculatedUsage, 0)
            THEN 'MORE_IN_IPO'
            
            -- Actual usage higher than IPO (underforecast)
            WHEN ISNULL(pu.CalculatedUsage, 0) > ISNULL(ipo.IPOUsage, 0)
            THEN 'MORE_IN_USAGE'
            
            ELSE 'ERROR'
        END as VarianceCategory,

        -- Include raw components for debugging
        pu.ICUsage,
        pu.IndirectUsage,
        pu.DirectUsage,
        pu.RentUsage,
        pu.OriginalKey as PartUsage_OriginalKey,

        -- IPOMethod for debugging exclusion logic
        COALESCE(ep.IPOMethod, 'Not_Excluded') as ipo_method,
        
        -- Add ProdCode from Part table
        p.ProdCode
        
    FROM PartUsage_Normalized pu
    
    FULL OUTER JOIN IPOValidation_Normalized ipo
        ON pu.Company = ipo.Company
        AND pu.Location = ipo.Location
        AND pu.Product = ipo.Product
        AND pu.Period = ipo.Period
    
    LEFT JOIN ExcludedParts ep
        ON COALESCE(pu.Company, ipo.Company) = ep.Company
        AND COALESCE(pu.Product, ipo.Product) = ep.PartNum
        AND COALESCE(pu.Plant, ipo.Plant) = ep.Plant
    
    LEFT JOIN sai_dw.Erp.Part p
        ON COALESCE(pu.Company, ipo.Company) = p.Company
        AND COALESCE(pu.Product, ipo.Product) = p.PartNum
)

-- =============================================================================
-- FINAL OUTPUT: Power BI Schema
-- Purpose: Transform comparison results into Power BI-ready format
-- Schema: snake_case naming, comprehensive date intelligence, boolean flags
-- =============================================================================
SELECT 
    -- =============================================================================
    -- BUSINESS IDENTITY (5 columns)
    -- =============================================================================
    Company as company_code,
    Location as location_name, 
    Product as part_num,
    ProdCode as prod_code,
    Period as validation_date,
    
    -- =============================================================================
    -- CORE VALIDATION DATA (5 columns)
    -- =============================================================================
    ISNULL(PartUsage_Actual, 0) as actual_usage,
    ISNULL(IPOValidation_Sent, 0) as ipo_usage,
    Variance as variance_amount,
    VariancePercent as variance_percent,
    ABS(ISNULL(Variance, 0)) as absolute_variance,
    
    -- =============================================================================
    -- ISSUE CLASSIFICATION (1 column)
    -- =============================================================================
    VarianceCategory as variance_category,
    
    -- =============================================================================
    -- POWER BI BOOLEAN FLAGS (3 columns)
    -- =============================================================================
    CASE WHEN VarianceCategory IN ('MISSING_FROM_USAGE', 'MISSING_FROM_IPO') THEN 1 ELSE 0 END as is_critical_issue,
    CASE WHEN VarianceCategory = 'PERFECT_MATCH' THEN 1 ELSE 0 END as is_perfect_match,
    CASE WHEN VarianceCategory IN ('MORE_IN_IPO', 'MORE_IN_USAGE', 'MISSING_FROM_USAGE', 'MISSING_FROM_IPO') THEN 1 ELSE 0 END as has_variance,
    
    -- =============================================================================
    -- DEBUG COMPONENTS (6 columns)
    -- =============================================================================
    ISNULL(ICUsage, 0) as ic_usage_amount,
    ISNULL(IndirectUsage, 0) as indirect_usage_amount,
    ISNULL(DirectUsage, 0) as direct_usage_amount,
    ISNULL(RentUsage, 0) as rent_usage_amount,
    PartUsage_OriginalKey as epicor_original_key,
    ipo_method,
    
    -- =============================================================================
    -- DATE INTELLIGENCE - CALENDAR COMPONENTS (6 columns)
    -- =============================================================================
    YEAR(Period) as validation_year,
    MONTH(Period) as validation_month,
    DATEPART(QUARTER, Period) as validation_quarter,
    DAY(Period) as validation_day,
    DATENAME(MONTH, Period) as month_name,
    LEFT(DATENAME(MONTH, Period), 3) as month_abbreviation,
    
    -- =============================================================================
    -- DATE INTELLIGENCE - PERIOD FORMATTING (3 columns)
    -- =============================================================================
    FORMAT(Period, 'yyyyMM') as period_key,
    FORMAT(Period, 'yyyy-MM') as period_year_month,
    CAST(YEAR(Period) AS VARCHAR(4)) + 'Q' + CAST(DATEPART(QUARTER, Period) AS VARCHAR(1)) as quarter_key,
    
    -- =============================================================================
    -- DATE INTELLIGENCE - RELATIVE DATE LOGIC (7 columns)
    -- =============================================================================
    CASE WHEN EOMONTH(GETDATE()) = Period THEN 1 ELSE 0 END as is_current_month,
    CASE WHEN EOMONTH(DATEADD(MONTH, -1, GETDATE())) = Period THEN 1 ELSE 0 END as is_previous_month,
    CASE WHEN DATEPART(QUARTER, GETDATE()) = DATEPART(QUARTER, Period) 
              AND YEAR(GETDATE()) = YEAR(Period) THEN 1 ELSE 0 END as is_current_quarter,
    CASE WHEN DATEPART(QUARTER, DATEADD(QUARTER, -1, GETDATE())) = DATEPART(QUARTER, Period) 
              AND YEAR(DATEADD(QUARTER, -1, GETDATE())) = YEAR(Period) THEN 1 ELSE 0 END as is_previous_quarter,
    CASE WHEN YEAR(GETDATE()) = YEAR(Period) THEN 1 ELSE 0 END as is_current_year,
    DATEDIFF(MONTH, Period, EOMONTH(GETDATE())) as months_from_current,
    DATEDIFF(QUARTER, Period, GETDATE()) as quarters_from_current,
    
    -- =============================================================================
    -- DATE INTELLIGENCE - DATA COMPLETENESS (3 columns)
    -- =============================================================================
    DATEDIFF(MONTH, '2020-01-31', Period) as sort_order,
    CASE WHEN Period < EOMONTH(GETDATE()) THEN 1 ELSE 0 END as is_month_complete,
    DAY(EOMONTH(Period)) as days_in_month

FROM Comparison_Results;
