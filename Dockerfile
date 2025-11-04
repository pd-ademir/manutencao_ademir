# 1. Imagem base leve com Python 3.11
FROM python:3.11-slim

# 2. Define o diretório de trabalho dentro do container
WORKDIR /app

# 3. Instala as dependências do sistema operacional (mantido como estava)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libfribidi0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libtiff6 \
    libgl1 \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia e instala as dependências Python
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copia todo o código da aplicação
COPY . .

# 6. Expõe a porta que o Cloud Run espera
EXPOSE 8080

# 7. Define o comando de entrada para iniciar o Gunicorn diretamente.
# O wsgi:app aponta para o arquivo wsgi.py, que cria a instância da aplicação.
CMD exec gunicorn --bind :$PORT --workers 1 --worker-tmp-dir /dev/shm --timeout 300 wsgi:app
