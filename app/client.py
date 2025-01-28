import asyncio
import random
import string
import time

import aiohttp


# Список реплик сервера
SERVER_REPLICAS = [
    "http://0.0.0.0:8124",
    "http://0.0.0.0:8123",
]


def generate_random_names(count: int) -> list[str]:
    """
    Генерирует список случайных имён длиной от 5 до 7 символов.
    """
    return [
        "".join(
            random.choice(string.ascii_letters)
            for _ in range(random.randint(5, 7))
        ).capitalize()
        for _ in range(count)
    ]


# Генерация случайных имён пользователей
USER_NAMES = generate_random_names(count=50)
print(USER_NAMES)

# Параметры нагрузки
TOTAL_REQUESTS = 5000
COROUTINE_COUNT = 50
REQUESTS_PER_COROUTINE = TOTAL_REQUESTS // COROUTINE_COUNT


async def send_request(session: aiohttp.ClientSession):
    server = random.choice(SERVER_REPLICAS)
    user = random.choice(USER_NAMES)
    payload = {"sender_name": user, "text": "Тестовое сообщение"}

    try:
        async with session.post(
            f"{server}/messages/", json=payload
        ) as response:
            if response.status == 200:
                return await response.text()
            else:
                return f"Ошибка: {response.status}"
    except Exception as e:
        return f"Ошибка запроса: {str(e)}"


async def worker():
    """
    Выполняет серию запросов в рамках одной корутины.
    """
    async with aiohttp.ClientSession() as session:
        for _ in range(REQUESTS_PER_COROUTINE):
            await send_request(session)


async def main():
    """
    Запускает тестирование производительности с параллельными корутинами.
    """
    start_time = time.time()

    # Создаём и запускаем корутины
    tasks = [worker() for _ in range(COROUTINE_COUNT)]
    await asyncio.gather(*tasks)

    end_time = time.time()

    total_time = end_time - start_time
    avg_request_time = total_time / TOTAL_REQUESTS
    throughput = TOTAL_REQUESTS / total_time

    print(f"Общее время выполнения: {total_time:.2f} секунд")
    print(f"Среднее время одного запроса: {avg_request_time:.4f} секунд")
    print(f"Пропускная способность: {throughput:.2f} запросов в секунду")


if __name__ == "__main__":
    asyncio.run(main())
