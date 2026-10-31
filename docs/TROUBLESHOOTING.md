# Troubleshooting

This guide covers common problems you may run into when setting up and running maqati3
locally. If yours is not covered here, check the other documents in [`docs/`](README.md)
or open an issue on GitHub.

## Docker and the database

### The database container fails to start

Make sure Docker is installed and running, then check the container status and its logs:

```bash
docker compose ps
docker compose logs db
```

If the container exits unexpectedly, read the logs for the underlying error before
restarting it.

### Port 5432 is already in use

Another PostgreSQL instance may already be using the default port. Start the database on a
different one with the `DB_PORT` variable:

```bash
DB_PORT=55432 docker compose up -d --wait db
```

and use the same port in `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://maqati3:devonly@127.0.0.1:55432/maqati3
```

## Backend

### The database connection fails

Check that:

- the database container is running;
- the port is the right one;
- the database name and credentials match your local configuration;
- `DATABASE_URL` is set.

The database logs help here too: `docker compose logs db`.

### The migration fails

Make sure the database is running and `DATABASE_URL` points to it, then run, from the
`backend` directory:

```bash
uv run python -m maqati3 migrate
```

If it still fails, read the error message before changing anything in the database by hand.

### Python dependencies fail to install

Make sure [uv](https://docs.astral.sh/uv/) is installed and you are on Python 3.13. From the
`backend` directory:

```bash
uv sync
```

If it fails, check the error output and your Python and uv versions.

## Media processing

### `ffmpeg` or `fpcalc` cannot be found

The media features need both. Install them with:

```bash
sudo apt update && sudo apt install ffmpeg libchromaprint-tools   # Debian, Ubuntu
brew install chromaprint ffmpeg                                   # macOS
```

and check that both are available:

```bash
ffmpeg -version
fpcalc -version
```

If one is not found, make sure the directory it was installed to is on your `PATH`.

## Frontend

### The dependencies fail to install

Make sure Node.js 22 is installed, then, from the `frontend` directory:

```bash
npm ci
```

If it fails, check the npm error output and your Node.js version.

### The frontend cannot reach the backend

Check that:

- the backend is running and listening on the expected port;
- the frontend development server is running;
- the proxy points at the backend (`API_ORIGIN`, see [`frontend/README.md`](../frontend/README.md)).

Start the backend with the documented development command:

```bash
UPLOAD_KEY=dev STAGING_DIR=.staging uv run python -m maqati3 serve --port 8000
```

and the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

## Tests

### Backend tests are skipped

The database and end-to-end tests need a running PostgreSQL, a valid `DATABASE_URL`, and
`ffmpeg` and `fpcalc` on the `PATH`. Without them those tests are skipped. CI runs all of them.

```bash
cd backend
uv run pytest
```

### Frontend checks fail

Run them one by one and read the output of the one that fails:

```bash
cd frontend
npm test
npm run lint
npx tsc --noEmit
```

## Still stuck?

Read the [README](../README.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md), and search the
[existing issues](https://github.com/PSchmitz-Valckenberg/maqati3/issues). If your problem
has not been reported, open a new issue and include:

- your operating system;
- your Python and Node.js versions;
- the command you ran;
- the complete error message;
- the steps to reproduce it.

Remove passwords, API keys, database credentials and other secrets from logs before you
share them.
