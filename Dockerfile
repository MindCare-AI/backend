FROM python:3.12
#env 
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt /code/

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

ENV ALLOWED_HOSTS="0.0.0.0,127.0.0.1"

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
