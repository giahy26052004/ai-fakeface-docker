# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

# Cập nhật pip
RUN pip install --upgrade pip

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Tải tài nguyên NLTK 'punkt'
RUN python -m nltk.downloader punkt

# Copy check_rabbitmq.py trước

COPY . .

CMD ["python", "app.py"]
