
from app.database.connection import test_source_connection

if __name__ == "__main__":
    try:
        result = test_source_connection()
        print("\nCYBERSHIELD POSTGRESQL CONNECTION")
        print("--------------------------------")
        print("Connected:", result["connected"])
        print("Database:", result["database"])
        print("User:", result["user"])

    except Exception as error:
        print("\nCONNECTION FAILED")
        print(error)
