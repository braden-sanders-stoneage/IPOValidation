-- =====================================================
-- IP&O Validation Query - Production Version
-- =====================================================
-- Purpose: Compare PartUsage (Epicor truth) vs IPOValidation (IP&O feed)
-- Mission: Ensure data integrity to prevent multi-million dollar forecasting errors
--
-- BUSINESS RULES:
-- - SAINC MfgSys/Durango: CalculatedUsage = ICUsage + IndirectUsage + DirectUsage  
-- - All Other Locations: CalculatedUsage = DirectUsage only
-- - Variance Threshold: configurable via @VarianceThreshold parameter
-- - Report Priority: Missing > Orphaned > >Threshold% Variance
--
-- AUTOMATION NOTES:
-- - Change @ValidationMonth parameter below for different analysis periods
-- - Schedule monthly after month-end data settlement (recommend 3 business days)
-- - Monitor for CRITICAL_MISSING_FROM_IPO and CRITICAL_IPO_ORPHAN categories
-- - Performance: ~30 seconds on 500K+ records, consider indexing on Period columns
-- - Results format: Critical exceptions first, then summary statistics
-- =====================================================

-- =====================================================
-- CONFIGURATION PARAMETERS
-- =====================================================
DECLARE @ValidationMonth DATE = '2025-08-31';  -- **CHANGE THIS FOR DIFFERENT MONTHS**
DECLARE @ShowAllRecords BIT = 1;               -- **1 = Show all parts, 0 = Show only critical issues**
DECLARE @VarianceThreshold DECIMAL(5,2) = 5.0; -- **Variance percentage threshold (5.0 = 5%)**

-- For automation, replace this with a parameter or calculate dynamically:
-- SET @ValidationMonth = EOMONTH(DATEADD(month, -1, GETDATE()));  -- Previous month
-- =====================================================

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
                 AND (
                     -- MfgSys Manufacturing (including Durango warehouses DGO*)
                     SUBSTRING(company_plant_warehouse_part, 
                              CHARINDEX('_', company_plant_warehouse_part) + 1, 
                              CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'MfgSys'
                     -- OR explicit Durango warehouse identification
                     OR (SUBSTRING(company_plant_warehouse_part, 
                                  CHARINDEX('_', company_plant_warehouse_part) + 1, 
                                  CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - CHARINDEX('_', company_plant_warehouse_part) - 1) = 'MfgSys'
                         AND SUBSTRING(company_plant_warehouse_part, 
                                      CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) + 1,
                                      CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) + 1) - CHARINDEX('_', company_plant_warehouse_part + '_', CHARINDEX('_', company_plant_warehouse_part) + 1) - 1) LIKE 'DGO%')
                 )
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
        -- Include all records for comprehensive validation (comment out line below for production to exclude zeros)
        -- AND (ICUsage <> 0 OR IndirectUsage <> 0 OR DirectUsage <> 0 OR RentUsage <> 0)
        -- PERFORMANCE: Consider adding index on endOfMonth for automation
)

-- =====================================================
-- SECTION 2: IPOValidation Normalization CTE
-- Standardize IPOValidation data format for comparison
-- =====================================================
, IPOValidation_Normalized AS (
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
        -- PERFORMANCE: Consider adding index on Period for automation
)

-- =====================================================
-- SECTION 3: Full Comparison Analysis
-- FULL OUTER JOIN to identify matches, mismatches, and missing records
-- =====================================================
, Comparison_Results AS (
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
        
        -- Flag significant variances (configurable threshold)
        CASE 
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) = 0 
            THEN 'MATCH_ZERO'
            WHEN ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) = 0
            THEN 'PERFECT_MATCH'
            WHEN ISNULL(pu.CalculatedUsage, 0) = 0 AND ISNULL(ipo.IPOUsage, 0) <> 0
            THEN 'CRITICAL_IPO_ORPHAN'
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND ISNULL(ipo.IPOUsage, 0) = 0
            THEN 'CRITICAL_MISSING_FROM_IPO'
            WHEN ISNULL(pu.CalculatedUsage, 0) <> 0 AND 
                 ABS(ISNULL(ipo.IPOUsage, 0) - ISNULL(pu.CalculatedUsage, 0)) * 100.0 / 
                 ISNULL(pu.CalculatedUsage, 0) > @VarianceThreshold
            THEN 'VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT'
            ELSE 'VARIANCE_WITHIN_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT'
        END as VarianceCategory,
        
        -- Include raw components for debugging
        pu.ICUsage,
        pu.IndirectUsage, 
        pu.DirectUsage,
        pu.OriginalKey as PartUsage_OriginalKey
        
    FROM PartUsage_Normalized pu
    FULL OUTER JOIN IPOValidation_Normalized ipo
        ON pu.Company = ipo.Company
        AND pu.Location = ipo.Location  
        AND pu.Product = ipo.Product
        AND pu.Period = ipo.Period
)

-- =====================================================
-- SECTION 4: Comprehensive Validation Results
-- Single statement with all results to maintain CTE scope
-- =====================================================

-- Critical Issues with Summary Statistics (Combined Results)
SELECT 
    -- Sort order to separate sections
    CASE 
        WHEN Company NOT IN ('SUMMARY_HEADER', 'RECORD_BREAKDOWN', 'VARIANCE_BREAKDOWN', 'COMPANY_BREAKDOWN') THEN 1
        WHEN Company = 'SUMMARY_HEADER' THEN 2
        WHEN Company = 'RECORD_BREAKDOWN' THEN 3
        WHEN Company = 'VARIANCE_BREAKDOWN' THEN 4  
        WHEN Company = 'COMPANY_BREAKDOWN' THEN 5
        ELSE 6
    END as SectionOrder,
    
    -- Priority within critical issues section
    CASE VarianceCategory
        WHEN 'CRITICAL_MISSING_FROM_IPO' THEN 1
        WHEN 'CRITICAL_IPO_ORPHAN' THEN 2  
        WHEN 'VARIANCE_EXCEEDS_5PCT' THEN 3
        ELSE 4
    END as VariancePriority,
    
    Company,
    Location, 
    Product,
    CONVERT(VARCHAR, Period, 23) as Period,
    PartUsage_Actual,
    IPOValidation_Sent,
    Variance,
    VariancePercent,
    VarianceCategory,
    RecordType,
    ICUsage,
    IndirectUsage,
    DirectUsage,
    PartUsage_OriginalKey
FROM Comparison_Results
WHERE 
    Period = @ValidationMonth
    -- Configurable filter: Show all records or just critical issues
    AND (@ShowAllRecords = 1 OR VarianceCategory IN ('VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT', 'CRITICAL_IPO_ORPHAN', 'CRITICAL_MISSING_FROM_IPO'))

UNION ALL

-- Summary Header
SELECT 
    2 as SectionOrder,
    1 as VariancePriority,
    'SUMMARY_HEADER' as Company,
    'Validation Date: ' + CONVERT(VARCHAR, @ValidationMonth, 23) as Location,
    CASE WHEN @ShowAllRecords = 1 THEN 'All Part Records Above' ELSE 'Critical Issues Above' END as Product,
    'Summary Statistics Below' as Period,
    NULL as PartUsage_Actual,
    NULL as IPOValidation_Sent,
    NULL as Variance,
    NULL as VariancePercent,
    NULL as VarianceCategory,
    NULL as RecordType,
    NULL as ICUsage,
    NULL as IndirectUsage,
    NULL as DirectUsage,
    NULL as PartUsage_OriginalKey

UNION ALL

-- Record Type Breakdown
SELECT 
    3 as SectionOrder,
    1 as VariancePriority,
    'RECORD_BREAKDOWN' as Company,
    RecordType as Location,
    CAST(COUNT(*) AS VARCHAR) + ' records (' + 
    CAST(ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS VARCHAR) + '%)' as Product,
    NULL as Period,
    COUNT(*) as PartUsage_Actual,
    NULL as IPOValidation_Sent,
    NULL as Variance,
    NULL as VariancePercent,
    NULL as VarianceCategory,
    NULL as RecordType,
    NULL as ICUsage,
    NULL as IndirectUsage,
    NULL as DirectUsage,
    NULL as PartUsage_OriginalKey
FROM Comparison_Results 
WHERE Period = @ValidationMonth
GROUP BY RecordType

UNION ALL

-- Variance Category Breakdown
SELECT 
    4 as SectionOrder,
    CASE VarianceCategory
        WHEN 'CRITICAL_MISSING_FROM_IPO' THEN 1
        WHEN 'CRITICAL_IPO_ORPHAN' THEN 2  
        WHEN 'VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT' THEN 3
        WHEN 'VARIANCE_WITHIN_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT' THEN 4
        WHEN 'PERFECT_MATCH' THEN 5
        WHEN 'MATCH_ZERO' THEN 6
        ELSE 7
    END as VariancePriority,
    'VARIANCE_BREAKDOWN' as Company,
    VarianceCategory as Location,
    CAST(COUNT(*) AS VARCHAR) + ' records' as Product,
    'Avg: ' + CAST(ROUND(AVG(ABS(Variance)), 1) AS VARCHAR) + 
    ', Max: ' + CAST(MAX(ABS(Variance)) AS VARCHAR) as Period,
    COUNT(*) as PartUsage_Actual,
    CAST(ROUND(AVG(ABS(Variance)), 1) AS INT) as IPOValidation_Sent,
    CAST(MAX(ABS(Variance)) AS INT) as Variance,
    NULL as VariancePercent,
    NULL as VarianceCategory,
    NULL as RecordType,
    NULL as ICUsage,
    NULL as IndirectUsage,
    NULL as DirectUsage,
    NULL as PartUsage_OriginalKey
FROM Comparison_Results 
WHERE Period = @ValidationMonth
GROUP BY VarianceCategory

UNION ALL

-- Company Breakdown
SELECT 
    5 as SectionOrder,
    CASE WHEN SUM(CASE WHEN VarianceCategory IN ('VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT', 'CRITICAL_IPO_ORPHAN', 'CRITICAL_MISSING_FROM_IPO') THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 2 END as VariancePriority,
    'COMPANY_BREAKDOWN' as Company,
    Company as Location,
    CAST(COUNT(*) AS VARCHAR) + ' total records' as Product,
    CAST(SUM(CASE WHEN VarianceCategory IN ('VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT', 'CRITICAL_IPO_ORPHAN', 'CRITICAL_MISSING_FROM_IPO') THEN 1 ELSE 0 END) AS VARCHAR) + ' critical issues' as Period,
    COUNT(*) as PartUsage_Actual,
    SUM(CASE WHEN VarianceCategory IN ('VARIANCE_EXCEEDS_' + CAST(@VarianceThreshold AS VARCHAR) + 'PCT', 'CRITICAL_IPO_ORPHAN', 'CRITICAL_MISSING_FROM_IPO') THEN 1 ELSE 0 END) as IPOValidation_Sent,
    CAST(ROUND(AVG(CASE WHEN RecordType = 'BOTH_EXIST' AND PartUsage_Actual > 0 THEN ABS(VariancePercent) END), 2) AS DECIMAL(10,2)) as Variance,
    NULL as VariancePercent,
    NULL as VarianceCategory,
    NULL as RecordType,
    NULL as ICUsage,
    NULL as IndirectUsage,
    NULL as DirectUsage,
    NULL as PartUsage_OriginalKey
FROM Comparison_Results 
WHERE Period = @ValidationMonth
GROUP BY Company

ORDER BY SectionOrder, VariancePriority, Variance DESC;
