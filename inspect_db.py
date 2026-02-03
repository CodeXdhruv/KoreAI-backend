import sqlite3
import sys
import os

def print_table(conn, table_name):
    print(f"\n=== Table: {table_name} ===")
    c = conn.cursor()
    try:
        c.execute(f"SELECT * FROM {table_name}")
        rows = c.fetchall()
        
        if not rows:
            print("(No data)")
            return

        # Get headers
        headers = [description[0] for description in c.description]
        
        # Calculate column widths
        widths = [len(h) for h in headers]
        formatted_rows = []
        for row in rows:
            f_row = [str(x) for x in row]
            formatted_rows.append(f_row)
            for i, val in enumerate(f_row):
                widths[i] = max(widths[i], len(val))
        
        # Print headers
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        print(header_line)
        print("-" * len(header_line))
        
        # Print rows
        for row in formatted_rows:
            print(" | ".join(val.ljust(w) for val, w in zip(row, widths)))
            
    except Exception as e:
        print(f"Error reading {table_name}: {e}")

def inspect():
    db_path = "habitcity.db"
    
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return

    print(f"Connecting to {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get list of tables
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in c.fetchall()]
        
        print(f"Found tables: {', '.join(tables)}")
        
        for table in tables:
            print_table(conn, table)
            
        conn.close()
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    inspect()
