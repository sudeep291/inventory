import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def get_server_connection():
    server = os.environ.get('DB_SERVER', 'localhost\\SQLEXPRESS')
    username = os.environ.get('DB_USER', '')
    password = os.environ.get('DB_PASSWORD', '')
    driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    
    if username and password:
        connection_string = f'DRIVER={{{driver}}};SERVER={server};DATABASE=master;UID={username};PWD={password}'
    else:
        # Windows Authentication
        connection_string = f'DRIVER={{{driver}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;'
        
    try:
        conn = pyodbc.connect(connection_string, autocommit=True)
        return conn
    except pyodbc.Error as e:
        print(f"SQL Server connection error: {e}")
        return None

def get_db_connection():
    server = os.environ.get('DB_SERVER', 'localhost\\SQLEXPRESS')
    database = os.environ.get('DB_NAME', 'FootwearInventory')
    username = os.environ.get('DB_USER', '')
    password = os.environ.get('DB_PASSWORD', '')
    driver = os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    
    if username and password:
        connection_string = f'DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
    else:
        # Windows Authentication
        connection_string = f'DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        
    try:
        conn = pyodbc.connect(connection_string, autocommit=True)
        return conn
    except pyodbc.Error as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    database = os.environ.get('DB_NAME', 'FootwearInventory')
    
    # 1. Ensure database exists
    conn_master = get_server_connection()
    if conn_master:
        cursor = conn_master.cursor()
        try:
            cursor.execute(f"SELECT DB_ID('{database}')")
            if not cursor.fetchone()[0]:
                print(f"Database '{database}' not found. Creating it...")
                cursor.execute(f"CREATE DATABASE {database}")
                print(f"Database '{database}' created successfully.")
            else:
                print(f"Database '{database}' already exists.")
        except Exception as e:
            print(f"Error checking/creating database: {e}")
        finally:
            cursor.close()
            conn_master.close()
    
    # 2. Initialize Tables
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database to initialize tables.")
        return
        
    cursor = conn.cursor()
    tables = [
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Categories' and xtype='U')
        BEGIN
            CREATE TABLE Categories (
                id INT PRIMARY KEY IDENTITY(1,1),
                name VARCHAR(255) UNIQUE NOT NULL
            )
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Products' and xtype='U')
        BEGIN
            CREATE TABLE Products (
                id INT PRIMARY KEY IDENTITY(1,1),
                name VARCHAR(255),
                article_no VARCHAR(255) UNIQUE NOT NULL,
                category_id INT FOREIGN KEY REFERENCES Categories(id),
                gender VARCHAR(50),
                image_path VARCHAR(255),
                cost_price DECIMAL(10,2) NULL,
                is_active BIT DEFAULT 1
            )
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ProductSizes' and xtype='U')
        BEGIN
            CREATE TABLE ProductSizes (
                id INT PRIMARY KEY IDENTITY(1,1),
                product_id INT FOREIGN KEY REFERENCES Products(id),
                size INT,
                stock INT DEFAULT 0
            )
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Sales' and xtype='U')
        BEGIN
            CREATE TABLE Sales (
                id INT PRIMARY KEY IDENTITY(1,1),
                product_id INT FOREIGN KEY REFERENCES Products(id),
                size INT,
                quantity INT,
                sale_date DATETIME DEFAULT GETDATE(),
                sold_price DECIMAL(10,2) NULL,
                profit_type VARCHAR(50) NULL
            )
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Products' AND COLUMN_NAME='mrp')
        BEGIN
            ALTER TABLE Products ADD mrp DECIMAL(10,2) NULL
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Products' AND COLUMN_NAME='default_discount')
        BEGIN
            ALTER TABLE Products ADD default_discount DECIMAL(5,2) NULL
        END
        """,
        """
        IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Products' AND COLUMN_NAME='cost_price')
        BEGIN
            ALTER TABLE Products DROP COLUMN cost_price
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Sales' AND COLUMN_NAME='sold_price')
        BEGIN
            ALTER TABLE Sales ADD sold_price DECIMAL(10,2) NULL
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Sales' AND COLUMN_NAME='discount_applied')
        BEGIN
            ALTER TABLE Sales ADD discount_applied DECIMAL(5,2) NULL
        END
        """,
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Products' AND COLUMN_NAME='selling_price')
        BEGIN
            ALTER TABLE Products ADD selling_price DECIMAL(10,2) NULL
        END
        """,
        """
        UPDATE Products 
        SET selling_price = mrp - (mrp * ISNULL(default_discount, 0) / 100)
        WHERE selling_price IS NULL AND mrp IS NOT NULL
        """
    ]
    
    try:
        for t in tables:
            cursor.execute(t)
        print("Database tables checked/initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB tables: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    init_db()
