# Part Investigation Examples

This folder contains templates and guides for investigating individual part IDs that appear in validation results.

---

## 📁 Files in This Folder

### 1. **AI_AGENT_GUIDE.md**
**Purpose:** Comprehensive methodology guide for AI agents

**Contains:**
- 7-step investigation process
- SQL query templates
- Decision matrices
- Root cause classification
- Recommendation frameworks
- Common patterns and quick diagnosis
- Best practices and tips

**Use this when:** You need to understand HOW to investigate a part systematically

---

### 2. **test_template.py**
**Purpose:** Reusable Python script template for part investigations

**Contains:**
- Pre-written SQL queries for all 7 steps
- Automated exclusion criteria evaluation
- Usage pattern analysis
- Root cause classification logic
- Recommendation generation
- Formatted output

**Use this when:** You need to actually RUN an investigation

**How to use:**
1. Copy to `dev/` folder: `cp tests/examples/test_template.py dev/investigate_PARTNUM.py`
2. Edit configuration section (COMPANY, PART_NUM, PERIOD, etc.)
3. Run: `python dev/investigate_PARTNUM.py`
4. Review output and create investigation report

---

### 3. **README.md** (this file)
**Purpose:** Overview and quick start guide

---

## 🚀 Quick Start

### For AI Agents

**When a user asks: "Can you investigate why part XYZ is missing from IP&O?"**

1. **Read the guide first:**
   ```bash
   cat tests/examples/AI_AGENT_GUIDE.md
   ```

2. **Copy the template:**
   ```bash
   cp tests/examples/test_template.py dev/investigate_XYZ.py
   ```

3. **Update configuration in the new file:**
   ```python
   COMPANY = "SAINC"
   PART_NUM = "XYZ 123"
   LOCATION = "StoneAge, Inc."
   PERIOD = "2025-08-31"
   EXPECTED_ACTUAL_USAGE = 10
   EXPECTED_IPO_USAGE = 0
   EXPECTED_VARIANCE_CATEGORY = "MISSING_FROM_IPO"
   ```

4. **Run the investigation:**
   ```bash
   python dev/investigate_XYZ.py
   ```

5. **Create investigation report using the output**

---

## 📖 Investigation Methodology

### The 7-Step Process

**STEP 1: Verify Raw Data Sources**
- Confirm data in PartUsage and IPOValidation tables
- Calculate expected usage values
- Verify against validation results

**STEP 2: Check Part Metadata**
- Review part attributes (NonStock, InActive, ClassID, etc.)
- Evaluate against exclusion criteria
- Determine if part should be filtered

**STEP 3: Analyze Usage History**
- Last 12 months usage pattern
- All-time usage statistics
- Determine if usage is significant or sporadic

**STEP 4: Check IP&O Historical Presence**
- Has part ever been in IP&O?
- When was it last in IP&O?
- Is this a new gap or ongoing issue?

**STEP 5: Evaluate Exclusion Criteria**
- Check current config settings
- Compare part attributes to exclusion rules
- Determine if part should appear in results

**STEP 6: Identify Root Cause**
- Classify issue type:
  - Configuration issue
  - Legitimate missing part
  - Data sync issue
  - Forecasting accuracy issue
- Provide evidence for classification

**STEP 7: Provide Recommendations**
- Immediate actions
- Follow-up actions
- Action owner
- Priority level

---

## 🎯 Root Cause Categories

### Configuration Issue
**Symptoms:** Part meets exclusion criteria, exclusions disabled  
**Action:** Enable exclusions or accept as-is  
**Severity:** Low

### Legitimate Missing Part
**Symptoms:** Stocked part with significant usage, never in IP&O  
**Action:** Add to IP&O system  
**Severity:** Medium-High

### Data Sync Issue
**Symptoms:** Part was in IP&O, stopped appearing, still has usage  
**Action:** Check integration logs  
**Severity:** High

### Forecasting Accuracy Issue
**Symptoms:** Part in both systems, variance in quantities  
**Action:** Review forecast parameters  
**Severity:** Low-Medium

---

## 📊 Example Investigations

See the `dev/` folder for complete examples:

### Example 1: ABX 207 (Configuration Issue)
- **Files:** `dev/investigate_abx207.py`, `dev/INVESTIGATION_FINDINGS.md`
- **Type:** Configuration issue
- **Finding:** NonStock part with low usage, should be excluded
- **Action:** Enable exclusions (optional)

### Example 2: GPT 082 (Legitimate Missing Part)
- **Files:** `dev/investigate_gpt082.py`, `dev/INVESTIGATION_GPT082.md`
- **Type:** Legitimate data integrity issue
- **Finding:** Stocked part with 25 units/year, never in IP&O
- **Action:** Add to IP&O system (required)

---

## 💡 Decision Tree

```
Is exclusions enabled in config?
├─ NO
│  └─ Does part meet any exclusion criteria?
│     ├─ YES → CONFIGURATION ISSUE (enable exclusions)
│     └─ NO → Continue to next check
└─ YES
   └─ Part is in results (passed exclusions)

Does part have usage in PartUsage?
├─ NO → MISSING_FROM_USAGE (check if part should be in IP&O)
└─ YES → Continue to next check

Does part exist in IPOValidation?
├─ NO
│  └─ Has it EVER been in IPOValidation?
│     ├─ NO → LEGITIMATE MISSING PART (add to IP&O)
│     └─ YES → DATA SYNC ISSUE (check integration)
└─ YES → FORECASTING ACCURACY ISSUE (review parameters)
```

---

## 🔍 Quick Reference: Exclusion Criteria

| Criterion | Rule | Action if True |
|-----------|------|----------------|
| NonStock | = True | Exclude (non-stocked items) |
| InActive | = True | Exclude (inactive parts) |
| Runout | = True | Exclude (being phased out) |
| ClassID | IN ('RAW', 'CSM') | Exclude (raw materials) |
| Low Usage | ≤2 units in 12 months | Exclude (minimal usage) |

**If ANY criterion is true** → Part should be excluded from validation

---

## 📝 Investigation Report Template

```markdown
# Investigation: [PART_NUM] [VARIANCE_CATEGORY]

**Date:** [Date]
**Part:** [Company] - [Location] - [Part] - [Period]
**Issue:** actual_usage = [X], ipo_usage = [Y]

## Executive Summary
[One paragraph: Is this legitimate or configuration issue?]

## Data Verification
[Confirm data accuracy]

## Exclusion Criteria Analysis
[Table showing each criterion]

## Usage Pattern Analysis
[Usage statistics and trends]

## Root Cause
[Classification with evidence]

## Recommended Actions
**Immediate:** [List]
**Action Owner:** [Team]
**Priority:** [Level]

## Conclusion
**VERDICT:** [Issue type]
```

---

## 🛠️ Tools & Resources

### Database Queries
- All queries are in `test_template.py`
- Copy/paste into MCP if needed
- Modify parameters as needed

### MCP Integration
- Can use `mcp_mssql_read_data` tool for queries
- Useful for quick checks without running full script
- Example:
  ```python
  mcp_mssql_read_data(query="SELECT * FROM PartUsage WHERE ...")
  ```

### Configuration
- Check current settings: `cat config.json`
- Key setting: `"apply_exclusions": true/false`
- Affects whether excluded parts appear in results

---

## ✅ Success Checklist

A complete investigation should answer:

- [ ] Is the variance data accurate?
- [ ] Should this part be excluded from validation?
- [ ] What is the root cause category?
- [ ] What is the business impact?
- [ ] What specific actions should be taken?
- [ ] Who should take action?
- [ ] What is the priority level?

---

## 📞 Support

### For Questions About:
- **Methodology:** See `AI_AGENT_GUIDE.md`
- **Template usage:** See comments in `test_template.py`
- **Example investigations:** See files in `dev/` folder
- **Pipeline setup:** See main `README.md` in project root

---

## 🔄 Version History

**v1.0** - Initial creation with comprehensive methodology guide and reusable template

---

**Happy investigating! 🔍**

