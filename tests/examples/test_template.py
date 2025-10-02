"""
Part ID Investigation Template
================================

This template provides a systematic approach to investigating individual part IDs
that appear in validation results with variance issues.

INSTRUCTIONS FOR AI AGENTS:
1. Copy this file to dev/ folder with a descriptive name (e.g., investigate_ABC123.py)
2. Update the configuration section below with the part details
3. Run the script: python dev/investigate_ABC123.py
4. Use the output to write your investigation report

For detailed methodology, see: tests/examples/AI_AGENT_GUIDE.md
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import pandas as pd
from utils.database import DatabaseConnection


# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

# Part to investigate (from validation results)
COMPANY = "SAINC"           # Company code (e.g., SAINC, SAUK, SANL)
PART_NUM = "ABC 123"        # Part number (e.g., ABX 207, GPT 082)
LOCATION = "StoneAge, Inc." # Location name from validation results
PERIOD = "2025-08-31"       # Period date (YYYY-MM-DD format, end of month)

# Expected values from validation results (for verification)
EXPECTED_ACTUAL_USAGE = 0   # actual_usage from CSV
EXPECTED_IPO_USAGE = 0      # ipo_usage from CSV
EXPECTED_VARIANCE_CATEGORY = "Missing From IP&O"  # variance_category from CSV


# ============================================================================
# INVESTIGATION SCRIPT - DO NOT MODIFY BELOW THIS LINE
# ============================================================================

print("="*80)
print(f"INVESTIGATION: {PART_NUM} - {EXPECTED_VARIANCE_CATEGORY}")
print("="*80)
print(f"\nTarget Part: {COMPANY} - {LOCATION} - {PART_NUM}")
print(f"Period: {PERIOD}")
print(f"Expected: actual_usage={EXPECTED_ACTUAL_USAGE}, ipo_usage={EXPECTED_IPO_USAGE}")
print("="*80)

# Load config
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Connect to database
db = DatabaseConnection(config['database'])
engine = db.connect()

# Initialize findings dictionary
findings = {
    'data_verified': False,
    'exclusion_criteria': {},
    'usage_pattern': {},
    'ipo_history': {},
    'root_cause': '',
    'recommendations': []
}

try:
    # =========================================================================
    # STEP 1: VERIFY RAW DATA SOURCES
    # =========================================================================
    print("\n[STEP 1/7] VERIFY RAW DATA SOURCES")
    print("-" * 80)
    
    # Query PartUsage
    print(f"\n[1.1] Querying PartUsage for {COMPANY}_MfgSys_{PART_NUM}...")
    part_usage_query = f"""
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
          AND endOfMonth = '{PERIOD}'
    """
    
    part_usage_result = pd.read_sql(part_usage_query, engine)
    print(f"Found {len(part_usage_result)} record(s):\n")
    
    if len(part_usage_result) > 0:
        print(part_usage_result.to_string(index=False))
        row = part_usage_result.iloc[0]
        calculated_usage = row['ICUsage'] + row['IndirectUsage'] + row['DirectUsage']
        print(f"\n✅ Part exists in PartUsage")
        print(f"Calculated Usage (IC+Indirect+Direct): {calculated_usage}")
        print(f"  - ICUsage: {row['ICUsage']}")
        print(f"  - IndirectUsage: {row['IndirectUsage']}")
        print(f"  - DirectUsage: {row['DirectUsage']}")
        findings['actual_usage'] = calculated_usage
    else:
        print("❌ Part NOT found in PartUsage")
        findings['actual_usage'] = 0
    
    # Query IPOValidation
    print(f"\n[1.2] Querying IPOValidation for {COMPANY} - {PART_NUM}...")
    ipo_query = f"""
        SELECT 
            Company,
            Location,
            Product,
            Period,
            Qty
        FROM IPOValidation
        WHERE Company = '{COMPANY}'
          AND Product = '{PART_NUM}'
          AND Period >= '{PERIOD[:8]}01'
          AND Period <= '{PERIOD}'
    """
    
    ipo_result = pd.read_sql(ipo_query, engine)
    print(f"Found {len(ipo_result)} record(s):\n")
    
    if len(ipo_result) > 0:
        print(ipo_result.to_string(index=False))
        print(f"\n✅ Part exists in IPOValidation")
        findings['ipo_usage'] = ipo_result.iloc[0]['Qty']
    else:
        print("❌ Part NOT found in IPOValidation")
        findings['ipo_usage'] = 0
    
    # Verify against expected values
    print(f"\n[1.3] Verification:")
    actual_match = findings.get('actual_usage', 0) == EXPECTED_ACTUAL_USAGE
    ipo_match = findings.get('ipo_usage', 0) == EXPECTED_IPO_USAGE
    
    print(f"  Actual usage matches expected: {actual_match} (Found: {findings.get('actual_usage', 0)}, Expected: {EXPECTED_ACTUAL_USAGE})")
    print(f"  IPO usage matches expected: {ipo_match} (Found: {findings.get('ipo_usage', 0)}, Expected: {EXPECTED_IPO_USAGE})")
    
    if actual_match and ipo_match:
        print("✅ Data verification PASSED")
        findings['data_verified'] = True
    else:
        print("⚠️  Data mismatch - check validation results or config")
    
    # =========================================================================
    # STEP 2: CHECK PART METADATA
    # =========================================================================
    print("\n[STEP 2/7] CHECK PART METADATA")
    print("-" * 80)
    
    metadata_query = f"""
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
    """
    
    metadata_result = pd.read_sql(metadata_query, engine)
    print(f"Found {len(metadata_result)} record(s):\n")
    
    if len(metadata_result) > 0:
        print(metadata_result.to_string(index=False))
        row = metadata_result.iloc[0]
        
        print(f"\n[2.1] Exclusion Criteria Evaluation:")
        
        # NonStock check
        nonstock_fail = row['NonStock'] == True
        findings['exclusion_criteria']['nonstock'] = nonstock_fail
        print(f"  - NonStock: {row['NonStock']} {'❌ SHOULD BE EXCLUDED' if nonstock_fail else '✅ Passes'}")
        
        # InActive check
        inactive_fail = row['InActive'] == True
        findings['exclusion_criteria']['inactive'] = inactive_fail
        print(f"  - InActive: {row['InActive']} {'❌ SHOULD BE EXCLUDED' if inactive_fail else '✅ Passes'}")
        
        # Runout check
        runout_fail = row['Runout'] == True
        findings['exclusion_criteria']['runout'] = runout_fail
        print(f"  - Runout: {row['Runout']} {'❌ SHOULD BE EXCLUDED' if runout_fail else '✅ Passes'}")
        
        # ClassID check
        classid_fail = row['ClassID'] in ['RAW', 'CSM']
        findings['exclusion_criteria']['classid'] = classid_fail
        print(f"  - ClassID: {row['ClassID']} {'❌ SHOULD BE EXCLUDED' if classid_fail else '✅ Passes'}")
        
        findings['exclusion_criteria']['any_failed'] = any([nonstock_fail, inactive_fail, runout_fail, classid_fail])
        
    else:
        print("⚠️  Part metadata not found")
    
    # =========================================================================
    # STEP 3: ANALYZE USAGE HISTORY
    # =========================================================================
    print("\n[STEP 3/7] ANALYZE USAGE HISTORY")
    print("-" * 80)
    
    print(f"\n[3.1] Last 12 Months Usage:")
    usage_history_query = f"""
        SELECT 
            endOfMonth,
            ICUsage,
            IndirectUsage,
            DirectUsage,
            (ICUsage + IndirectUsage + DirectUsage) as TotalUsage
        FROM PartUsage
        WHERE company_plant_part = '{COMPANY}_MfgSys_{PART_NUM}'
          AND endOfMonth >= DATEADD(MONTH, -12, '{PERIOD}')
        ORDER BY endOfMonth DESC
    """
    
    usage_history_result = pd.read_sql(usage_history_query, engine)
    
    if len(usage_history_result) > 0:
        print(usage_history_result.to_string(index=False))
        
        total_usage_12mo = usage_history_result['TotalUsage'].sum()
        period_count = len(usage_history_result)
        avg_usage = usage_history_result['TotalUsage'].mean()
        
        print(f"\n[3.2] Usage Summary:")
        print(f"  Total usage (12 months): {total_usage_12mo}")
        print(f"  Periods with activity: {period_count}")
        print(f"  Average usage per period: {avg_usage:.2f}")
        
        # Low usage check
        low_usage_fail = total_usage_12mo <= 2
        findings['exclusion_criteria']['low_usage'] = low_usage_fail
        
        if low_usage_fail:
            print(f"  ❌ SHOULD BE EXCLUDED - Low usage (≤2 units/12mo)")
        else:
            print(f"  ✅ Passes low usage threshold ({total_usage_12mo} > 2)")
        
        findings['usage_pattern'] = {
            'total_12mo': total_usage_12mo,
            'period_count': period_count,
            'avg_per_period': avg_usage,
            'low_usage': low_usage_fail
        }
        
        # Update overall exclusion check
        if findings['exclusion_criteria'].get('any_failed') is not None:
            findings['exclusion_criteria']['any_failed'] = findings['exclusion_criteria']['any_failed'] or low_usage_fail
    else:
        print("  No usage history found in last 12 months")
        findings['usage_pattern']['total_12mo'] = 0
    
    # All-time stats
    print(f"\n[3.3] All-Time Usage Statistics:")
    alltime_query = f"""
        SELECT 
            COUNT(*) as PeriodCount,
            MIN(endOfMonth) as FirstUsage,
            MAX(endOfMonth) as LastUsage,
            SUM(ICUsage + IndirectUsage + DirectUsage) as TotalUsage,
            AVG(ICUsage + IndirectUsage + DirectUsage) as AvgUsagePerPeriod
        FROM PartUsage
        WHERE company_plant_part = '{COMPANY}_MfgSys_{PART_NUM}'
    """
    
    alltime_result = pd.read_sql(alltime_query, engine)
    print(alltime_result.to_string(index=False))
    
    # =========================================================================
    # STEP 4: CHECK IP&O HISTORICAL PRESENCE
    # =========================================================================
    print("\n[STEP 4/7] CHECK IP&O HISTORICAL PRESENCE")
    print("-" * 80)
    
    ipo_history_query = f"""
        SELECT 
            COUNT(*) as RecordCount,
            MIN(Period) as FirstPeriod,
            MAX(Period) as LastPeriod,
            SUM(Qty) as TotalQty
        FROM IPOValidation
        WHERE Company = '{COMPANY}'
          AND Product = '{PART_NUM}'
    """
    
    ipo_history_result = pd.read_sql(ipo_history_query, engine)
    record_count = ipo_history_result.iloc[0]['RecordCount']
    
    print(f"Total records in IPOValidation (all time): {record_count}")
    
    if record_count > 0:
        print(f"First Period: {ipo_history_result.iloc[0]['FirstPeriod']}")
        print(f"Last Period: {ipo_history_result.iloc[0]['LastPeriod']}")
        print(f"Total Qty: {ipo_history_result.iloc[0]['TotalQty']}")
        findings['ipo_history']['ever_in_ipo'] = True
        findings['ipo_history']['record_count'] = record_count
    else:
        print("❌ This part has NEVER been sent to IP&O system")
        findings['ipo_history']['ever_in_ipo'] = False
        findings['ipo_history']['record_count'] = 0
    
    # =========================================================================
    # STEP 5: EVALUATE EXCLUSION CRITERIA
    # =========================================================================
    print("\n[STEP 5/7] EVALUATE EXCLUSION CRITERIA")
    print("-" * 80)
    
    print(f"\nCurrent config setting:")
    print(f"  apply_exclusions: {config['options']['apply_exclusions']}")
    
    if config['options']['apply_exclusions']:
        print("  ✅ Exclusions are ENABLED - Parts meeting exclusion criteria are filtered")
    else:
        print("  ⚠️  Exclusions are DISABLED - All parts are being validated")
    
    print(f"\nExclusion criteria summary:")
    for criterion, failed in findings['exclusion_criteria'].items():
        if criterion != 'any_failed':
            status = "❌ Fails" if failed else "✅ Passes"
            print(f"  - {criterion}: {status}")
    
    should_be_excluded = findings['exclusion_criteria'].get('any_failed', False)
    
    if should_be_excluded:
        print(f"\n⚠️  This part SHOULD BE EXCLUDED from validation")
    else:
        print(f"\n✅ This part SHOULD BE VALIDATED (passes all exclusion criteria)")
    
    findings['should_be_excluded'] = should_be_excluded
    
    # =========================================================================
    # STEP 6: IDENTIFY ROOT CAUSE
    # =========================================================================
    print("\n[STEP 6/7] IDENTIFY ROOT CAUSE")
    print("-" * 80)
    
    # Root cause classification logic
    if should_be_excluded and not config['options']['apply_exclusions']:
        findings['root_cause'] = 'CONFIGURATION_ISSUE'
        print("\n🔧 ROOT CAUSE: Configuration Issue")
        print("  - Part meets exclusion criteria")
        print("  - Exclusions are disabled in config")
        print("  - Part should be filtered out but isn't")
        print("\n💡 This is NOT a data issue - it's a configuration choice")
        
    elif not should_be_excluded and not findings['ipo_history']['ever_in_ipo']:
        findings['root_cause'] = 'LEGITIMATE_MISSING_PART'
        print("\n⚠️  ROOT CAUSE: Legitimate Missing Part")
        print("  - Part is stocked, active, with significant usage")
        print("  - Part passes all exclusion criteria")
        print("  - Part has NEVER been added to IP&O system")
        print("\n💡 This IS a legitimate data integrity issue")
        
    elif not should_be_excluded and findings['ipo_history']['ever_in_ipo'] and findings.get('ipo_usage', 0) == 0:
        findings['root_cause'] = 'DATA_SYNC_ISSUE'
        print("\n🔌 ROOT CAUSE: Data Sync Issue")
        print("  - Part was in IP&O but stopped appearing")
        print("  - Part still has actual usage")
        print("  - Integration may have failed")
        print("\n💡 This may be a system/interface issue")
        
    elif findings.get('actual_usage', 0) > 0 and findings.get('ipo_usage', 0) > 0:
        findings['root_cause'] = 'FORECASTING_ACCURACY'
        print("\n📊 ROOT CAUSE: Forecasting Accuracy Issue")
        print("  - Part exists in both systems")
        print("  - Variance is due to forecast accuracy")
        print("  - May need parameter adjustment")
        print("\n💡 This is an operational forecasting issue")
        
    else:
        findings['root_cause'] = 'UNKNOWN'
        print("\n❓ ROOT CAUSE: Unknown - requires manual review")
    
    # =========================================================================
    # STEP 7: PROVIDE RECOMMENDATIONS
    # =========================================================================
    print("\n[STEP 7/7] PROVIDE RECOMMENDATIONS")
    print("-" * 80)
    
    print("\n💡 RECOMMENDATIONS:\n")
    
    if findings['root_cause'] == 'CONFIGURATION_ISSUE':
        print("  IMMEDIATE:")
        print("    1. If exclusions are intended: Set 'apply_exclusions: true' in config.json")
        print("    2. If validating all parts: Accept this as expected behavior")
        print("\n  ACTION OWNER: Configuration/Admin team")
        print("  PRIORITY: Low (configuration choice)")
        print("\n  VERDICT: NOT A DATA ISSUE - Configuration choice")
        
    elif findings['root_cause'] == 'LEGITIMATE_MISSING_PART':
        print("  IMMEDIATE:")
        print(f"    1. Review {PART_NUM} with procurement/planning team")
        print(f"    2. Add {PART_NUM} to IP&O forecasting system")
        print(f"    3. Configure appropriate forecasting parameters")
        print("\n  FOLLOW-UP:")
        print("    1. Check if other similar parts are missing")
        print("    2. Review part setup process to prevent future gaps")
        print("\n  ACTION OWNER: Procurement/Planning team")
        
        # Determine priority based on usage
        usage_12mo = findings['usage_pattern'].get('total_12mo', 0)
        if usage_12mo > 50:
            priority = "High"
        elif usage_12mo > 10:
            priority = "Medium"
        else:
            priority = "Low"
        
        print(f"  PRIORITY: {priority} (based on {usage_12mo} units/12mo usage)")
        print("\n  VERDICT: LEGITIMATE DATA INTEGRITY ISSUE - Requires action")
        
    elif findings['root_cause'] == 'DATA_SYNC_ISSUE':
        print("  IMMEDIATE:")
        print("    1. Check integration logs for errors")
        print("    2. Verify IP&O system connectivity")
        print("    3. Restart data sync if needed")
        print("\n  ACTION OWNER: IT/Integration team")
        print("  PRIORITY: High (system issue)")
        print("\n  VERDICT: SYSTEM ISSUE - Check integration")
        
    elif findings['root_cause'] == 'FORECASTING_ACCURACY':
        print("  IMMEDIATE:")
        print("    1. Review forecasting parameters for this part")
        print("    2. Check if forecast model needs adjustment")
        print("    3. Consider seasonality or trend changes")
        print("\n  ACTION OWNER: Planning/Forecasting team")
        print("  PRIORITY: Medium (operational improvement)")
        print("\n  VERDICT: FORECASTING ISSUE - Review parameters")
        
    else:
        print("  IMMEDIATE:")
        print("    1. Manual investigation required")
        print("    2. Review all data points above")
        print("    3. Consult with subject matter expert")
        print("\n  ACTION OWNER: Analysis team")
        print("  PRIORITY: Medium")
        print("\n  VERDICT: UNKNOWN - Requires manual review")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("INVESTIGATION SUMMARY")
    print("="*80)
    
    print(f"\n✅ DATA VERIFICATION:")
    print(f"  - Part in PartUsage: {'Yes' if findings.get('actual_usage', 0) > 0 else 'No'}")
    print(f"  - Part in IPOValidation: {'Yes' if findings.get('ipo_usage', 0) > 0 else 'No'}")
    print(f"  - Actual usage: {findings.get('actual_usage', 0)}")
    print(f"  - IPO usage: {findings.get('ipo_usage', 0)}")
    
    print(f"\n{'✅' if not should_be_excluded else '❌'} EXCLUSION CRITERIA:")
    if should_be_excluded:
        print(f"  - Part SHOULD BE EXCLUDED (meets exclusion criteria)")
    else:
        print(f"  - Part SHOULD BE VALIDATED (passes all criteria)")
    
    print(f"\n📊 USAGE PATTERN:")
    print(f"  - Last 12 months: {findings['usage_pattern'].get('total_12mo', 0)} units")
    print(f"  - Active periods: {findings['usage_pattern'].get('period_count', 0)}")
    
    print(f"\n🎯 ROOT CAUSE: {findings['root_cause']}")
    
    print("\n" + "="*80)
    print("Investigation complete!")
    print("="*80)

finally:
    db.close()

# ============================================================================
# INVESTIGATION COMPLETE
# ============================================================================

print("\n📝 NEXT STEPS:")
print("  1. Review the findings above")
print("  2. Create investigation report in dev/ folder")
print("  3. Share recommendations with appropriate team")
print("\n  See tests/examples/AI_AGENT_GUIDE.md for report template")

