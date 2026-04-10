from db import get_db_connection

def clear_all():
    conn = get_db_connection()
    if not conn:
        print("Error connecting to DB")
        return
    c = conn.cursor()
    try:
        print("Clearing Sales...")
        c.execute("DELETE FROM Sales")
        print("Clearing ProductSizes...")
        c.execute("DELETE FROM ProductSizes")
        print("Clearing Products...")
        c.execute("DELETE FROM Products")
        print("Clearing Categories...")
        c.execute("DELETE FROM Categories")
        
        # Reseed identities
        try:
            c.execute("DBCC CHECKIDENT ('Sales', RESEED, 0)")
            c.execute("DBCC CHECKIDENT ('ProductSizes', RESEED, 0)")
            c.execute("DBCC CHECKIDENT ('Products', RESEED, 0)")
            c.execute("DBCC CHECKIDENT ('Categories', RESEED, 0)")
        except Exception as id_err:
            print("Could not complete reseeding (maybe tables were empty):", id_err)
            
        print("Database successfully wiped to Factory Settings.")
    except Exception as e:
        print("Error during wipe:", e)
    finally:
        c.close()
        conn.close()

if __name__ == '__main__':
    clear_all()
