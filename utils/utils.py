"""
Data transformation utilities for IPO Validation
"""

import pandas as pd
import numpy as np
from datetime import datetime


# ============================================================================
# SECTION 1: PARSING
# ============================================================================

def parse_composite_key(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse 'company_plant_part' into separate columns
    
    Format: "COMPANY_PLANT_PARTNUM"
    Example: "SAINC_MfgSys_ABX 326" → Company="SAINC", Plant="MfgSys", PartNum="ABX 326"
    
    Args:
        df: DataFrame with 'company_plant_part' column
        
    Returns:
        DataFrame with added columns: Company, Plant, PartNum
    """
    print("[PARSING] Extracting Company, Plant, and PartNum from composite key...")
    
    # Split on underscore, limit to 2 splits (handles part numbers with underscores)
    split_data = df['company_plant_part'].str.split('_', n=2, expand=True)
    
    df['Company'] = split_data[0]
    df['Plant'] = split_data[1]
    df['PartNum'] = split_data[2]
    
    # Count unique combinations
    unique_companies = df['Company'].nunique()
    unique_plants = df['Plant'].nunique()
    unique_parts = df['PartNum'].nunique()
    
    print(f"[PARSING] ✓ Parsed into {unique_companies} companies, {unique_plants} plants, {unique_parts} parts")
    
    return df


# ============================================================================
# SECTION 2: NORMALIZATION
# ============================================================================

def normalize_part_usage(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Normalize PartUsage data into standardized format
    
    Steps:
    1. Parse composite key
    2. Map plant codes to location names
    3. Calculate usage based on business rules
    4. Standardize column names
    5. Normalize dates to end-of-month
    
    Args:
        df: Raw PartUsage DataFrame
        config: Configuration dictionary with mappings and rules
        
    Returns:
        Normalized DataFrame with columns:
        - company, location, plant, part_num, period, actual_usage
    """
    print("[NORMALIZE] Normalizing PartUsage data...")
    print(f"[NORMALIZE] Input: {len(df):,} rows")
    
    # Step 1: Parse composite key
    df = parse_composite_key(df)
    
    # Step 2: Map locations
    print("[NORMALIZE] Mapping plant codes to location names...")
    df['Location'] = df.apply(
        lambda row: map_location(row['Company'], row['Plant'], config['mappings']['locations']),
        axis=1
    )
    
    # Step 3: Calculate usage based on business rules
    print("[NORMALIZE] Calculating usage based on business rules...")
    df['CalculatedUsage'] = df.apply(
        lambda row: calculate_usage(row, config['rules']['usage_calculation']),
        axis=1
    )
    
    # Step 4: Normalize dates to end-of-month
    print("[NORMALIZE] Normalizing dates to end-of-month...")
    df['Period'] = pd.to_datetime(df['endOfMonth'])
    df['Period'] = df['Period'] + pd.offsets.MonthEnd(0)
    
    # Step 5: Filter excluded companies
    if config['validation']['excluded_companies']:
        excluded = config['validation']['excluded_companies']
        initial_count = len(df)
        df = df[~df['Company'].isin(excluded)]
        excluded_count = initial_count - len(df)
        if excluded_count > 0:
            print(f"[NORMALIZE] Excluded {excluded_count:,} rows from companies: {', '.join(excluded)}")
    
    # Step 6: Standardize output schema
    output_df = pd.DataFrame({
        'company': df['Company'],
        'location': df['Location'],
        'plant': df['Plant'],
        'part_num': df['PartNum'],
        'period': df['Period'],
        'actual_usage': df['CalculatedUsage']
    })
    
    print(f"[NORMALIZE] ✓ Output: {len(output_df):,} rows")
    print(f"[NORMALIZE] ✓ Date range: {output_df['period'].min().date()} to {output_df['period'].max().date()}")
    
    return output_df


def normalize_ipo_validation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize IPOValidation data into standardized format
    
    Steps:
    1. Standardize column names
    2. Normalize dates to end-of-month
    
    Args:
        df: Raw IPOValidation DataFrame
        
    Returns:
        Normalized DataFrame with columns:
        - company, location, part_num, period, ipo_usage
    """
    print("[NORMALIZE] Normalizing IPOValidation data...")
    print(f"[NORMALIZE] Input: {len(df):,} rows")
    
    # Step 1: Normalize dates to end-of-month
    print("[NORMALIZE] Normalizing dates to end-of-month...")
    df['Period'] = pd.to_datetime(df['Period'])
    df['Period'] = df['Period'] + pd.offsets.MonthEnd(0)
    
    # Step 2: Standardize output schema
    output_df = pd.DataFrame({
        'company': df['Company'],
        'location': df['Location'],
        'part_num': df['Product'],
        'period': df['Period'],
        'ipo_usage': df['Qty']
    })
    
    print(f"[NORMALIZE] ✓ Output: {len(output_df):,} rows")
    print(f"[NORMALIZE] ✓ Date range: {output_df['period'].min().date()} to {output_df['period'].max().date()}")
    
    return output_df


def map_location(company: str, plant: str, mappings: dict) -> str:
    """
    Map (Company, Plant) combination to business-friendly location name
    
    Args:
        company: Company code (e.g., 'SAINC')
        plant: Plant code (e.g., 'SAILA')
        mappings: Location mappings from config
        
    Returns:
        Location name (e.g., 'StoneAge Louisiana')
    """
    if company in mappings and plant in mappings[company]:
        return mappings[company][plant]
    else:
        return f"UNMAPPED_LOCATION_{company}_{plant}"


def calculate_usage(row, rules: dict) -> float:
    """
    Calculate usage based on business rules
    
    Rules:
    - SAINC MfgSys: ICUsage + IndirectUsage + DirectUsage
    - All other locations: DirectUsage only
    
    Args:
        row: DataFrame row with usage columns
        rules: Usage calculation rules from config
        
    Returns:
        Calculated usage value
    """
    if row['Company'] == 'SAINC' and row['Plant'] == 'MfgSys':
        # Special case: sum multiple components
        components = rules['sainc_mfgsys_components']
        return sum(row.get(comp, 0) for comp in components)
    else:
        # Default case: use DirectUsage only
        return row.get(rules['default_component'], 0)


# ============================================================================
# SECTION 3: FILTERING / EXCLUSIONS
# ============================================================================

def apply_exclusions(df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply exclusion rules to filter out parts that shouldn't be validated
    
    Exclusion criteria:
    - Inactive parts
    - Runout parts
    - NonStock parts
    - RAW/CSM classification
    - IPO Method (Number02) values 1, 2, 3 (parts not planned in IP&O)
    
    Args:
        df: Normalized usage DataFrame
        metadata_df: Part metadata from database
        
    Returns:
        Filtered DataFrame
    """
    print("[EXCLUSIONS] Applying exclusion rules...")
    initial_count = len(df)
    
    # Create exclusion list
    excluded_parts = metadata_df[
        (metadata_df['InActive'] == True) |
        (metadata_df['Runout'] == True) |
        (metadata_df['NonStock'] == True) |
        (metadata_df['ClassID'].isin(['RAW', 'CSM'])) |
        (metadata_df['Number02'].isin([1, 2, 3, '1', '2', '3']))
    ]
    
    # Create exclusion keys
    exclusion_keys = set(
        zip(excluded_parts['Company'], excluded_parts['Plant'], excluded_parts['PartNum'])
    )
    
    # Filter out excluded parts
    df['_exclude_key'] = list(zip(df['company'], df['plant'], df['part_num']))
    df = df[~df['_exclude_key'].isin(exclusion_keys)]
    df = df.drop(columns=['_exclude_key', 'plant'])  # Drop temporary columns
    
    excluded_count = initial_count - len(df)
    print(f"[EXCLUSIONS] ✓ Excluded {excluded_count:,} rows ({excluded_count/initial_count*100:.1f}%)")
    print(f"[EXCLUSIONS] ✓ Remaining: {len(df):,} rows")
    
    return df


# ============================================================================
# SECTION 4: COMPARISON
# ============================================================================

def compare_datasets(part_usage_df: pd.DataFrame, ipo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare PartUsage vs IPOValidation datasets
    
    Performs FULL OUTER JOIN on (company, location, part_num, period)
    Calculates variance metrics
    
    Args:
        part_usage_df: Normalized PartUsage DataFrame
        ipo_df: Normalized IPOValidation DataFrame
        
    Returns:
        Comparison DataFrame with variance metrics
    """
    print("[COMPARISON] Comparing PartUsage vs IPOValidation...")
    print(f"[COMPARISON] PartUsage records: {len(part_usage_df):,}")
    print(f"[COMPARISON] IPOValidation records: {len(ipo_df):,}")
    
    # Perform FULL OUTER JOIN
    merge_keys = ['company', 'location', 'part_num', 'period']
    result = pd.merge(
        part_usage_df,
        ipo_df,
        on=merge_keys,
        how='outer',
        indicator=True
    )
    
    # Fill NaN values with 0 for usage columns
    result['actual_usage'] = result['actual_usage'].fillna(0)
    result['ipo_usage'] = result['ipo_usage'].fillna(0)
    
    # Calculate variance (IPO - Actual)
    result['variance'] = result['ipo_usage'] - result['actual_usage']
    
    # Calculate percentage variance
    print("[COMPARISON] Calculating variance percentages...")
    result['variance_percent'] = result.apply(
        lambda row: calculate_variance_percent(row['actual_usage'], row['ipo_usage']),
        axis=1
    )
    
    # Calculate absolute variance
    result['absolute_variance'] = result['variance'].abs()
    
    # Drop merge indicator
    result = result.drop(columns=['_merge'])
    
    print(f"[COMPARISON] ✓ Total comparison records: {len(result):,}")
    
    # Summary statistics
    only_in_usage = len(part_usage_df) - len(result[result['ipo_usage'] > 0])
    only_in_ipo = len(ipo_df) - len(result[result['actual_usage'] > 0])
    in_both = len(result[(result['actual_usage'] > 0) & (result['ipo_usage'] > 0)])
    
    print(f"[COMPARISON] Records only in PartUsage: {only_in_usage:,}")
    print(f"[COMPARISON] Records only in IPOValidation: {only_in_ipo:,}")
    print(f"[COMPARISON] Records in both: {in_both:,}")
    
    return result


def calculate_variance_percent(actual: float, ipo: float) -> float:
    """
    Calculate percentage variance with edge case handling
    
    Edge cases:
    - Both zero: 0% variance (perfect match)
    - Actual is zero, IPO has data: 999.99 (flag for infinite variance)
    - IPO is zero, Actual has data: -999.99 (flag for missing from IPO)
    
    Args:
        actual: Actual usage value
        ipo: IPO usage value
        
    Returns:
        Variance percentage
    """
    actual = float(actual) if not pd.isna(actual) else 0.0
    ipo = float(ipo) if not pd.isna(ipo) else 0.0
    
    # Both zero: perfect match
    if actual == 0 and ipo == 0:
        return 0.0
    
    # Actual is zero, IPO has data: infinite variance
    if actual == 0 and ipo != 0:
        return 999.99
    
    # IPO is zero, Actual has data: negative infinite variance
    if actual != 0 and ipo == 0:
        return -999.99
    
    # Normal case: calculate percentage variance
    return round(abs(ipo - actual) * 100.0 / actual, 2)


# ============================================================================
# SECTION 5: CATEGORIZATION
# ============================================================================

def categorize_variance(row) -> str:
    """
    Categorize variance type
    
    Categories:
    - Perfect Match: Exact match (actual == ipo)
    - Missing From IP&O: Actual usage occurred but IPO got zero (critical)
    - Missing From Usage: IPO has data but no actual usage recorded
    - More In Usage: Actual usage higher than IPO (underforecast)
    - More In IP&O: IPO shows higher usage than actual (overforecast)
    
    Args:
        row: DataFrame row with actual_usage and ipo_usage
        
    Returns:
        Variance category string
    """
    actual = row['actual_usage']
    ipo = row['ipo_usage']
    
    # Exact match
    if abs(ipo - actual) == 0:
        return 'Perfect Match'
    
    # IPO has data but no actual usage
    if actual == 0 and ipo != 0:
        return 'Missing From Usage'
    
    # Actual usage occurred but IPO got zero (CRITICAL)
    if actual != 0 and ipo == 0:
        return 'Missing From IP&O'
    
    # IPO shows higher usage than actual
    if ipo > actual:
        return 'More In IP&O'
    
    # Actual usage higher than IPO
    if actual > ipo:
        return 'More In Usage'
    
    return 'ERROR'


def add_variance_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add variance category column to comparison DataFrame
    
    Args:
        df: Comparison DataFrame with actual_usage and ipo_usage
        
    Returns:
        DataFrame with added 'variance_category' column
    """
    print("[CATEGORIZATION] Categorizing variance types...")
    
    df['variance_category'] = df.apply(categorize_variance, axis=1)
    
    # Print category distribution
    category_counts = df['variance_category'].value_counts()
    print("[CATEGORIZATION] Variance distribution:")
    for category, count in category_counts.items():
        percentage = count / len(df) * 100
        print(f"[CATEGORIZATION]   {category}: {count:,} ({percentage:.1f}%)")
    
    return df

