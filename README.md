# Locations Popularity Map

REST API на Django REST Framework: локації, відгуки з рейтингом, like/dislike,
популярність, кешування, експорт у CSV/JSON.

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- Mailpit (листи): http://localhost:8025/

## Тести

```bash
docker compose run --rm web pytest
```

## Примітки

- Аутентифікація через сесію: спочатку `GET /api/auth/csrf/`, далі заголовок `X-CSRFToken`.
- Популярність: `rating · ln(1 + reviews_count) + 0.5 · ln(1 + views_7d)`, рахується в БД.
- Перегляд зараховується один раз на годину на користувача (анонім — за IP + User-Agent).
- Список локацій кешується на 5 хв, кеш скидається після змін локацій, категорій і відгуків.
- Експорт: `GET /api/locations/export/?file_format=csv|json` (підтримує ті самі фільтри).
