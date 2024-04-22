FROM python:3.9-slim

WORKDIR /app

RUN pip install fastapi uvicorn

COPY . .

EXPOSE 80

CMD ["uvicorn", "libapi:app", "--host", "0.0.0.0", "--port", "8000"]
