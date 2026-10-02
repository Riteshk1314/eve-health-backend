# EVE Healthcare: Diagnostic Booking & Payments API

Django REST backend where patients book diagnostic tests at centres and pay through a simulated payment provider.
Paying creates an order (`PENDING`); the provider always reports the result later through a signed, idempotent webhook that Celery processes in the background.

**Stack:** Django 5.2 · DRF · PostgreSQL · Redis · Celery · JWT · drf-spectacular · Docker

**Extras:** Redis caching · Celery retries with backoff · Swagger UI · JSON logging · pagination · rate limiting

## Running

### Docker

```bash
docker compose up --build -d
docker compose exec web python manage.py seed_data
docker compose exec web python manage.py createsuperuser
```

Starts Postgres, Redis, the API (gunicorn on `:8000`, migrations run on start) and a Celery worker.

- Swagger UI: http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/
- Health: http://localhost:8000/health/

### Local

Needs Python 3.10+, PostgreSQL and Redis.

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # set POSTGRES_* for your database
python manage.py migrate
python manage.py seed_data
python manage.py runserver
celery -A config worker -l info -P solo     # second terminal (-P solo on Windows)
```

Without a worker, set `CELERY_TASK_ALWAYS_EAGER=true` in `.env`.

## Payment flow

```
POST /api/payments/  {"booking_id": 1}        (optional header: Idempotency-Key)
  ├─ same Idempotency-Key seen before?  -> 200, original payment
  ├─ create_order(): lock booking, check it's payable, create Payment(PENDING)
  └─ 201, payment PENDING

Provider -> POST /api/payments/webhook/   (signed with HMAC-SHA256, X-Webhook-Signature)
  ├─ bad signature -> 401
  ├─ event_id already stored -> 200, ignored
  └─ store WebhookEvent, queue Celery task -> 202

Celery: process_payment() -> Payment SUCCESS/FAILED, Booking CONFIRMED/FAILED
        retries 5 times with backoff (2s .. 32s), then marks the event FAILED
```

Simulate the provider with:

```bash
python manage.py send_test_webhook <provider_reference> succeeded [--event-id evt_1] [--bad-signature]
python manage.py send_test_webhook <provider_reference> failed
```

**No double charge, enforced in PostgreSQL:** one `SUCCESS` and one `PENDING` payment per booking (partial unique indexes), unique `event_id` per webhook, unique `Idempotency-Key`.
`process_payment()` ignores payments that are already final, so late or repeated webhooks change nothing.

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/auth/signup/` · `/login/` · `/refresh/` | public |
| GET | `/api/auth/me/` | user |
| GET | `/api/centres/` (`?city=`, `?search=`) · `/api/centres/{id}/` (with tests + prices) | public |
| GET | `/api/tests/` · `/api/centre-tests/` (`?centre=`, `?test=`) | public |
| POST/PUT/PATCH/DELETE | centres, tests, centre-tests | staff (DELETE = soft delete) |
| GET/POST | `/api/bookings/` (`?status=`) | user |
| GET | `/api/bookings/{id}/` | owner |
| POST | `/api/bookings/{id}/cancel/` | owner |
| GET/POST | `/api/payments/` · GET `/api/payments/{id}/` | owner |
| POST | `/api/payments/webhook/` | HMAC signature |

Lists are paginated (20 per page). Someone else's booking/payment returns `404`. Invalid status changes return `409`.

## Data model

- **User**: email login, `is_staff` manages the catalogue.
- **DiagnosticCentre**, **DiagnosticTest**, **CentreTest**: the price is on `CentreTest`, so each centre sets its own price.
- **Booking**: `amount` is a snapshot of the price at booking time. Status machine:
  `PENDING → CONFIRMED / FAILED / CANCELLED`, `FAILED → CONFIRMED / CANCELLED`, `CONFIRMED → CANCELLED`.
- **Payment**: many attempts per booking (a failed one can be retried).
- **WebhookEvent**: every provider event with its attempts and last error.

Centres, tests and offerings are soft-deleted, and bookings/payments use `on_delete=PROTECT`.

## Assumptions

- One booking = one test at one centre. No time-slot capacity.
- Full payment only, single currency.
- Cancelling after payment is allowed. Refunds aren't implemented; a success arriving for a cancelled booking is logged as `refund_required`.
- All routes are under `/api/`.
