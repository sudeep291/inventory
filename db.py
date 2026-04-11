import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Global Connection Pool
_db_pool = None

def get_connection_pool():
    global _db_pool
    if _db_pool is None:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("DATABASE_URL not found in environment variables.")
            return None
            
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        try:
            # Min 1, Max 10 connections (Slightly relaxed for better parallel support)
            _db_pool = pool.ThreadedConnectionPool(1, 10, database_url, sslmode='require', cursor_factory=RealDictCursor)
            print("DATABASE POOL: Initialized successfully.")
        except Exception as e:
            print(f"DATABASE POOL ERROR: {e}")
            return None
    return _db_pool

def get_db_connection():
    import time
    pool = get_connection_pool()
    if pool:
        for attempt in range(3): # Professional retry loop for cold-boot resilience
            try:
                conn = pool.getconn()
                return conn
            except Exception as e:
                print(f"POOL ATTEMPT {attempt+1} FAILED: {e}")
                time.sleep(1) # Wait 1s before retry
        print("CRITICAL: ALL CONNECTION ATTEMPTS FAILED.")
        return None
    return None

def release_db_connection(conn):
    pool = get_connection_pool()
    if pool and conn:
        pool.putconn(conn)

def init_db():
    conn = get_db_connection()
    if not conn:
        print("Failed to initialize database: No connection.")
        return
        
    cursor = conn.cursor()
    
    tables = [
        """
        CREATE TABLE IF NOT EXISTS Categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            article_no VARCHAR(255) UNIQUE NOT NULL,
            category_id INT REFERENCES Categories(id),
            gender VARCHAR(50),
            image_path VARCHAR(255),
            mrp DECIMAL(10,2) NULL,
            default_discount DECIMAL(5,2) NULL,
            selling_price DECIMAL(10,2) NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ProductSizes (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES Products(id),
            size DECIMAL(4,1),
            stock INT DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Sales (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES Products(id),
            size DECIMAL(4,1),
            quantity INT,
            sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sold_price DECIMAL(10,2) NULL,
            discount_applied DECIMAL(5,2) NULL,
            status VARCHAR(20) DEFAULT 'SALE'
        )
        """,
        """
        ALTER TABLE Sales ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'SALE'
        """,
        """
        CREATE TABLE IF NOT EXISTS WeeklyMetrics (
            id SERIAL PRIMARY KEY,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_pairs_sold INT DEFAULT 0,
            total_revenue DECIMAL(15,2) DEFAULT 0.0,
            net_profit DECIMAL(15,2) DEFAULT 0.0,
            current_vault_stock INT DEFAULT 0,
            current_total_investment DECIMAL(15,2) DEFAULT 0.0
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sales_date ON Sales(sale_date DESC);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sales_product ON Sales(product_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_psizes_product ON ProductSizes(product_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_active ON Products(is_active);
        """,
        """
        ALTER TABLE Products ALTER COLUMN image_path TYPE TEXT;
        """,
        """
        UPDATE Sales SET status = 'RETURNED' WHERE status = 'RETURN';
        """
    ]
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        for t in tables:
            cursor.execute(t)
        conn.commit()
        print("DATABASE SUCCESS: Tables initialized correctly.")
    except Exception as e:
        print(f"DATABASE INIT ERROR: {e}")
        if conn: conn.rollback()
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn: release_db_connection(conn)

if __name__ == '__main__':
    init_db()
