# library-service

## Books API

Books are available at `/api/books/`:

- `GET /api/books/` and `GET /api/books/<id>/` are public.
- `POST /api/books/`, `PUT`/`PATCH /api/books/<id>/`, and
  `DELETE /api/books/<id>/` require a staff account.

Book fields are `title`, `author`, `cover` (`HARD` or `SOFT`), `inventory`
(zero is allowed for out-of-stock books), and `daily_fee` (USD, at least
`0.01`).

## Borrowings API

Borrowings are available to authenticated users at `/api/borrowings/`:

- `GET /api/borrowings/` lists borrowings; `is_active=true|false` filters by
  return status. Staff users can also filter by `user_id`.
- `POST /api/borrowings/` creates a borrowing with `book` (book ID) and
  `expected_return_date` (ISO date). The current user and borrow date are set
  automatically, and book inventory is decreased atomically.
- `GET /api/borrowings/<id>/` returns details, including the book.
- `POST /api/borrowings/<id>/return/` returns a book and restores inventory.

Non-staff users can access only their own borrowings. A borrowing can be
returned only once. Users with a pending payment cannot create a new borrowing
until that payment is paid.

## Payments API

Authenticated users can list and retrieve payments at `/api/payments/`:

- `GET /api/payments/` lists payments.
- `GET /api/payments/<id>/` returns payment details.
- `POST /api/payments/<id>/renew/` creates a new Stripe Checkout Session for an
  expired payment and returns it to `PENDING`.
- `GET /api/payments/success/?session_id=...` verifies the session with Stripe
  and marks the payment `PAID` only after Stripe confirms it.
- `GET /api/payments/cancel/` returns a paused-payment message.

Non-staff users see only payments associated with their borrowings; staff users
can see all payments. Payment records include `status` (`PENDING`, `PAID`, or
`EXPIRED`), `type` (`PAYMENT` or `FINE`), `borrowing` (ID), Stripe session URL
and ID, and `money_to_pay` in USD. Set `STRIPE_SECRET_KEY` in the environment
before using Stripe endpoints or the expiration command.

Run `python manage.py check_expired_payment_sessions` from an external
scheduler every minute to mark expired Stripe sessions. The command does not
start a background scheduler inside Django.
