"""
IPO Validation Pipeline - Main Orchestration

Compares PartUsage (Epicor actual usage) vs IPOValidation (sent to IP&O software)
to identify data integrity issues and forecast variances.
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path

from utils.database import DatabaseConnection, query_part_usage, query_ipo_validation, query_part_metadata
from utils.utils import (
    normalize_part_usage,
    normalize_ipo_validation,
    apply_exclusions,
    compare_datasets,
    add_variance_categories
)


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config(config_path: str = "config.json") -> dict:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    print(f"[CONFIG] Loading configuration from {config_path}...")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print(f"[CONFIG] ✓ Configuration loaded")
    print(f"[CONFIG] Database: {config['database']['server']}.{config['database']['database']}")
    print(f"[CONFIG] Date range: {config['validation']['start_date']} to {config['validation']['end_date']}")
    print(f"[CONFIG] Companies: {', '.join(config['validation']['companies'])}")
    
    return config


# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def run_validation_pipeline(config: dict) -> pd.DataFrame:
    """
    Main orchestration function for validation pipeline
    
    Pipeline steps:
    1. Connect to database
    2. Query PartUsage and IPOValidation tables
    3. Normalize both datasets
    4. [Optional] Query metadata and apply exclusions
    5. Compare the two normalized datasets
    6. Categorize variances
    7. Return final DataFrame
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Final validation results DataFrame
    """
    print("\n" + "="*80)
    print("IPO VALIDATION PIPELINE - STARTING")
    print("="*80 + "\n")
    
    start_time = datetime.now()
    
    # -------------------------------------------------------------------------
    # STEP 1: Connect to Database
    # -------------------------------------------------------------------------
    print("\n[STEP 1/7] DATABASE CONNECTION")
    print("-" * 80)
    
    db = DatabaseConnection(config['database'])
    engine = db.connect()
    
    try:
        # ---------------------------------------------------------------------
        # STEP 2: Extract Data
        # ---------------------------------------------------------------------
        print("\n[STEP 2/7] DATA EXTRACTION")
        print("-" * 80)
        
        # Query PartUsage
        part_usage_raw = query_part_usage(
            engine,
            config['validation']['start_date'],
            config['validation']['end_date']
        )
        
        # Query IPOValidation
        ipo_validation_raw = query_ipo_validation(
            engine,
            config['validation']['start_date'],
            config['validation']['end_date']
        )
        
        # Optional: Query metadata for exclusions
        if config['options']['apply_exclusions']:
            part_metadata = query_part_metadata(
                engine,
                config['validation']['companies']
            )
        
        # ---------------------------------------------------------------------
        # STEP 3: Normalize PartUsage
        # ---------------------------------------------------------------------
        print("\n[STEP 3/7] NORMALIZE PARTUSAGE")
        print("-" * 80)
        
        part_usage_normalized = normalize_part_usage(part_usage_raw, config)
        
        # ---------------------------------------------------------------------
        # STEP 4: Normalize IPOValidation
        # ---------------------------------------------------------------------
        print("\n[STEP 4/7] NORMALIZE IPOVALIDATION")
        print("-" * 80)
        
        ipo_validation_normalized = normalize_ipo_validation(ipo_validation_raw)
        
        # ---------------------------------------------------------------------
        # STEP 5: Apply Exclusions (Optional)
        # ---------------------------------------------------------------------
        if config['options']['apply_exclusions']:
            print("\n[STEP 5/7] APPLY EXCLUSIONS")
            print("-" * 80)
            
            part_usage_normalized = apply_exclusions(
                part_usage_normalized,
                part_metadata
            )
        else:
            print("\n[STEP 5/7] APPLY EXCLUSIONS - SKIPPED")
            print("-" * 80)
            print("[EXCLUSIONS] Exclusions disabled in config")
            # Drop plant column since it's not needed in output
            if 'plant' in part_usage_normalized.columns:
                part_usage_normalized = part_usage_normalized.drop(columns=['plant'])
        
        # ---------------------------------------------------------------------
        # STEP 6: Compare Datasets
        # ---------------------------------------------------------------------
        print("\n[STEP 6/7] COMPARE DATASETS")
        print("-" * 80)
        
        comparison_results = compare_datasets(
            part_usage_normalized,
            ipo_validation_normalized
        )
        
        # ---------------------------------------------------------------------
        # STEP 7: Categorize Variances
        # ---------------------------------------------------------------------
        print("\n[STEP 7/7] CATEGORIZE VARIANCES")
        print("-" * 80)
        
        final_results = add_variance_categories(comparison_results)
        
        # ---------------------------------------------------------------------
        # Pipeline Complete
        # ---------------------------------------------------------------------
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*80)
        print("PIPELINE COMPLETE")
        print("="*80)
        print(f"[SUMMARY] Total records: {len(final_results):,}")
        print(f"[SUMMARY] Execution time: {duration:.2f} seconds")
        print(f"[SUMMARY] Records per second: {len(final_results)/duration:,.0f}")
        
        return final_results
        
    finally:
        # Always close database connection
        db.close()


# ============================================================================
# OUTPUT MANAGEMENT
# ============================================================================

def save_results(df: pd.DataFrame, output_path: str, output_format: str = "csv"):
    """
    Save validation results to file
    
    Args:
        df: Results DataFrame
        output_path: Output file path
        output_format: Output format ('csv', 'excel', 'parquet')
    """
    print(f"\n[OUTPUT] Saving results to {output_path}...")
    
    # Create output directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save based on format
    if output_format == 'csv':
        df.to_csv(output_path, index=False)
    elif output_format == 'excel':
        df.to_excel(output_path, index=False, engine='openpyxl')
    elif output_format == 'parquet':
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    file_size = output_file.stat().st_size / 1024 / 1024  # Convert to MB
    print(f"[OUTPUT] ✓ Saved {len(df):,} rows ({file_size:.2f} MB)")


def print_summary_statistics(df: pd.DataFrame):
    """
    Print summary statistics about validation results
    
    Args:
        df: Results DataFrame
    """
    print("\n" + "="*80)
    print("VALIDATION SUMMARY STATISTICS")
    print("="*80)
    
    # Overall metrics
    total_records = len(df)
    total_variance_count = len(df[df['variance_category'] != 'PERFECT_MATCH'])
    variance_percentage = total_variance_count / total_records * 100 if total_records > 0 else 0
    
    print(f"\n[METRICS] Total Records: {total_records:,}")
    print(f"[METRICS] Total Variances: {total_variance_count:,} ({variance_percentage:.1f}%)")
    print(f"[METRICS] Perfect Matches: {len(df[df['variance_category'] == 'PERFECT_MATCH']):,}")
    
    # Critical issues
    critical_issues = len(df[df['variance_category'].isin(['MISSING_FROM_IPO', 'MISSING_FROM_USAGE'])])
    print(f"[METRICS] Critical Issues: {critical_issues:,}")
    
    # Variance category breakdown
    print("\n[BREAKDOWN] By Variance Category:")
    category_counts = df['variance_category'].value_counts()
    for category, count in category_counts.items():
        percentage = count / total_records * 100
        print(f"  {category:25} {count:8,} ({percentage:5.1f}%)")
    
    # Company breakdown
    print("\n[BREAKDOWN] By Company:")
    company_counts = df['company'].value_counts()
    for company, count in company_counts.items():
        percentage = count / total_records * 100
        print(f"  {company:25} {count:8,} ({percentage:5.1f}%)")
    
    # Variance category by Company
    print("\n[BREAKDOWN] Variance Category by Company:")
    for company in sorted(df['company'].unique()):
        company_df = df[df['company'] == company]
        company_total = len(company_df)
        print(f"\n  {company} ({company_total:,} records):")
        
        category_counts = company_df['variance_category'].value_counts()
        for category, count in category_counts.items():
            percentage = count / company_total * 100
            print(f"    {category:25} {count:6,} ({percentage:5.1f}%)")
    
    # Variance category by Location
    print("\n[BREAKDOWN] Variance Category by Location:")
    for location in sorted(df['location'].unique()):
        location_df = df[df['location'] == location]
        location_total = len(location_df)
        print(f"\n  {location} ({location_total:,} records):")
        
        category_counts = location_df['variance_category'].value_counts()
        for category, count in category_counts.items():
            percentage = count / location_total * 100
            print(f"    {category:25} {count:6,} ({percentage:5.1f}%)")
    
    # Date range
    print("\n[DATE RANGE]")
    print(f"  Earliest Period: {df['period'].min().date()}")
    print(f"  Latest Period: {df['period'].max().date()}")
    print(f"  Total Months: {df['period'].nunique()}")
    
    # Variance magnitudes
    print("\n[VARIANCE MAGNITUDES]")
    variance_stats = df['absolute_variance'].describe()
    print(f"  Mean Absolute Variance: {variance_stats['mean']:.2f}")
    print(f"  Median Absolute Variance: {variance_stats['50%']:.2f}")
    print(f"  Max Absolute Variance: {variance_stats['max']:.2f}")
    print(f"  Total Absolute Variance: {df['absolute_variance'].sum():,.2f}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    Main entry point for validation pipeline
    """
    try:
        # Load configuration
        config = load_config()
        
        # Run validation pipeline
        results = run_validation_pipeline(config)
        
        # Print summary statistics
        print_summary_statistics(results)
        
        # Save results
        output_path = config['options']['output_path']
        output_format = config['options']['output_format']
        save_results(results, output_path, output_format)
        
        print("\n" + "="*80)
        print("✓ VALIDATION COMPLETE - ALL STEPS SUCCESSFUL")
        print("="*80 + "\n")
        
        return results
        
    except Exception as e:
        print("\n" + "="*80)
        print("✗ ERROR - PIPELINE FAILED")
        print("="*80)
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        print("\nPlease check the error message above and fix the issue.")
        raise


if __name__ == "__main__":
    results = main()

