"""
Validation Management Module
============================

Handles validation job execution, metadata management, and result storage.
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd

from utils.main import run_validation_pipeline
from utils.notifications import send_validation_notification


# Validation storage configuration
VALIDATIONS_DIR = Path('validations')
METADATA_FILE = VALIDATIONS_DIR / 'metadata.json'

# Ensure validations directory exists
VALIDATIONS_DIR.mkdir(exist_ok=True)
if not METADATA_FILE.exists():
    METADATA_FILE.write_text(json.dumps({'validations': []}, indent=2))


def load_metadata():
    """
    Load validation metadata from JSON file.
    
    Returns:
        dict: Metadata dictionary with 'validations' list
    """
    try:
        with open(METADATA_FILE, 'r') as f:
            content = f.read()
            if not content.strip():
                return {'validations': []}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {'validations': []}


def save_metadata(metadata):
    """
    Save validation metadata to JSON file.
    
    Args:
        metadata (dict): Metadata dictionary to save
    """
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def run_validation_job(validation_id, config):
    """
    Execute a validation job.
    
    This function is called by both manual (Flask-Executor) and scheduled 
    (APScheduler) validations. It orchestrates the entire validation process:
    - Updates status to 'running'
    - Executes the validation pipeline
    - Saves results to CSV
    - Updates metadata with completion status
    - Sends email notification (if enabled)
    
    Args:
        validation_id (str): Unique validation identifier (timestamp format)
        config (dict): Configuration dictionary from config.json
    """
    print("\n" + "="*80)
    print(f"[VALIDATION JOB] Starting validation: {validation_id}")
    print("="*80)
    
    metadata = load_metadata()
    validation_entry = next((v for v in metadata['validations'] if v['id'] == validation_id), None)
    
    if not validation_entry:
        print(f"[VALIDATION JOB] ✗ Error: Validation entry not found for {validation_id}")
        return
    
    trigger_type = validation_entry.get('triggered_by', 'manual')
    print(f"[VALIDATION JOB] Trigger type: {trigger_type}")
    print(f"[VALIDATION JOB] Date range: {validation_entry['date_range']['start']} to {validation_entry['date_range']['end']}")
    print(f"[VALIDATION JOB] Companies: {', '.join(validation_entry['companies'])}")
    
    try:
        print(f"[VALIDATION JOB] Updating status to 'running'...")
        validation_entry['status'] = 'running'
        save_metadata(metadata)
        
        print(f"[VALIDATION JOB] Executing validation pipeline...")
        start_time = datetime.now()
        results = run_validation_pipeline(config)
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        print(f"[VALIDATION JOB] Pipeline completed in {execution_time:.2f} seconds")
        
        output_path = VALIDATIONS_DIR / f'{validation_id}.csv'
        print(f"[VALIDATION JOB] Saving results to: {output_path}")
        results.to_csv(output_path, index=False)
        
        total_records = len(results)
        critical_issues = len(results[results['variance_category'].isin(['Missing From IP&O', 'Missing From Usage'])])
        
        print(f"[VALIDATION JOB] Results summary:")
        print(f"  - Total records: {total_records:,}")
        print(f"  - Critical issues: {critical_issues:,}")
        print(f"  - Execution time: {execution_time:.2f}s")
        
        validation_entry['status'] = 'completed'
        validation_entry['total_records'] = total_records
        validation_entry['critical_issues'] = critical_issues
        validation_entry['execution_time'] = execution_time
        save_metadata(metadata)
        
        print(f"[VALIDATION JOB] Metadata updated with completion status")
        
        if config.get('options', {}).get('enable_notifications', False):
            print(f"[VALIDATION JOB] Email notifications enabled - sending...")
            try:
                send_validation_notification(validation_id)
                print(f"[VALIDATION JOB] ✓ Email notification sent successfully")
            except Exception as email_error:
                print(f"[VALIDATION JOB] ✗ Email notification failed: {email_error}")
        else:
            print(f"[VALIDATION JOB] Email notifications disabled in config")
        
        print(f"[VALIDATION JOB] ✓ Validation {validation_id} completed successfully")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"[VALIDATION JOB] ✗ Validation failed with error: {e}")
        validation_entry['status'] = 'failed'
        validation_entry['error'] = str(e)
        save_metadata(metadata)
        print(f"[VALIDATION JOB] Metadata updated with failed status")
        print("="*80 + "\n")
        raise

