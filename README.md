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
You can use the following commands to create the database and the user:

please refer to the [DATABASE](DATABASE.md) file for more information on how to create the database and the user.

To create the apply database migrations, you can use the following command:
```bash
python manage.py migrate
```

To run the application, you can use the following command:
```bash
python manage.py runserver
```
