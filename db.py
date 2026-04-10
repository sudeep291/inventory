import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in environment variables.")
        return None
        
    try:
        # Connect to the PostgreSQL database
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
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
            discount_applied DECIMAL(5,2) NULL
        )
        """
    ]
    
    try:
        for t in tables:
            cursor.execute(t)
        conn.commit()
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Error initializing DB tables: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    init_db()
