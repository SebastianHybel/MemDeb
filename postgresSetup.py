import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# POSTGRES DB

con = psycopg2.connect(
    host= os.getenv('DATABASE_HOST'), port= os.getenv('DATABASE_PORT'),
    database= os.getenv('DATABASE_NAME'), user= os.getenv('DATABASE_USER'), password= os.getenv('DATABASE_PASSWORD'))

cur = con.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS mdmemory (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        ticker VARCHAR(10) NOT NULL,
        model VARCHAR(255) NOT NULL,
        version VARCHAR(10) NOT NULL,
        content TEXT NOT NULL,
        decision VARCHAR(15) NOT NULL,
        price VARCHAR(25) NOT NULL,  
        position BOOL NOT NULL, 
        positionSize VARCHAR(50) NOT NULL    
    )
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS mddebate (
        id SERIAL PRIMARY KEY,
        key VARCHAR(10) NOT NULL,
        date DATE NOT NULL,
        ticker VARCHAR(10) NOT NULL,
        agent VARCHAR(20) NOT NULL,
        model VARCHAR(255) NOT NULL,
        version VARCHAR(10) NOT NULL,
        content TEXT NOT NULL,
        decision VARCHAR(15) NOT NULL,
        price VARCHAR(25) NOT NULL,    
        position BOOL NOT NULL, 
        positionSize VARCHAR(50) NOT NULL    
    )
""")

def insert_summary(date, ticker, model, version, content, decision, price, position, positionsize):
    cur.execute("""
        INSERT INTO mdmemory (date, ticker, model, version, content, decision, price,  position, positionsize)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (date, ticker, model, version, content, decision, price, position, positionsize))
    con.commit()

insert_summary("2024-03-12", "TSLA", "GPT3.5", "V1", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")
insert_summary("2024-03-12", "TSLA", "GPT3.5", "V2", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")

insert_summary("2024-03-12", "MSFT", "GPT3.5", "V1", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")
insert_summary("2024-03-12", "MSFT", "GPT3.5", "V2", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")

insert_summary("2024-03-12", "NVDA", "GPT3.5", "V1", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")
insert_summary("2024-03-12", "NVDA", "GPT3.5", "V2", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")

insert_summary("2024-03-12", "META", "GPT3.5", "V1", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")
insert_summary("2024-03-12", "META", "GPT3.5", "V2", "This is the first data entry. The database is waiting for your first day investing", "-", "-", "False", "0")
con.commit()

cur.close()
con.close()