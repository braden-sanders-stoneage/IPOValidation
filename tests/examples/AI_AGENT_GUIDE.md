# AI Agent Guide: Part ID Investigation

## Purpose

This guide provides a systematic methodology for investigating individual part IDs that appear in validation results with variance issues. Use this when a user asks you to investigate why a specific part is flagged as `MISSING_FROM_IPO`, `MISSING_FROM_USAGE`, or has other variance issues.

---

## Investigation Methodology

### Overview

When investigating a part ID issue, follow this **7-step process**:

1. **Verify Raw Data Sources** - Confirm the actual data in both tables
2. **Check Part Metadata** - Review exclusion criteria and part attributes
3. **Analyze Usage History** - Understand usage patterns over time
4. **Check IP&O Presence** - Verify if part has ever been in IP&O
5. **Evaluate Exclusion Criteria** - Determine if part should be excluded
6. **Identify Root Cause** - Categorize the issue type
7. **Provide Recommendations** - Suggest actionable next steps

---

## Step-by-Step Investigation Process

### STEP 1: Verify Raw Data Sources

**Objective:** Confirm the data in both source tables that led to the variance.

#### Query PartUsage Table

```sql
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
    RentTranCount
FROM PartUsage
WHERE company_plant_part = '{COMPANY}_MfgSys_{PART_NUM}'
  AND endOfMonth = '{PERIOD_DATE}'
```

**What to Look For:**
- ✅ Record exists → Part has actual usage in Epicor
- ❌ No record → Part might only exist in IP&O (MISSING_FROM_USAGE)
- 🔍 Which usage components are non-zero? (IC, Indirect, Direct, Rent)
- 🔍 Transaction counts indicate number of transactions

**Calculate Expected Usage:**
- For SAINC MfgSys: `ICUsage + IndirectUsage + DirectUsage`
- For all other locations: `DirectUsage` only

#### Query IPOValidation Table

```sql
SELECT 
    Company,
    Location,
    Product,
    Period,
    Qty
FROM IPOValidation
WHERE Company = '{COMPANY}'
  AND Product = '{PART_NUM}'
  AND Period >= '{START_DATE}'
  AND Period <= '{END_DATE}'
```

**What to Look For:**
- ✅ Record exists → Part is in IP&O system
- ❌ No record → Part missing from IP&O (MISSING_FROM_IPO)
- 🔍 Qty value matches or differs from actual usage
- 🔍 Date format (should be first of month in raw data)

**Expected Outcome:** Confirm the variance reported in validation results is accurate.

---

### STEP 2: Check Part Metadata

**Objective:** Review part attributes that determine if it should be excluded from validation.

#### Query Part Master & PartPlant Tables

```sql
SELECT 
    p.Company,
    p.PartNum,
    p.ClassID,
    p.InActive,
    p.Runout,
    pp.Plant,
    pp.NonStock
FROM sai_dw.Erp.Part p
JOIN sai_dw.Erp.PartPlant pp 
    ON p.Company = pp.Company 
    AND p.PartNum = pp.PartNum
WHERE p.PartNum = '{PART_NUM}'
  AND p.Company = '{COMPANY}'
  AND pp.Plant = 'MfgSys'
```

**Exclusion Criteria Evaluation:**

| Field | Exclusion Rule | If True | Impact |
|-------|---------------|---------|--------|
| `NonStock` | = True | ❌ Exclude | Non-stocked items aren't forecasted |
| `InActive` | = True | ❌ Exclude | Inactive parts shouldn't be validated |
| `Runout` | = True | ❌ Exclude | Parts being phased out |
| `ClassID` | IN ('RAW', 'CSM') | ❌ Exclude | Raw materials, consumables |

**Common ClassID Values:**
- `PUR` - Purchased parts (✅ should be in IP&O)
- `MFG` - Manufactured parts (✅ should be in IP&O)
- `OSI` - Outside services (⚠️ often NonStock)
- `RAW` - Raw materials (❌ excluded)
- `CSM` - Consumable materials (❌ excluded)

**Expected Outcome:** Determine if part meets any exclusion criteria.

---

### STEP 3: Analyze Usage History

**Objective:** Understand the usage pattern to determine if it's significant or sporadic.

#### Last 12 Months Usage

```sql
SELECT 
    endOfMonth,
    ICUsage,
    IndirectUsage,
    DirectUsage,
    (ICUsage + IndirectUsage + DirectUsage) as TotalUsage
FROM PartUsage
WHERE company_plant_part = '{COMPANY}_MfgSys_{PART_NUM}'
  AND endOfMonth >= DATEADD(MONTH, -12, '{CURRENT_PERIOD}')
ORDER BY endOfMonth DESC
```

**What to Look For:**
- 📊 Total usage over 12 months
- 📊 Number of periods with activity
- 📊 Consistency (regular vs sporadic)
- 📊 Trend (increasing, stable, decreasing)

**Low Usage Threshold:**
- ≤2 units in 12 months → ❌ Should be excluded
- >2 units in 12 months → ✅ Should be validated

#### All-Time Usage Pattern

```sql
SELECT 
    COUNT(*) as PeriodCount,
    MIN(endOfMonth) as FirstUsage,
    MAX(endOfMonth) as LastUsage,
    SUM(ICUsage + IndirectUsage + DirectUsage) as TotalUsage,
    AVG(ICUsage + IndirectUsage + DirectUsage) as AvgUsagePerPeriod
FROM PartUsage
WHERE company_plant_part = '{COMPANY}_MfgSys_{PART_NUM}'
```

**What to Look For:**
- 🕐 First usage date (how long has part been active?)
- 🕐 Last usage date (recently used or dormant?)
- 📈 Total usage (significant volume or minimal?)
- 📈 Average per period (consistent demand indicator)

**Expected Outcome:** Classify usage as significant/consistent or sporadic/low-volume.

---

### STEP 4: Check IP&O Historical Presence

**Objective:** Determine if part has ever been in IP&O system or if this is a new gap.

#### Historical IP&O Records

```sql
SELECT 
    COUNT(*) as RecordCount,
    MIN(Period) as FirstPeriod,
    MAX(Period) as LastPeriod,
    SUM(Qty) as TotalQty
FROM IPOValidation
WHERE Company = '{COMPANY}'
  AND Product = '{PART_NUM}'
```

**Interpretation:**

| Record Count | Meaning | Implication |
|--------------|---------|-------------|
| 0 | Never in IP&O | Part was never configured for forecasting |
| >0 but not recent | Was in IP&O, stopped | Part was removed or system sync failed |
| >0 and recent | Currently in IP&O | Variance is a forecasting accuracy issue |

**Expected Outcome:** Understand the history of this part in IP&O system.

---

### STEP 5: Evaluate Against Exclusion Logic

**Objective:** Determine if the part should appear in validation results at all.

#### Exclusion Decision Matrix

```
IF exclusions are DISABLED:
    → All parts appear in results (current behavior)
    → Record may be legitimate OR should-be-excluded

IF exclusions are ENABLED:
    → Only non-excluded parts appear
    → All records in results are legitimate issues
```

#### Exclusion Evaluation Checklist

Check each criterion:

- [ ] **NonStock = True?** → Should be excluded
- [ ] **InActive = True?** → Should be excluded
- [ ] **Runout = True?** → Should be excluded
- [ ] **ClassID in ['RAW', 'CSM']?** → Should be excluded
- [ ] **Usage ≤2 in last 12 months?** → Should be excluded

**Decision:**
- If ANY checkbox is checked → Part should be excluded
- If ALL are unchecked → Part should be validated (legitimate issue)

---

### STEP 6: Identify Root Cause

**Objective:** Categorize the type of issue to provide correct recommendation.

#### Issue Classification

**A. Configuration Issue (Exclusions Disabled)**

**Symptoms:**
- Part meets exclusion criteria (NonStock, low usage, etc.)
- Exclusions are disabled in config
- Part has never been in IP&O

**Root Cause:** Pipeline is validating parts that should be filtered out

**Severity:** Low (expected behavior)

**Action:** Enable exclusions if desired, or accept as-is

---

**B. Legitimate Missing Part**

**Symptoms:**
- Part is stocked (NonStock = False)
- Part is active (InActive = False)
- Usage > 2 units in 12 months
- ClassID is PUR, MFG, or other standard class
- Part has never been in IP&O OR stopped appearing

**Root Cause:** Part should be forecasted but isn't configured in IP&O

**Severity:** Medium-High (forecasting blind spot)

**Action:** Add part to IP&O system

---

**C. Forecasting Accuracy Issue**

**Symptoms:**
- Part exists in both systems
- Variance is due to over/under forecasting
- Part is properly configured

**Root Cause:** Forecast model needs adjustment

**Severity:** Low-Medium (operational issue)

**Action:** Review forecasting parameters

---

**D. Data Sync Issue**

**Symptoms:**
- Part was in IP&O but stopped appearing
- Recent gap in data
- Part is still active and used

**Root Cause:** Interface/integration failure

**Severity:** High (system issue)

**Action:** Check integration logs, restart sync

---

### STEP 7: Provide Recommendations

**Objective:** Give clear, actionable next steps based on root cause.

#### Recommendation Template

```markdown
## Root Cause: [Issue Type]

### Summary
[One sentence description of the issue]

### Evidence
- Data point 1
- Data point 2
- Data point 3

### Business Impact
[Describe the consequences of this issue]

### Recommended Actions

**Immediate:**
1. [First action]
2. [Second action]

**Follow-up:**
1. [Longer-term action]
2. [Process improvement]

**Action Owner:** [Who should handle this]

**Priority:** [Low/Medium/High] based on:
- Usage volume
- Part criticality
- Business impact
```

---

## Common Patterns & Quick Diagnosis

### Pattern 1: NonStock Low-Usage Part

**Quick Checks:**
- NonStock = True? ✅
- Usage ≤2 in 12 months? ✅
- Never in IP&O? ✅

**Diagnosis:** Configuration choice - part should be excluded

**Action:** Enable exclusions or accept as-is

---

### Pattern 2: Stocked Part Never Added to IP&O

**Quick Checks:**
- NonStock = False ✅
- ClassID = PUR or MFG ✅
- Usage >10 in 12 months ✅
- Never in IP&O ✅

**Diagnosis:** Legitimate missing part

**Action:** Add to IP&O forecasting system

---

### Pattern 3: Part Stopped Appearing in IP&O

**Quick Checks:**
- Historical IP&O records exist ✅
- Recent gap in IP&O data ✅
- Still has usage ✅

**Diagnosis:** Data sync issue

**Action:** Check integration logs

---

### Pattern 4: Forecast Variance

**Quick Checks:**
- Part in both systems ✅
- Significant qty difference
- Part properly configured ✅

**Diagnosis:** Forecasting accuracy issue

**Action:** Review forecast parameters

---

## Using the Test Template

### File Location
`tests/examples/test_template.py`

### How to Use

1. **Copy the template** to a new file (e.g., `investigate_PARTNUM.py`)

2. **Update the configuration section:**
   ```python
   # Investigation configuration
   COMPANY = "SAINC"
   PART_NUM = "ABC 123"
   PERIOD = "2025-08-31"
   ```

3. **Run the script:**
   ```bash
   python investigate_PARTNUM.py
   ```

4. **Review the output** - it will guide you through all 7 steps

5. **Use the findings** to write your investigation report

### Template Structure

The template includes:
- ✅ All SQL queries pre-written
- ✅ Automatic exclusion criteria evaluation
- ✅ Usage pattern analysis
- ✅ Root cause classification logic
- ✅ Recommendation generation
- ✅ Formatted output for documentation

---

## Investigation Report Template

When documenting your findings, use this structure:

```markdown
# Investigation: [PART_NUM] [VARIANCE_CATEGORY]

**Date:** [Date]
**Record:** [Company] - [Location] - [Part] - [Period]
**Issue:** actual_usage = [X], ipo_usage = [Y], variance_category = [CATEGORY]

---

## Executive Summary

[One paragraph summary: Is this a config issue, legitimate issue, or other?]

---

## Data Verification

**PartUsage Table:**
- [Key findings]

**IPOValidation Table:**
- [Key findings]

**Conclusion:** ✅/❌

---

## Exclusion Criteria Analysis

| Criterion | Status | Result |
|-----------|--------|--------|
| NonStock | [True/False] | ✅/❌ |
| InActive | [True/False] | ✅/❌ |
| etc... | | |

**Conclusion:** PASSES ALL / FAILS [criterion]

---

## Usage Pattern Analysis

[Include usage table and summary statistics]

**Conclusion:** [Significant/Sporadic/Low-volume]

---

## Root Cause

[Detailed explanation with classification]

---

## Business Impact

[Consequences of this issue]

---

## Recommended Actions

### Immediate
1. [Action 1]
2. [Action 2]

### Follow-up
1. [Action 1]

**Action Owner:** [Team/Role]
**Priority:** [Low/Medium/High]

---

## Conclusion

**VERDICT:** [CONFIGURATION ISSUE / LEGITIMATE ISSUE / OTHER]

[Final summary paragraph]
```

---

## Tips for AI Agents

### Do's ✅

1. **Follow the 7-step process systematically** - Don't skip steps
2. **Show your SQL queries** - Makes debugging easier
3. **Interpret results in context** - Don't just report numbers
4. **Classify the issue type** - Be explicit about root cause
5. **Provide actionable recommendations** - Tell them what to do next
6. **Compare to config settings** - Check if exclusions are enabled
7. **Look for patterns** - Similar parts may have similar issues
8. **Document everything** - Create investigation files in `dev/` folder

### Don'ts ❌

1. **Don't assume data is wrong** - Usually it's correct
2. **Don't forget exclusion criteria** - Most "issues" should be excluded
3. **Don't ignore usage patterns** - Context matters
4. **Don't give vague recommendations** - Be specific
5. **Don't skip the summary** - User needs quick verdict
6. **Don't forget to check config** - Exclusions on/off changes everything
7. **Don't over-complicate** - Some issues are simple config choices

---

## Example Investigations

See these files for complete examples:
- `dev/investigate_abx207.py` - Configuration issue (NonStock, low usage)
- `dev/INVESTIGATION_FINDINGS.md` - Detailed writeup of config issue
- `dev/investigate_gpt082.py` - Legitimate missing part
- `dev/INVESTIGATION_GPT082.md` - Detailed writeup of legitimate issue

---

## Quick Reference: SQL Queries

### Get Part Usage
```sql
SELECT * FROM PartUsage 
WHERE company_plant_part = '{COMPANY}_MfgSys_{PART}'
AND endOfMonth = '{DATE}'
```

### Get IP&O Data
```sql
SELECT * FROM IPOValidation 
WHERE Company = '{COMPANY}' AND Product = '{PART}'
AND Period >= '{START}' AND Period <= '{END}'
```

### Get Part Metadata
```sql
SELECT p.*, pp.Plant, pp.NonStock
FROM sai_dw.Erp.Part p
JOIN sai_dw.Erp.PartPlant pp ON p.Company = pp.Company AND p.PartNum = pp.PartNum
WHERE p.PartNum = '{PART}' AND p.Company = '{COMPANY}'
```

### Get 12-Month Usage
```sql
SELECT endOfMonth, ICUsage, IndirectUsage, DirectUsage,
       (ICUsage + IndirectUsage + DirectUsage) as Total
FROM PartUsage
WHERE company_plant_part = '{COMPANY}_MfgSys_{PART}'
AND endOfMonth >= DATEADD(MONTH, -12, '{CURRENT}')
ORDER BY endOfMonth DESC
```

---

## Success Criteria

A complete investigation should answer:

1. ✅ Is the variance data accurate?
2. ✅ Should this part be excluded from validation?
3. ✅ What is the root cause category?
4. ✅ What is the business impact?
5. ✅ What specific actions should be taken?
6. ✅ Who should take action?
7. ✅ What is the priority level?

If you can answer all 7 questions with confidence, your investigation is complete!

---

**Good luck with your investigations! 🔍**

