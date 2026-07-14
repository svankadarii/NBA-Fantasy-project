import os
import psycopg2
from dotenv import load_dotenv

# Loads the same .env file the Node ETL uses (one folder up).
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_connection():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set. Copy ../.env.example to ../.env and fill it in.")
    return psycopg2.connect(dsn)
