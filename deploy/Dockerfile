# Установка базового образа

FROM cgr.dev/chainguard/wait-for-it:latest as wait-for-it

FROM python:3.11
# Установка переменной окружения для отключения вывода буфера Python
ENV PYTHONUNBUFFERED 1

# Установка рабочей директории внутри контейнера
WORKDIR /app

# Копирование файла pyproject.toml и poetry.lock в контейнер
COPY ./pyproject.toml ./poetry.lock /app/
# Установка зависимостей с помощью Poetry
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Копирование всего остального в контейнер
COPY . /app/
COPY --from=wait-for-it --chown=root:root /usr/bin/wait-for-it /usr/bin/wait-for-it