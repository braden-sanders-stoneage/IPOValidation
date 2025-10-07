"""
Scheduler Module
================

Handles scheduled validation execution and scheduler initialization.
"""

from datetime import datetime
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter
import pytz

from utils.main import load_config
from utils.validator import load_metadata, save_metadata, run_validation_job


def get_scheduler_info(config):
    """
    Calculate next scheduled run time for countdown display.
    
    Args:
        config (dict): Configuration dictionary from config.json
    
    Returns:
        dict: Scheduler information including enabled status, description, and next_run_time
    """
    scheduler_config = config.get('scheduler', {})
    enabled = scheduler_config.get('enabled', False)
    
    if not enabled:
        return {'enabled': False}
    
    # Determine schedule type and build cron expression
    schedule_type = scheduler_config.get('schedule_type', 'monthly')
    timezone_str = scheduler_config.get('timezone', 'America/Denver')
    
    if schedule_type == 'monthly':
        day = scheduler_config.get('monthly_day', 1)
        hour = scheduler_config.get('monthly_hour', 8)
        minute = scheduler_config.get('monthly_minute', 0)
        cron_expression = f"{minute} {hour} {day} * *"
        schedule_description = f"Monthly on day {day} at {hour:02d}:{minute:02d}"
    elif schedule_type == 'testing':
        cron_expression = scheduler_config.get('testing_cron', '*/5 * * * *')
        schedule_description = f"Testing: {cron_expression}"
    else:
        return {'enabled': False}
    
    # Calculate next run time
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        cron = croniter(cron_expression, now)
        next_run = cron.get_next(datetime)
        
        return {
            'enabled': True,
            'schedule_type': schedule_type,
            'description': schedule_description,
            'next_run_time': next_run.isoformat(),
            'timezone': timezone_str
        }
    except Exception as e:
        print(f"[SCHEDULER] Error calculating next run: {e}")
        return {'enabled': False}


def scheduled_validation():
    """
    Execute a scheduled validation run.
    
    This function is called by APScheduler on the configured cron schedule.
    It runs in a background thread alongside the Flask application.
    
    Creates a validation entry, executes the pipeline, and handles errors.
    """
    print("\n" + "="*80)
    print(f"[SCHEDULER] Validation triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    try:
        config = load_config()
        validation_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print(f"[SCHEDULER] Creating validation entry: {validation_id}")
        
        metadata = load_metadata()
        validation_entry = {
            'id': validation_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'date_range': {
                'start': config['validation']['start_date'],
                'end': config['validation']['end_date']
            },
            'companies': config['validation']['companies'],
            'triggered_by': 'scheduler'
        }
        metadata['validations'].insert(0, validation_entry)
        save_metadata(metadata)
        
        print(f"[SCHEDULER] Running validation pipeline...")
        
        # Run validation job (scheduler already runs in background thread)
        run_validation_job(validation_id, config)
        
        print(f"[SCHEDULER] ✓ Validation {validation_id} completed")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"[SCHEDULER] ✗ Error during scheduled validation: {e}")
        print("="*80 + "\n")


def init_scheduler(scheduler):
    """
    Initialize and start the background scheduler for automated validations.
    
    Called when the Flask app starts. Configures APScheduler with cron trigger
    and starts it in a background thread.
    
    Supports two schedule types:
    - "monthly": Runs on specified day of month at specified time (production)
    - "testing": Uses custom cron expression for testing/development
    
    Args:
        scheduler: APScheduler BackgroundScheduler instance from app.py
    """
    config = load_config()
    scheduler_config = config.get('scheduler', {})
    
    if not scheduler_config.get('enabled', False):
        print("[SCHEDULER] Disabled in config.json")
        return
    
    # Determine schedule type and build cron expression
    schedule_type = scheduler_config.get('schedule_type', 'monthly')
    timezone = scheduler_config.get('timezone', 'America/Denver')
    
    if schedule_type == 'monthly':
        # Monthly schedule: run on specific day of month at specific time
        day = scheduler_config.get('monthly_day', 1)
        hour = scheduler_config.get('monthly_hour', 8)
        minute = scheduler_config.get('monthly_minute', 0)
        cron_expression = f"{minute} {hour} {day} * *"
        schedule_description = f"Monthly on day {day} at {hour:02d}:{minute:02d}"
    elif schedule_type == 'testing':
        # Testing schedule: use custom cron expression
        cron_expression = scheduler_config.get('testing_cron', '*/5 * * * *')
        schedule_description = f"Testing interval: {cron_expression}"
    else:
        print(f"[SCHEDULER] ✗ Invalid schedule_type: {schedule_type}")
        print(f"[SCHEDULER] Valid options: 'monthly', 'testing'")
        return
    
    print("\n" + "="*80)
    print("INITIALIZING BACKGROUND SCHEDULER")
    print("="*80)
    print(f"[SCHEDULER] ✓ Scheduler ENABLED")
    print(f"[SCHEDULER] Schedule Type: {schedule_type}")
    print(f"[SCHEDULER] Schedule: {schedule_description}")
    print(f"[SCHEDULER] Cron Expression: {cron_expression}")
    print(f"[SCHEDULER] Timezone: {timezone}")
    print(f"[SCHEDULER] Validation Config:")
    print(f"  - Date Range: {config['validation']['start_date']} to {config['validation']['end_date']}")
    print(f"  - Companies: {', '.join(config['validation']['companies'])}")
    print(f"  - Notifications: {'Enabled' if config['options'].get('enable_notifications') else 'Disabled'}")
    
    try:
        scheduler.add_job(
            scheduled_validation,
            CronTrigger.from_crontab(cron_expression),
            id='validation_job',
            name='IPO Validation',
            max_instances=1,
            timezone=timezone
        )
        
        scheduler.start()
        
        # Get next run time
        jobs = scheduler.get_jobs()
        if jobs:
            next_run = jobs[0].next_run_time
            print(f"[SCHEDULER] ✓ Scheduler started in background thread")
            print(f"[SCHEDULER] Next scheduled run: {next_run}")
        else:
            print(f"[SCHEDULER] ✓ Scheduler started (no jobs scheduled)")
        
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"[SCHEDULER] ✗ Failed to start scheduler: {e}")
        print("="*80 + "\n")

