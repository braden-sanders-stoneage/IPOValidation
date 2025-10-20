import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_NAME')
    port = os.getenv('DB_PORT', '1433')
    driver = os.getenv('DB_DRIVER')
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    
    print("="*80)
    print("SQL SERVER CONNECTION TEST")
    print("="*80)
    print(f"Server: {server}")
    print(f"Database: {database}")
    print(f"Port: {port}")
    print(f"Driver: {driver}")
    print(f"Username: {username}")
    print("="*80)
    
    if not username or not password:
        print("✗ Error: DB_USERNAME and DB_PASSWORD must be set in .env file")
        return
    
    connection_string = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    
    print("\nAttempting connection...")
    
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    
    print("✓ Connection successful!")
    print("\nTesting simple query...")
    
    cursor.execute("SELECT @@VERSION AS Version")
    row = cursor.fetchone()
    print(f"\nSQL Server Version:")
    print(row[0])
    
    cursor.execute("SELECT DB_NAME() AS CurrentDatabase")
    row = cursor.fetchone()
    print(f"\nCurrent Database: {row[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM dbo.PartUsage")
    row = cursor.fetchone()
    print(f"\nPartUsage table row count: {row[0]:,}")
    
    cursor.execute("SELECT COUNT(*) FROM dbo.IPOValidation")
    row = cursor.fetchone()
    print(f"IPOValidation table row count: {row[0]:,}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✓ ALL TESTS PASSED")
    print("="*80)

if __name__ == "__main__":
    test_connection()

