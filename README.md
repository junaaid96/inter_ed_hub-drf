# InterEd Hub API

Django REST Framework backend for **InterEd Hub**, an online course platform with
video lessons. Data lives in **Neon Postgres**; videos, cover images and avatars
live in **Neon Object Storage** (S3 compatible, private bucket).

- Frontend: https://github.com/junaaid96/inter_ed_hub-nextjs
- Live API: https://inter-ed-hub-drf.vercel.app
- Neon project: `billowing-mountain-53588698` (branch `production`)

## What's inside

| Area | Highlights |
| --- | --- |
| Accounts | One auth flow for students and teachers, login by username **or** email, optional email confirmation, password change, throttled auth endpoints |
| Catalog | Search, subject/level/length/rating filters, sort by popularity, rating or newest, all stats computed with correlated subqueries (no join blow-up) |
| Courses | Sections → lessons (video or reading), free-preview lessons, outcomes/requirements, draft → publish (needs at least one lesson), drag-and-drop reorder API |
| Video | Browser uploads **straight to Neon Object Storage** with presigned URLs; files over 64 MB use parallel **multipart** uploads (16 MB parts, up to 5 GB). Playback uses short-lived presigned GET URLs with HTTP range requests, so seeking is instant and bytes never pass through Django |
| Learning | Resume position per lesson, watch-time heartbeats, auto-complete at 90%, course progress, private **timestamped notes**, per-lesson **discussion** with instructor badges, reviews and rating breakdown |
| Motivation | Daily learning activity → **streaks** + 12-week heatmap, verifiable **certificates** with a public code |
| Teachers | Studio endpoints, dashboard with learners, rating, watch minutes, 30-day enrollments and an unanswered-questions inbox |

## How video upload and streaming work

```
Browser ──POST /uploads/──────────────► Django: reserve key, presign PUT (or start multipart)
Browser ──PUT bytes (parallel parts)──► Neon Object Storage (private bucket)
Browser ──POST /uploads/<id>/complete/► Django: HEAD object, mark asset ready
Player  ──GET /lessons/<id>/stream/───► Django: access check → presigned GET (4 h)
<video> ──Range: bytes=…──────────────► Neon Object Storage (206 Partial Content)
```

Without `AWS_*` variables the app falls back to a local-disk backend that
imitates the same presigned-URL contract, so everything works offline.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # DEBUG=true is enough for local dev
python manage.py migrate
python manage.py seed_demo --demo-users   # optional demo catalog + logins
python manage.py runserver
```

Demo logins (only with `--demo-users`): `demo_student` / `demo_teacher`,
password `learn-together-2026`.

### Connect to Neon

`neon.ts` declares the private `intered-hub-uploads` bucket. From this folder:

```bash
npm i -g neon@latest && neon login
neon link --project-id billowing-mountain-53588698 --branch production -y
npm install                      # installs @neon/config for neon.ts
neon deploy                      # applies neon.ts and writes DATABASE_URL + AWS_* to .env
python manage.py migrate
python manage.py configure_bucket_cors   # lets the frontend PUT/GET the bucket
```

The `production` branch already has the schema and the six subjects applied.

### Deploy (Vercel)

The API runs on Vercel as project `inter-ed-hub-drf`, linked to this repo, so
every push to `main` deploys to https://inter-ed-hub-drf.vercel.app. Vercel's
Django preset installs `requirements.txt`, runs `collectstatic` and serves
`inter_ed_hub.wsgi` as a function; no `vercel.json` is needed.

- **Framework preset:** Django. **Function region:** `sin1` (Singapore, next to
  the Neon branch in `ap-southeast-1`).
- **Environment variables** (Production + Preview): `SECRET_KEY`, `DEBUG=false`,
  `DATABASE_URL`, `STORAGE_BUCKET`, `AWS_ENDPOINT_URL_S3`, `AWS_REGION`,
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `FRONTEND_URL`
  (`https://inter-ed-hub-nextjs.vercel.app`) and `BACKEND_URL`
  (`https://inter-ed-hub-drf.vercel.app`). Take the Neon values from
  `neon env pull` or a Neon Console credential with `storage:read` +
  `storage:write`.
- **Deployment protection:** Vercel Authentication covers previews and
  per-deployment URLs; the production domain stays public so the frontend can
  call it.
- **Migrations don't run on deploy.** After changing models, run them against
  Neon yourself:

  ```bash
  DATABASE_URL=postgresql://... python manage.py migrate
  ```

- **Bucket CORS** is applied on the first upload of each process
  (`STORAGE_AUTO_CORS`), or run `python manage.py configure_bucket_cors` once.

The frontend reads the API address from `NEXT_PUBLIC_API_URL` in its own Vercel
project; it is baked in at build time, so redeploy the frontend after changing it.

### Deploy (Render, alternative)

`render.yaml` + `build.sh` still work: they install dependencies, collect static
files, migrate and sync the bucket CORS rules. Set the same variables as above,
with `BACKEND_URL` pointing at the Render URL.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY`, `DEBUG` | Django basics (`SECRET_KEY` required when `DEBUG` is off) |
| `DATABASE_URL` | Neon Postgres connection string (SQLite fallback) |
| `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | Neon Object Storage credentials |
| `STORAGE_BUCKET` | Bucket name, default `intered-hub-uploads` |
| `FRONTEND_URL`, `BACKEND_URL` | Used for CORS, activation links and media URLs |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Optional SMTP. When set, new accounts must confirm their email |
| `VIDEO_URL_TTL`, `MAX_VIDEO_BYTES`, `MULTIPART_THRESHOLD`, `MULTIPART_PART_SIZE` | Upload/streaming tuning |

## API overview

| Method & path | Description |
| --- | --- |
| `POST /auth/register/` · `POST /auth/login/` · `POST /auth/logout/` | Token auth (`Authorization: Token <key>`) |
| `GET/PATCH /auth/me/` · `POST /auth/password/` · `POST /auth/activate/` | Profile and account |
| `GET /departments/` · `GET /teachers/` · `GET /teachers/<id>/` | Public directory |
| `GET /courses/?search=&department=&level=&duration=&min_rating=&ordering=` | Catalog |
| `POST /courses/` · `GET/PATCH/DELETE /courses/<slug>/` | Course CRUD (teachers own theirs) |
| `POST /courses/<slug>/enroll/` · `GET/POST /courses/<slug>/reviews/` | Enrollment and reviews |
| `POST /courses/<slug>/sections/` · `PATCH/DELETE /sections/<id>/` · `POST /sections/<id>/lessons/` | Curriculum builder |
| `POST /courses/<slug>/reorder/` | Persist drag-and-drop order |
| `GET/PATCH/DELETE /lessons/<id>/` · `GET /lessons/<id>/stream/` | Player data and video URL |
| `POST /lessons/<id>/progress/` | Heartbeat: position, watch time, completion |
| `GET/POST /lessons/<id>/notes/` · `PATCH/DELETE /notes/<id>/` · `GET /courses/<slug>/notes/` | Timestamped notes |
| `GET/POST /lessons/<id>/comments/` · `DELETE /comments/<id>/` | Discussion |
| `POST /uploads/` · `POST /uploads/<id>/parts/` · `POST /uploads/<id>/complete/` · `POST /uploads/<id>/abort/` | Direct-to-storage uploads |
| `GET /media/<asset>/` | Public redirect for images (covers, avatars) |
| `GET /me/learning/` · `GET /me/teaching/` | Student and teacher dashboards |
| `GET /certificates/<code>/` | Public certificate verification |

## Tests

```bash
DEBUG=1 python manage.py test
```

Covers the full journey (register → build course → upload → publish → enroll →
stream with range requests → progress → notes → discussion → certificate),
ownership rules, reordering, multipart uploads and streak maths. Runs on SQLite
or Postgres (`DATABASE_URL=...`).
