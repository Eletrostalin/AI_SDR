FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
libpq-dev \
gcc \
netcat \
iputils-ping \
&& rm -rf /var/lib/apt/lists/*

# Создаем нового пользователя и переключаемся на него
RUN useradd -m appuser
USER appuser

# Устанавливаем рабочую директорию
WORKDIR /app

# Обновляем PATH для пользователя appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Копируем файлы проекта в контейнер
COPY --chown=appuser:appuser . /app

# Устанавливаем зависимости напрямую в контейнер
RUN python3.11 -m pip install --upgrade pip && \
pip install --no-cache-dir -r requirements.txt

# Команда для запуска приложения
CMD ["sh", "-c", "until nc -z db 5433; do echo 'Waiting for the database...'; sleep 1; done; python main.py"]]