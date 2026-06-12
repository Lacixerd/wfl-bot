FROM python:3.14-slim

# Çalışma dizini
# Python output'u buffer'lamadan direkt gönder (docker logs için)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Bağımlılıkları önce kopyala (cache optimizasyonu)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Botu çalıştır
CMD ["python", "main.py"]
