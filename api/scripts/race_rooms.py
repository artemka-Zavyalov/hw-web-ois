"""Проверка гонки за одну аудиторию.

Перед запуском:
    uvicorn app.main:app --reload --app-dir api

Затем:
    python api/scripts/race_rooms.py

Три потока одновременно отправляют одинаковый POST на создание
мероприятия в аудитории 1 в один и тот же интервал.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from json import dumps
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"
PAYLOAD_TEMPLATE = {
    "title": "Гонка за аудиторию",
    "description": "Тест конкурентного создания мероприятий",
    "club_id": 1,
    "room_id": 1,
    "starts_at": "2026-11-28T18:00:00+07:00",
    "ends_at": "2026-11-28T19:00:00+07:00",
    "capacity": 20,
}


def create_event(index: int) -> tuple[int, str]:
    payload = dict(PAYLOAD_TEMPLATE)
    payload["title"] = f"Гонка за аудиторию #{index}"

    request = Request(
        f"{BASE_URL}/api/events",
        data=dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body
    except URLError as exc:
        return 0, f"Ошибка подключения: {exc.reason}"


def main() -> None:
    print("Запускаю три одновременных запроса...")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(create_event, i) for i in range(1, 4)]
        for i, future in enumerate(futures, start=1):
            code, body = future.result()
            print(f"Запрос {i}: HTTP {code}")
            print(body)


if __name__ == "__main__":
    main()
