# Library Service

Library Service is a Django REST Framework API for managing customers, books,
and book borrowings. It also exposes read-only payment records. The API root
and browsable API are available at `/api/`; interactive Swagger and ReDoc
documentation are available at `/api/docs/` and `/api/redoc/`. The OpenAPI
schema is available at `/api/schema/`; the Django admin is at `/admin/`.

## Features

- Customer registration, JWT authentication, and profile management.
- Public book catalog with staff-only book management.
- Borrowing creation, inventory tracking, return processing, and filtering.
- Payment list and detail endpoints with owner-based access control.

The project is a single Django application with separate domain apps sharing
one database:

| App | Responsibility |
| --- | --- |
| `users` | Customer model, registration, profile, and JWT endpoints |
| `library` | Book inventory and catalog API |
| `borrowings` | Borrowing lifecycle and inventory changes |
| `payments` | Payment model and read-only API |

## Requirements and local setup

The project is tested with Python 3.12. Dependencies are pinned in
`requirements.txt`; the default database is SQLite.

Create and activate a virtual environment, then install dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate the environment with
`source .venv/bin/activate`.

Copy `.env.example` to `.env`:

```text
Copy-Item .env.example .env
```

On macOS/Linux, use `cp .env.example .env`. Replace `DJANGO_SECRET_KEY` in
`.env` with a private random value. For example, generate one with:

```text
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The environment variables are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django cryptographic secret; required | None |
| `DJANGO_DEBUG` | Enables Django debug mode | `False` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed host names | Empty |

`.env` is ignored by Git and must not be committed. Django fails during startup
if `DJANGO_SECRET_KEY` is missing.

Emails use Django's console mailer in development; messages are written to the
server console instead of being sent through SMTP.

Apply migrations and start the development server:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The default SQLite database is `db.sqlite3`. Staff users can manage books,
users, borrowings, and payments through `/admin/`.

## Authentication

Register a customer:

```http
POST /api/users/
Content-Type: application/json

{
  "email": "reader@example.com",
  "first_name": "Alex",
  "last_name": "Reader",
  "password": "a-strong-password"
}
```

Obtain an access and refresh token:

```http
POST /api/users/token/
Content-Type: application/json

{
  "email": "reader@example.com",
  "password": "a-strong-password"
}
```

The token response contains both tokens:

```json
{
  "refresh": "<refresh-token>",
  "access": "<access-token>"
}
```

For protected endpoints, send the access token using the standard
`Authorization` header:

```http
Authorization: Bearer <access-token>
```

Refresh an access token with `POST /api/users/token/refresh/` and a JSON body
containing the `refresh` token. The browsable API also supports Django session
authentication.

## Users API

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `POST` | `/api/users/` | Public | Register a customer |
| `POST` | `/api/users/token/` | Public | Obtain JWT access and refresh tokens |
| `POST` | `/api/users/token/refresh/` | Public | Refresh an access token |
| `GET` | `/api/users/me/` | Authenticated | Get the current profile |
| `PUT`, `PATCH` | `/api/users/me/` | Authenticated | Update the current profile |

Profiles contain `id`, `email`, `first_name`, `last_name`, and `is_staff`.
Passwords are write-only and hashed. The password is required at registration
and optional during profile updates. Customers cannot grant themselves staff
access.

## Books API

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/books/` | Public | List books |
| `GET` | `/api/books/<id>/` | Public | Get book details |
| `POST` | `/api/books/` | Staff | Create a book |
| `PUT`, `PATCH` | `/api/books/<id>/` | Staff | Replace or update a book |
| `DELETE` | `/api/books/<id>/` | Staff | Delete a book |

Book fields:

| Field | Type and rules |
| --- | --- |
| `title` | String, required |
| `author` | String, required |
| `cover` | `HARD` or `SOFT` |
| `inventory` | Non-negative integer; zero means out of stock |
| `daily_fee` | USD decimal with two decimal places; minimum `0.01`, maximum `99999999.99` |

Staff means a user with `is_staff=True`. All read requests, including detail
requests, are public.

Example create/update body:

```json
{
  "title": "The Hobbit",
  "author": "J. R. R. Tolkien",
  "cover": "HARD",
  "inventory": 5,
  "daily_fee": "1.50"
}
```

## Borrowings API

All borrowing endpoints require authentication. Customers can access only
their own borrowings; staff can access all borrowings.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/borrowings/` | List borrowings |
| `POST` | `/api/borrowings/` | Borrow an available book |
| `GET` | `/api/borrowings/<id>/` | Get borrowing details |
| `POST` | `/api/borrowings/<id>/return/` | Return a book |

Create a borrowing with a book ID and ISO-8601 expected return date:

```json
{
  "book": 1,
  "expected_return_date": "2026-12-01"
}
```

The API sets `borrow_date` to the current date and attaches the authenticated
user. The expected return date must be later than the borrow date. Creating a
borrowing atomically decreases inventory; a book with zero inventory cannot be
borrowed. The response includes borrowing dates, the user ID, and detailed book
information.

Filter the list with query parameters:

| Parameter | Access | Values and behavior |
| --- | --- | --- |
| `is_active` | Authenticated users | `true` for not yet returned; `false` for returned |
| `user_id` | Staff only | Limit results to the specified customer |

For example, `/api/borrowings/?is_active=true&user_id=2` returns active
borrowings for customer 2 when requested by staff. Non-staff users always see
only their own records. A borrowing cannot be returned more than once; a
successful return sets `actual_return_date` and restores one book to inventory.

## Payments API

The required Payments API is read-only:

| Method | Endpoint | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/api/payments/` | Authenticated | List payments |
| `GET` | `/api/payments/<id>/` | Authenticated | Get payment details |

Customers see payments associated with their own borrowings; staff can see all
payments. Payment fields are:

| Field | Values/type |
| --- | --- |
| `status` | `PENDING` or `PAID` |
| `type` | `PAYMENT` or `FINE` |
| `borrowing` | Borrowing ID |
| `session_url` | URL |
| `session_id` | String |
| `money_to_pay` | Positive USD decimal with two decimal places; maximum `99999999.99` |

Book daily fees and payment totals use the same `Decimal(10, 2)` precision in
USD.

Payment creation and Stripe checkout processing are not part of the selected
required scope.

## Common responses

List endpoints for books, borrowings, and payments use page-number pagination.
Responses contain `count`, `next`, `previous`, and `results`; request another
page with `?page=2`. The default page size is 10.

- `400 Bad Request`: invalid input, invalid query parameters, unavailable book
  inventory, or an invalid borrowing date.
- `401 Unauthorized`: a protected endpoint was called without valid
  authentication.
- `403 Forbidden`: an authenticated non-staff user attempted to modify books.
- `404 Not Found`: the requested resource does not exist or is outside the
  customer's permitted records.
- `405 Method Not Allowed`: an unsupported operation, such as creating a
  payment through the read-only Payments API.

## Migrations, checks, and tests

After changing models, create and apply migrations:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Run the project checks and complete test suite:

```powershell
python manage.py check
python manage.py test
```
