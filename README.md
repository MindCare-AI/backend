# backend
### Important Note:
Before pushing any changes to the repository, make sure to run the following command:
```bash
ruff check 
ruff check --fix 
ruff format 
```

For creating a venv, you can use the following command:
```bash
python3 -m venv venv
```
Then, you can activate the venv using the following command:
```bash
source venv/bin/activate
```

After activating the venv, you can install the required packages using the following command:
```bash
pip install -r requirements.txt
```

Now make sure that you have postgresql installed and running on port 5432 (default port) <br>
After that, you will need to create "mindcare" database and "mindcare" user <br>

### Database Setup
Create a database called "mindcare" and a user with the same name. Grant all privileges on the database to the user.

**Note:** The DATABASE.md file has been removed from this repository. Instead, follow these steps:

```sql
CREATE DATABASE mindcare;
CREATE USER mindcare WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mindcare TO mindcare;
```

### Deleted Files Notice
Several files have been removed from this repository as part of cleaning up the codebase. These include:
- Documentation files (CLASS_DIAGRAMS.md, DATABASE.md, DATABASE_SCHEMA.md)
- Diagram files (class_diagrams.puml, database_relationships.puml)
- Utility scripts (check_mood_data.py, cleanup_test_data.py)
- Test files (chatbot test files, rag_evaluation_results.json)

To prevent tools like GitHub Copilot from referencing these deleted files, they have been added to:
- `.gitignore`
- `.copilotignore` 
- `.github/copilot/settings.json`

If you find references to these deleted files in suggestions, run the cache clearing script:
```bash
./scripts/clear_copilot_cache.sh
```

To create the apply database migrations, you can use the following command:
```bash
python manage.py migrate
```

To run the application, you can use the following command:
```bash
python manage.py runserver
```
