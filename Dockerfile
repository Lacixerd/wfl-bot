FROM python:3.12-slim

# Çalışma dizini
WORKDIR /app

# Bağımlılıkları önce kopyala (cache optimizasyonu)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Botu çalıştır
CMD ["python", "main.py"]
