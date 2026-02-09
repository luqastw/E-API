# E-API

E-commerce REST API. FastAPI, PostgreSQL, Redis. Has an AI layer for
semantic search and product recommendations using RAG (Groq + sentence-transformers).

## What it does

- Authentication (register, login, JWT)
- Users (profile CRUD, soft delete)
- Products (CRUD, filtering by category/price/name, pagination, admin-only writes, soft delete)
- Cart (add/remove/update items, price snapshot at add time)
- Orders (checkout from cart, stock validation, status flow: pending -> paid -> shipped -> delivered | cancelled)
- AI: semantic product search (cosine similarity on embeddings), personalized recommendations based on purchase history, RAG-powered chat assistant (LLaMA 3.3 70B via Groq)

## Dependencies

Python 3. PostgreSQL 16. Redis 7. See requirements.txt for the full list.

Key libraries: FastAPI, SQLAlchemy, Alembic, Pydantic, python-jose (JWT),
bcrypt, sentence-transformers, scikit-learn, groq.

## Setup

```
docker compose up -d
```

That gives you PostgreSQL and Redis. Configure the rest in `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<something-random>
GROQ_API_KEY=<your-groq-key>
```

Install dependencies and run migrations:

```
pip install -r requirements.txt
alembic upgrade head
```

Run:

```
uvicorn src.main:app --reload
```

API docs at <http://localhost:8000/docs>.

## Project structure

```
src/
  main.py           -- app entry point, router registration
  api/
    deps.py         -- dependency injection (db session, auth)
    routes/         -- endpoint definitions per domain
  core/
    config.py       -- settings from environment
    security.py     -- password hashing, JWT encode/decode
  models/           -- SQLAlchemy models (User, Product, Cart, Order)
  schemas/          -- Pydantic request/response schemas
  services/         -- business logic (cart, orders, AI)
  db/               -- database engine and base model
tests/
alembic/            -- database migrations
```

## Endpoints

```
GET    /                       health check

POST   /auth/register          create account
POST   /auth/login             get JWT token

GET    /users/me               current user profile
PATCH  /users/me               update profile
DELETE /users/me               deactivate account

GET    /products/              list (filter, paginate)
GET    /products/{id}          get one
POST   /products/              create (admin)
PATCH  /products/{id}          update (admin)
DELETE /products/{id}          soft delete (admin)

GET    /cart/                  full cart
GET    /cart/summary           totals only
POST   /cart/items             add item
PATCH  /cart/items/{id}        update quantity
DELETE /cart/items/{id}        remove item
DELETE /cart/                  clear cart

POST   /orders/                checkout
GET    /orders/                list user orders
GET    /orders/{id}            order details
PATCH  /orders/{id}/patch      update status (admin)

GET    /ai/search?q=           semantic search
POST   /ai/chat                RAG chat
GET    /ai/recommend           personalized recommendations
```

## Tests

```
pytest
```

## License

MIT
