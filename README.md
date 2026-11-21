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
returned only once.
