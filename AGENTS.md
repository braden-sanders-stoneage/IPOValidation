# IP&O Validation Project - AI Agent Context Document

## **Business Problem & Background**

### **Critical Issue**
StoneAge Manufacturing discovered a **2-year bug in their IP&O (Inventory Planning & Optimization) software** that was chronically underforecasting part usage, costing the company **millions of dollars**. The bug caused systematic underestimation of inventory needs, leading to stockouts and production delays.

### **Root Cause**
The IP&O software was receiving incorrect or inconsistent data from their ERP system (Epicor), leading to flawed forecasting models. The company needs to ensure **data integrity** between what they send to IP&O versus their actual usage data in Epicor.

### **Mission**
Create an automated validation system that compares:
- **Source Data**: Actual part usage from Epicor ERP (PartUsage table)
- **IP&O Feed Data**: Data being sent to IP&O software (IPOValidation table)

Ensure these datasets are **EXACTLY THE SAME** each month to prevent future forecasting errors.

## **Database Structure Analysis**

### **Table 1: dbo.PartUsage (Actual Epicor Usage Data)**
- **Purpose**: Actual part consumption from Epicor ERP system
- **Scale**: 384,845 records covering 39,789 unique part-location combinations
- **Time Range**: November 2018 to January 2025
- **Structure**:
  ```sql
  endOfMonth (datetime) - End of month date
  ICUsage (numeric) - Inventory Control usage quantity
  IndirectUsage (numeric) - Indirect usage quantity  
  DirectUsage (numeric) - Direct usage quantity
  RentUsage (numeric) - Rental usage quantity
  ICTranCount (int) - Number of IC transactions
  IndirectTranCount (int) - Number of indirect transactions
  DirectTranCount (int) - Number of direct transactions
  RentTranCount (int) - Number of rental transactions
  company_plant_warehouse_part (varchar 200) - Composite identifier
  company_plant_warehouse_part_date (varchar 200) - Primary key with date
  ```

### **Table 2: dbo.IPOValidation (Data Sent to IP&O)**
- **Purpose**: Validated inventory data being fed to IP&O software
- **Scale**: 594,864 records covering 5,736 unique products
- **Time Range**: January 2020 to August 2025 (includes forecasting periods)
- **Structure**:
  ```sql
  Product (nvarchar 50) - Product identifier/part number
  Location (nvarchar 50) - Physical location or facility name
  Company (nvarchar 50) - Company code (SAINC, SANL, SAUK)
  Period (date) - Time period for the inventory data
  Qty (decimal) - Validated quantity for the product
  ```

### **Key Structural Differences**
1. **Time Fields**: PartUsage uses `endOfMonth` (datetime) vs IPOValidation uses `Period` (date)
2. **Location Encoding**: PartUsage uses composite `company_plant_warehouse_part` vs IPOValidation has separate fields
3. **Quantity Aggregation**: PartUsage has multiple usage categories vs IPOValidation has single `Qty` field

## **Business Rules (Critical)**

### **Usage Calculation Rules**
**SAINC Company - Manufacturing Locations (MfgSys or Durango):**
```
IPOValidation.Qty = ICUsage + IndirectUsage + DirectUsage
```

**All Other Locations:**
```
IPOValidation.Qty = DirectUsage (only)
```

### **Validation Thresholds**
- **Variance Threshold**: 5% (configurable)
- **Scope**: Validate ALL products and locations
- **Exception Handling**: Log discrepancies to database table for analysis

## **Technology Decision Process**

### **Options Considered**

#### **Option 1: Python Approach**
- **Pros**: Flexible data manipulation, complex business logic handling
- **Cons**: Additional infrastructure, learning curve, deployment complexity
- **Verdict**: Initially considered but deemed over-engineered

#### **Option 2: Microsoft Report Builder (SSRS)**
- **Pros**: Native SQL Server integration, visual designer
- **Cons**: Limited business logic capabilities, not designed for data validation workflows
- **Verdict**: Suggested by coworker but insufficient for complex comparison needs

#### **Option 3: Single SQL Query File (CHOSEN APPROACH)**
- **Pros**: Read-only operation, portable, transparent logic, automation-ready
- **Approach**: Single .sql file with CTEs for data normalization and comparison
- **Verdict**: **SELECTED** - No database modifications required, all logic visible

## **Solution Architecture**

### **Single SQL File Approach**
The solution is implemented as **one comprehensive .sql file** that performs the entire validation as a query operation:

```sql
-- IP&O Validation Query
-- Section 1: PartUsage Normalization CTE
WITH PartUsage_Normalized AS (
  -- Parse locations, apply business rules, standardize dates
)

-- Section 2: IPOValidation Normalization CTE  
, IPOValidation_Normalized AS (
  -- Standardize dates to month-end format
)

-- Section 3: Full Comparison CTE
, Comparison_Results AS (
  -- FULL OUTER JOIN with variance calculations
)

-- Section 4: Final Results
SELECT * FROM Comparison_Results
UNION ALL
SELECT * FROM Summary_Statistics
```

### **Validation Logic Flow**
```sql
1. PartUsage CTE: Parse composite fields, apply business rules, calculate usage
2. IPOValidation CTE: Standardize dates for period matching
3. Comparison CTE: FULL OUTER JOIN between normalized datasets
4. Calculate percentage variances and identify exceptions (variance > 5%)
5. Return complete result set with matches, mismatches, and missing records
6. Include summary statistics and exception categorization
```

### **Key SQL Business Logic**
```sql
CASE 
    WHEN Company = 'SAINC' AND (Location LIKE '%MfgSys%' OR Location LIKE '%Durango%')
    THEN ICUsage + IndirectUsage + DirectUsage
    ELSE DirectUsage
END AS CalculatedUsage
```

## **Current Project Status**

### **Completed Tasks**
- [x] Database structure analysis and documentation
- [x] Business requirements gathering
- [x] Technology approach selection
- [x] Project architecture design
- [x] TODO list creation

### **TODO List (13 Tasks Remaining)**

#### **Phase 1: Data Analysis & Mapping (Tasks 1-3)**
1. **Location parsing analysis** - Map PartUsage composite field to IPOValidation Location field
2. **Date alignment analysis** - Match PartUsage.endOfMonth to IPOValidation.Period for overlapping periods
3. **Business rule validation** - Identify SAINC MfgSys/Durango locations vs other locations

#### **Phase 2: Data Normalization (Tasks 4-5)**
4. **PartUsage CTE creation** - Parse fields, apply business rules, calculate usage with CASE statements
5. **IPOValidation CTE creation** - Standardize date format for month-end alignment

#### **Phase 3: Comparison Logic (Tasks 6-8)**
6. **Full comparison CTE** - FULL OUTER JOIN between normalized datasets
7. **Variance calculations** - 5% threshold logic and variance categorization
8. **Result set design** - Comprehensive output showing matches, mismatches, missing records

#### **Phase 4: Testing & Optimization (Tasks 9-13)**
9. **Single month testing** - Test complete SQL file on sample month to verify logic
10. **Summary statistics** - Exception counts, variance distribution, validation metrics
11. **Performance optimization** - Query tuning and helpful comments for automation
12. **Multi-month testing** - Verify consistency and reliability across multiple periods
13. **Final production file** - Parameter options for month selection and automation integration

## **Database Environment Details**

### **Technology Stack**
- **Database**: Microsoft SQL Server
- **Admin Tool**: SQL Server Management Studio (SSMS)
- **Scheduling**: SQL Server Agent
- **Optional Reporting**: SQL Server Reporting Services (SSRS)

### **Database Access Pattern**
- User currently uses SSMS for database browsing and queries
- MCP (Model Context Protocol) connection available for programmatic access
- Database contains multi-company data (SAINC, SANL, SAUK, BWLLC)

### **Sample Data Insights**
- **PartUsage**: Primarily SAINC and BWLLC company data
- **IPOValidation**: SAINC, SANL, SAUK company data
- **Location Examples**: StoneAge Inc., StoneAge Texas, various plant/warehouse combinations
- **Product Examples**: BA-6-MP, ABX 356, OS7 002, GPT 310

## **Critical Success Factors**

### **Data Quality Requirements**
- **Exact Matching**: Zero tolerance for data discrepancies between systems
- **Comprehensive Coverage**: Must validate ALL products and locations
- **Timeliness**: Monthly validation within 3 business days of month-end
- **Auditability**: Complete logging of all exceptions and validation results

### **Performance Requirements**
- Handle 500K+ records efficiently
- Complete validation within reasonable timeframe (< 30 minutes)
- Minimal impact on production database performance

### **Operational Requirements**
- **Automated Execution**: No manual intervention required
- **Exception Alerting**: Immediate notification of validation failures
- **Trend Analysis**: Historical tracking of validation results
- **Easy Maintenance**: Standard SQL skills sufficient for modifications

## **Risk Mitigation**

### **Data Integrity Risks**
- **Incomplete Data**: Handle missing records in either dataset
- **Timing Issues**: Account for data settlement delays after month-end
- **Schema Changes**: Monitor for structural changes in source tables

### **Technical Risks**
- **Performance Degradation**: Monitor execution times and optimize as needed
- **False Positives**: Validate variance thresholds don't create noise
- **System Dependencies**: Ensure SQL Server Agent reliability

## **Next Steps for AI Assistant**

1. **Immediate Priority**: Start with Task 1 (Location parsing analysis)
2. **Focus Areas**: CTE development, business rule implementation, data mapping
3. **Testing Strategy**: Single month samples first, then multi-month validation
4. **Documentation**: Comment SQL file thoroughly for future automation
5. **Deliverable**: Single comprehensive .sql file ready for monthly execution

## **Key Questions for Ongoing Development**

1. **Location Parsing**: How to reliably extract company/location from `company_plant_warehouse_part` field?
2. **Date Alignment**: How to handle month-end date standardization between datasets?
3. **Exception Prioritization**: Which types of exceptions are most critical for business?
4. **Performance Tuning**: What indexing strategy will optimize the comparison queries?
5. **Alerting Mechanism**: How should critical exceptions be communicated to stakeholders?

## **Contact & Handoff Information**

- **Project Owner**: User working on inventory forecasting accuracy
- **Technical Environment**: Windows 10, PowerShell, SQL Server Management Studio
- **Workspace**: `C:\Users\braden.sanders\SQL\IPO_Validation`
- **Deliverable**: Single .sql file for validation operations
- **Database Access**: Read-only via MCP connection for query development and testing

This project is **mission-critical** for preventing future forecasting errors that cost millions of dollars. The solution must be **robust, automated, and absolutely reliable** in detecting any data discrepancies between Epicor and IP&O systems.
