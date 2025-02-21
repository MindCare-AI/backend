Here’s the shortened version of the `DATABASE.md`:

---

# Local Database Setup for MindCare-IA

## Prerequisites
- PostgreSQL installed (Windows/Linux)
- Python 3.11+
- `pip` and `virtualenv`

---

## Step 1: Install PostgreSQL

### On Windows:
1. Download from [PostgreSQL Windows Download](https://www.postgresql.org/download/windows/).
2. Follow the installation instructions.

### On Linux:
1. Run:
   ```
   sudo apt install postgresql postgresql-contrib
   sudo service postgresql start
   ```

---

## Step 2: Create Database

1. Log in to PostgreSQL:
   ```
   sudo -u postgres psql
   ```
2. Create database:
   ```
   CREATE DATABASE mindcare;
   ```
3. (Optional) Create user and set password:
   ```
   CREATE USER mindcare WITH PASSWORD 'mindcare';
   GRANT ALL PRIVILEGES ON DATABASE mindcare TO mindcare;
   ```
4. Exit PostgreSQL:
   ```
   \q
   ```

---

## Step 3: Configure `.env`

Add to your `.env` file:
```
USE_CLOUD=false
DB_NAME=mindcare
DB_USER=mindcare
DB_PASSWORD=mindcare
DB_HOST=localhost
DB_PORT=5432
```

---

## Step 4: Install Dependencies

1. Create and activate virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate  # Linux
   venv\Scripts\activate     # Windows
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

---

## Step 5: Run Migrations

Run the following to set up the database schema:
```
python manage.py migrate
```

---
 