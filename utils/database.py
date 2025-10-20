"""
Database connection and query utilities for IPO Validation
"""

import os
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

class DatabaseConnection:
    """Manage SQL Server database connection"""
    
    def __init__(self, config: dict):
        """
        Initialize database connection
        
        Args:
            config: Database configuration dictionary
        """
        self.config = config
        self.engine = None
        
    def connect(self):
        """Create and return SQLAlchemy engine"""
        print(f"[DATABASE] Connecting to {self.config['server']}.{self.config['database']}...")
        
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')
        
        if not username or not password:
            raise ValueError("DB_USERNAME and DB_PASSWORD must be set in .env file")
        
        connection_string = (
            f"DRIVER={{{self.config['driver']}}};"
            f"SERVER={self.config['server']};"
            f"DATABASE={self.config['database']};"
            f"UID={username};"
            f"PWD={password};"
        )
        
        connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"
        self.engine = create_engine(connection_url)
        
        print(f"[DATABASE] ✓ Connected successfully")
        return self.engine
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            print(f"[DATABASE] Connection closed")


# ============================================================================
# QUERY EXECUTION
# ============================================================================

def query_part_usage(engine, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Query raw PartUsage table
    
    Args:
        engine: SQLAlchemy engine
        start_date: Start date for filtering (YYYY-MM-DD)
        end_date: End date for filtering (YYYY-MM-DD)
    
    Returns:
        DataFrame with columns: company_plant_part, endOfMonth, ICUsage, 
        IndirectUsage, DirectUsage, RentUsage, transaction counts
    """
    print(f"[DATABASE] Querying PartUsage table ({start_date} to {end_date})...")
    
    query = text("""
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
        FROM dbo.PartUsage
        WHERE endOfMonth >= :start_date 
          AND endOfMonth <= :end_date
    """)
    
    df = pd.read_sql(query, engine, params={'start_date': start_date, 'end_date': end_date})
    print(f"[DATABASE] ✓ Retrieved {len(df):,} rows from PartUsage")
    
    return df


def query_ipo_validation(engine, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Query raw IPOValidation table
    
    Args:
        engine: SQLAlchemy engine
        start_date: Start date for filtering (YYYY-MM-DD)
        end_date: End date for filtering (YYYY-MM-DD)
    
    Returns:
        DataFrame with columns: Company, Location, Product, Period, Qty
    """
    print(f"[DATABASE] Querying IPOValidation table ({start_date} to {end_date})...")
    
    query = text("""
        SELECT 
            Company,
            Location,
            Product,
            Period,
            Qty
        FROM IPOValidation
        WHERE Period >= :start_date 
          AND Period <= :end_date
    """)
    
    df = pd.read_sql(query, engine, params={'start_date': start_date, 'end_date': end_date})
    print(f"[DATABASE] ✓ Retrieved {len(df):,} rows from IPOValidation")
    
    return df


def query_part_metadata(engine, companies: list) -> pd.DataFrame:
    """
    Query Part/PartPlant metadata for exclusion logic
    
    Args:
        engine: SQLAlchemy engine
        companies: List of company codes to filter
    
    Returns:
        DataFrame with part metadata (Company, PartNum, Plant, ClassID, etc.)
    """
    print(f"[DATABASE] Querying Part metadata for companies: {', '.join(companies)}...")
    
    companies_str = "', '".join(companies)
    
    query = text(f"""
        SELECT 
            p.Company,
            p.PartNum,
            pp.Plant,
            p.ClassID,
            p.InActive,
            p.Runout,
            pp.NonStock,
            p.ProdCode,
            u.Number02
        FROM sai_dw.Erp.Part p
        JOIN sai_dw.Erp.PartPlant pp 
            ON p.Company = pp.Company 
            AND p.PartNum = pp.PartNum
        JOIN sai_dw.Erp.PartPlant_UD u
            ON pp.SysRowID = u.ForeignSysRowID
        WHERE p.Company IN ('{companies_str}')
    """)
    
    df = pd.read_sql(query, engine)
    print(f"[DATABASE] ✓ Retrieved {len(df):,} part records")
    
    return df

