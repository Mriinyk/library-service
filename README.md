# library-service

## Books API

Books are available at `/api/books/`:

- `GET /api/books/` and `GET /api/books/<id>/` are public.
- `POST /api/books/`, `PUT`/`PATCH /api/books/<id>/`, and
  `DELETE /api/books/<id>/` require a staff account.

Book fields are `title`, `author`, `cover` (`HARD` or `SOFT`), `inventory`
(zero is allowed for out-of-stock books), and `daily_fee` (USD, at least
`0.01`).
