# گزارش کامل پروژه IG Funnel (اینستاریل)

> این فایل به‌صورت خودکار تولید شده و شامل شرح کامل کارهای انجام‌شده، توضیح تک‌تک فایل‌ها و متن کامل سورس‌کد است.

## ۱. خلاصه اجرایی

یک وب‌اپلیکیشن فول‌استک برای پردازش و پست محتوای اینستاگرام: ادمین ویدیوها را از داشبورد آپلود می‌کند، بک‌اند با FFmpeg پردازش می‌کند و طبق زمان‌بندی به‌صورت ریلز پست می‌کند. مدیریت بات‌های تلگرام کاملاً خارجی است؛ تنها نقطه تماس، فیلد لینک (`link_url`) در تنظیمات بایو است که می‌تواند به بات خارجی (مثل `https://t.me/your_external_bot`) اشاره کند.

**آمار:** 91 فایل سورس، حدود 6390 خط کد. بک‌اند: Python 3.11 + FastAPI + SQLAlchemy (آسنکرون برای وب، سینک برای سلری) + Celery + Redis + FFmpeg + instagrapi. فرانت‌اند: Next.js 14 + React 18 + TypeScript + Tailwind + TanStack Query + Zustand + Recharts. داشبورد ۱۲ بخش (بدون صفحه تلگرام).

## ۲. فازهای اجرایی (ساخت اولیه)

| فاز | شرح | وضعیت |
|---|---|---|
| ۱ | زیرساخت ریشه و بک‌اند (کامپوز، env، تنظیمات، دیتابیس، مدل‌ها، امنیت، آلمبیک، main) | ✅ انجام شد |
| ۲ | اسکیماها، روت‌های API و سرویس‌ها (ویدیو، اینستاگرام، آمار، زمان‌بند، پروکسی) | ✅ انجام شد |
| ۳ | تسک‌های سلری و زمان‌بند Beat (پردازش، پست، آمار، بایو، پاک‌سازی) | ✅ انجام شد |
| ۴ | شالوده فرانت (پکیج‌ها، لی‌آوت، API کلاینت، تایپ‌ها، استورها، سایدبار، لاگین) | ✅ انجام شد |
| ۵ | همه صفحات داشبورد + کامپوننت‌ها و هوک‌ها | ✅ انجام شد |
| ۶ | وب‌سوکت بلادرنگ، Nginx، داکرفایل‌ها، README و راستی‌آزمایی نهایی | ✅ انجام شد |

## ۳. وصله‌های پایداری تولید (چهار اصلاح بحرانی)

### اصلاح ۱ — رفع Celery Poisoned Pool (بحرانی)

مشکل: تسک‌های سلری با `asyncio.run()` داخل تسک سینک، به‌ازای هر اجرا یک event loop جدید می‌ساختند؛ نتیجه نشتی حافظه، race condition و فریز ورکر زیر بار بود. راه‌حل: لایه تسک کاملاً سینک بازنویسی شد — `SYNC_DATABASE_URL` به تنظیمات اضافه شد، موتور و سشن سینک (`sync_engine`/`SyncSessionLocal`/`get_sync_db`) در `database.py`، فایل جدید `tasks/sync_helpers.py` با نسخه‌های بلاکینگ انتشار realtime، لاگ و توابع زمان‌بند، رانرهای سینک FFmpeg (`probe_sync`/`run_sync_with_progress` با `Popen` و خواندن خط‌به‌خط stderr) و `process_video_sync` در `video_processor.py`، و `check_proxy_sync` با سوکت بلاکینگ. هر سه فایل تسک بدون هیچ `asyncio`/`await`/`ThreadPoolExecutor` بازنویسی شدند؛ تأخیر ضدشناسایی با `time.sleep` انجام می‌شود.

### اصلاح ۲ — رفع اتمام حافظه در آپلود ویدیوهای حجیم

مشکل: نوشتن سینک فایل حجیم (تا ۵۰۰MB) می‌توانست حافظه ورکر وب را تحت فشار بگذارد. راه‌حل: `upload_video` با `aiofiles` به‌صورت استریمینگ بازنویسی شد — حلقه `while True` با چانک ۴MB، هش MD5 لحظه‌ای، بستن صریح فایل، حذف فایل ناقص در خطا/محدودیت حجم/فایل خالی، و اعتبارسنجی `ffprobe` (در ترد جدا با تایم‌اوت ۹۰ ثانیه) قبل از کامیت در دیتابیس.

### اصلاح ۳ — پیش‌نمایش زنده واترمارک و افکت در فرانت

مشکل: صفحه آپلود هیچ بازخورد بصری از واترمارک و افکت نداشت. راه‌حل: دو کامپوننت جدید `components/video-preview.tsx` (جدول `EFFECT_CSS`، لود `/watermark.png` با fallback، تابع `drawWatermark` منطبق بر فیلتر بک‌اند: عرض ۱۲۰px در خروجی ۷۲۰p با پدینگ ۲۰px) و `components/live-preview.tsx` (ویدیو + canvas اورلی با بازطراحی هر فریم روی play/seek/resize). صفحه آپلود با `URL.createObjectURL` پیش‌نمایش فوری نشان می‌دهد و انتخاب‌های افکت/واترمارک را پس از آپلود خودکار ذخیره می‌کند؛ صفحه جزئیات ویدیو هم همان `LivePreview` را با مقادیر فرم نمایش می‌دهد.

### اصلاح ۴ — اعتبارسنجی Docker Compose و SYNC DB URL

`SYNC_DATABASE_URL` به `.env.example` اضافه شد (با توضیح مشتق خودکار)، هر سه سرویس backend/worker/beat در کامپوز از انکر مشترک `x-backend-env` هر دو URL را می‌گیرند، `./data:/data` برای ماندگاری SQLite مونت شد، ورکر با `--pool=solo` اجرا می‌شود و `ffmpeg` در داکرفایل بک‌اند حفظ شده است.

## ۴. حذف کامل تلگرام از داشبورد

مدیریت بات تلگرام دیگر در اسکوپ پروژه نیست؛ بات‌ها خارجی‌اند و داشبورد صرفاً پردازش و پست اینستاگرام انجام می‌دهد. تغییرات:

- **بک‌اند:** فایل `services/telegram_service.py` حذف شد؛ `telegram_router` و اندپوینت‌های `GET/PUT /telegram` از `api/resources.py` حذف شدند؛ مدل `TelegramConfig` و جدول `telegram_configs` از مدل‌ها و مایگریشن اولیه (upgrade و downgrade) حذف شدند؛ اسکیماهای `TelegramIn/Out` حذف شدند؛ اندپوینت `POST /settings/test-telegram` و مقدار پیش‌فرض `funnel_enabled` حذف شدند؛ تابع `notify` (ارسال به Bot API) از `post_tasks.py` حذف شد و موفقیت/شکست فقط با `log_event_sync` در دیتابیس ثبت می‌شود؛ تسک `send_daily_summary` و ورودی `daily-summary` در Beat حذف شدند (۶ تسک دوره‌ای باقی ماند)؛ کلاس `TelegramError` و متغیرهای `TELEGRAM_*` در `.env.example` حذف شدند.
- **فرانت‌اند:** پوشه `dashboard/telegram/` حذف شد (۱۸ روت در بیلد، بدون مسیر تلگرام)؛ آیتم Telegram از سایدبار و ناوبری موبایل حذف شد؛ دکمه «Test Telegram» از تنظیمات حذف شد؛ هوک `useTelegram` و دسته `telegram` در فیلتر لاگ‌ها حذف شدند؛ متای `layout.tsx` به‌روزرسانی شد.
- **حفظ‌شده:** مدل `BioConfig` با فیلد `link_url` و صفحه Bios دست‌نخورده‌اند — ادمین لینک بات خارجی را همان‌جا در بایو ثبت می‌کند. فایل README هم از ارجاع‌های تلگرام پاک‌سازی شد.
- **راستی‌آزمایی حذف:** `compileall` و `tsc` و `npm run build` سبز؛ بک‌اند روی پورت ۸۰۱۴ بالا آمد و هر ۱۲ مسیر باقی‌مانده ۲۰۰ دادند؛ `/api/v1/telegram` مقدار ۴۰۴ و `/api/v1/settings/test-telegram` مقدار ۴۰۵ برگرداندند (حذف کامل)؛ تسک‌های سینک مستقیم اجرا و موفق شدند.

## ۵. نحوه اجرا

````bash
cp .env.example .env   # سپس SECRET_KEY و FERNET_KEY و ADMIN_PASSWORD را ست کنید
docker compose up --build
````
فرانت روی پورت ۳۰۰۰، API روی ۸۰۰۰ و سلامت روی `/health`. ترتیب اولین اجرا: اکانت‌ها → پروکسی‌ها → افکت‌ها → کپشن/هشتگ → بایو (با لینک بات خارجی) → قوانین زمان‌بندی → آپلود ویدیو.

---

## ۶. فایل‌ها و سورس کامل (91 فایل)

### `.env.example`

فایل نمونه متغیرهای محیطی (کلید JWT، رمز فرنت، اطلاعات ادمین، آدرس‌های دیتابیس آسنکرون و سینک، ردیس، محدودیت آپلود و…). متغیرهای تلگرام حذف شده‌اند چون بات‌ها خارجی‌اند.

```
# --- Core ---
ENV=production
SECRET_KEY=change-this-to-a-long-random-string
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=
APP_BASE_URL=http://localhost:8000

# --- Database ---
# Async URL (FastAPI): sqlite+aiosqlite:///./data/app.db
# Sync URL (Celery workers â€” sync SQLAlchemy engine, no event loop):
#   sqlite:///./data/app.db
# PostgreSQL (enable `postgres` profile):
#   async: postgresql+asyncpg://igfunnel:changeme@postgres:5432/igfunnel
#   sync:  postgresql+psycopg2://igfunnel:changeme@postgres:5432/igfunnel
# If SYNC_DATABASE_URL is left at its default while DATABASE_URL is customized,
# the backend derives the sync URL automatically (+aiosqlite -> plain, +asyncpg -> +psycopg2).
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
SYNC_DATABASE_URL=sqlite:///./data/app.db
POSTGRES_USER=igfunnel
POSTGRES_PASSWORD=changeme
POSTGRES_DB=igfunnel

# --- Redis / Celery ---
REDIS_URL=redis://localhost:6379/0

# --- Admin auth (single admin, credentials live here â€” never in the DB) ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme-please
JWT_EXPIRE_MINUTES=15
JWT_REFRESH_DAYS=7

# --- Media / uploads ---
MEDIA_ROOT=./media
MAX_UPLOAD_MB=500
AUTO_PROCESS_ON_UPLOAD=true

# --- CORS ---
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# --- Frontend ---
FRONTEND_API_URL=http://localhost:8000
NGINX_PORT=8080

# --- Instagram defaults ---
IG_DEFAULT_MAX_DAILY_POSTS=3
IG_PRE_POST_DELAY_MIN=30
IG_PRE_POST_DELAY_MAX=120
```

### `.gitignore`

مشخص می‌کند چه چیزهایی وارد گیت نشوند: فایل `.env`، دیتابیس لوکال، ویدیوهای خام و پردازش‌شده، سشن‌های اینستاگرام، `node_modules` و خروجی بیلد.

```
.env
__pycache__/
*.pyc
data/
media/raw/*
media/processed/*
media/thumbnails/*
!media/.gitkeep
!media/watermarks/.gitkeep
backend/sessions/
node_modules/
frontend/.next/
frontend/out/
*.log
.DS_Store
```

### `README.md`

راهنمای انگلیسی راه‌اندازی (به‌روزشده بدون تلگرام): معرفی پردازش و پست اینستاگرام، جدول سرویس‌ها، چک‌لیست اولین اجرا با لینک بات خارجی در بایو، و جدول عیب‌یابی.

````markdown
# IG Funnel - Instagram content processing and posting

Admin uploads videos via the dashboard. The backend processes them with FFmpeg,
posts them to Instagram Reels on schedule (Celery Beat). All configuration lives in the dashboard UI. The Instagram bio can link to an external Telegram bot.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: SECRET_KEY, FERNET_KEY, ADMIN_PASSWORD, DATABASE_URL…
docker compose up --build
```

- Frontend: http://localhost:3000 (or http://localhost:8080 via nginx profile)
- API: http://localhost:8000 — health at `/health`, docs at `/docs`
- Login with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

With the nginx profile (`docker compose --profile nginx up`), the whole stack is
served on `${NGINX_PORT:-8080}`: `/` → frontend, `/api/*` + `/ws` → backend.

## Services

| Service  | Role |
|----------|------|
| backend  | FastAPI + Uvicorn (port 8000) |
| worker   | Celery worker (video queue + posts queue) |
| beat     | Celery Beat (per-minute scheduler, analytics 4h, bio rotation, proxy checks, cleanup) |
| redis    | Broker + result backend + realtime pub/sub + progress keys |
| frontend | Next.js 14 dashboard |
| postgres | Optional — enable with `DATABASE_URL=postgresql+asyncpg://…` and `--profile postgres` |

Default is SQLite (`./data/app.db` via the `appdata` volume) — zero-config.

## Local dev (no Docker)

Backend needs Python 3.11+, FFmpeg, and Redis:

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # or set env vars
uvicorn app.main:app --reload
celery -A app.tasks.celery_app.celery worker --loglevel=info
celery -A app.tasks.celery_app.celery beat --loglevel=info
alembic upgrade head          # optional — app also auto-creates tables on startup
```

Frontend:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## First-run checklist

1. Log in → **Accounts** → add IG accounts (one proxy per account recommended).
2. **Proxies** → add proxies, health-check them.
3. **Effects** → review FFmpeg presets (applied after 720×1280 crop/scale).
4. **Captions / Hashtags** → seed pools (3–5 tags/post auto-rotated).
5. **Bios** - per-account bio + external bot link (e.g. https://t.me/your_external_bot), rotation interval.`n6. **Schedule** → rules (day/hour/minute); beat creates posts every minute with ±5 min jitter.
8. **Videos → Upload** → auto-processes (or trigger manually), then auto-posts at the next due slot.

## Database

Alembic migration `0001_initial` covers all tables. SQLite auto-creates on
startup; for Postgres run `alembic upgrade head`. Models live in
`backend/app/models/`; secrets (IG passwords, proxy passwords) are
Fernet-encrypted at rest — set a persistent `FERNET_KEY` in `.env`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Login fails | Check `ADMIN_USERNAME`/`ADMIN_PASSWORD` in `.env` (backend reads them at startup). |
| Video stuck in processing | Check worker logs; FFmpeg stderr is stored in `failed_reason` + SystemLog. |
| `challenge_required` account | Log in manually in the IG app, then **Accounts → Login** to refresh the session. |
| Throttled / cooldown | Account auto-cools for 24h; post retries with a different account. |
| WS not updating | Frontend falls back to polling (5–15s); check Redis is reachable. |
````

### `backend/Dockerfile`

ایمیج بک‌اند بر پایه `python:3.11-slim`؛ نصب `ffmpeg` سیستمی، نصب وابستگی‌ها و اجرای یوی‌کورن روی پورت ۸۰۰۰.

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `backend/alembic.ini`

تنظیمات پایه آلمبیک (مسیر اسکریپت‌ها و سطح لاگ).

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```

### `backend/alembic/env.py`

محیط آلمبیک: مدل‌ها را ایمپورت می‌کند تا autogenerate همه جدول‌ها را ببیند و مایگریشن را به‌صورت آسنکرون روی همان `DATABASE_URL` تنظیمات اجرا می‌کند.

```python
"""Alembic env — imports Base metadata so autogenerate sees all models."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 — register all models
from app.config import settings
from app.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.DATABASE_URL}, prefix="sqlalchemy.", poolclass=None
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

### `backend/alembic/versions/0001_initial.py`

مایگریشن اولیه: ساخت ۱۲ جدول (بدون `telegram_configs` — حذف‌شده). پروکسی، اکانت، ویدیو، پست، کپشن، هشتگ، زمان‌بند، بایو، افکت، لاگ و تنظیمات.

```python
"""Initial schema: all tables."""
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _ts_columns():
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "proxies",
        *_ts_columns(),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("protocol", sa.Enum("http", "socks5", "socks4", name="proxyprotocol"), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password_enc", sa.String(1024), nullable=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "accounts",
        *_ts_columns(),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_enc", sa.String(1024), nullable=False),
        sa.Column("proxy_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "cooldown", "banned", "challenge_required", "disabled", name="accountstatus"),
            nullable=False,
        ),
        sa.Column("session_file_path", sa.String(512), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_post", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posts_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_daily_posts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["proxy_id"], ["proxies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_username", "accounts", ["username"], unique=True)
    op.create_table(
        "videos",
        *_ts_columns(),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("raw_path", sa.String(1024), nullable=False),
        sa.Column("processed_path", sa.String(1024), nullable=True),
        sa.Column("thumbnail_path", sa.String(1024), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("md5_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("uploaded", "processing", "processed", "posting", "posted", "failed", "archived", name="videostatus"),
            nullable=False,
        ),
        sa.Column("upload_notes", sa.Text(), nullable=True),
        sa.Column("effect_preset", sa.String(128), nullable=True),
        sa.Column("custom_filters", sa.Text(), nullable=True),
        sa.Column("trim_start", sa.Float(), nullable=True),
        sa.Column("trim_end", sa.Float(), nullable=True),
        sa.Column("add_watermark", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_md5", "videos", ["md5_hash"], unique=True)
    op.create_table(
        "posts",
        *_ts_columns(),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("ig_media_id", sa.String(128), nullable=True),
        sa.Column("ig_permalink", sa.String(512), nullable=True),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("hashtags", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.Enum("scheduled", "posting", "posted", "failed", "deleted", "shadowbanned_check", name="poststatus"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views_1h", sa.Integer(), nullable=True),
        sa.Column("views_6h", sa.Integer(), nullable=True),
        sa.Column("views_24h", sa.Integer(), nullable=True),
        sa.Column("views_48h", sa.Integer(), nullable=True),
        sa.Column("views_7d", sa.Integer(), nullable=True),
        sa.Column("likes_1h", sa.Integer(), nullable=True),
        sa.Column("likes_24h", sa.Integer(), nullable=True),
        sa.Column("likes_7d", sa.Integer(), nullable=True),
        sa.Column("comments_24h", sa.Integer(), nullable=True),
        sa.Column("comments_7d", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("last_analytics_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "caption_templates",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_engagement", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "hashtag_sets",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schedule_rules",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("preferred_effect", sa.String(128), nullable=True),
        sa.Column("caption_template_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["caption_template_id"], ["caption_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bio_configs",
        *_ts_columns(),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("link_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_applied", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_interval_days", sa.Integer(), nullable=False, server_default="14"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "effect_presets",
        *_ts_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("ffmpeg_filter", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_engagement", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_effect_presets_name", "effect_presets", ["name"], unique=True)
    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", sa.Enum("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", name="loglevel"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_logs_category", "system_logs", ["category"])
    op.create_index("ix_logs_timestamp", "system_logs", ["timestamp"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    for table in [
        "settings", "system_logs", "effect_presets", "bio_configs",
        "schedule_rules", "hashtag_sets", "caption_templates", "posts", "videos", "accounts", "proxies",
    ]:
        op.drop_table(table)
```

### `backend/app/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/api/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/api/accounts.py`

مدیریت اکانت‌های اینستاگرام: لیست، ساخت، جزئیات، ویرایش، حذف، لاگین اجباری با ذخیره سشن، تست اعتبار سشن، خواب دستی، فعال‌سازی و آمار هر اکانت.

```python
"""IG accounts CRUD + session management."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, AccountStatus, Post, PostStatus
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.log_service import log_event

router = APIRouter()


def _out(a: Account) -> AccountOut:
    return AccountOut(
        id=a.id, username=a.username, proxy_id=a.proxy_id, status=a.status.value,
        last_login=a.last_login, last_post=a.last_post, posts_today=a.posts_today,
        max_daily_posts=a.max_daily_posts, cooldown_until=a.cooldown_until,
        total_posts=a.total_posts, total_views=a.total_views, total_likes=a.total_likes,
        notes=a.notes, created_at=a.created_at, updated_at=a.updated_at,
    )


@router.get("", response_model=list[AccountOut])
async def list_accounts(_: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    rows = (await db.execute(select(Account).order_by(Account.username))).scalars().all()
    return [_out(a) for a in rows]


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(body: AccountCreate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    from app.config import settings

    exists = (await db.execute(select(Account).where(Account.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Account already exists")
    acc = Account(
        username=body.username,
        password_enc=encrypt_secret(body.password),
        proxy_id=body.proxy_id,
        max_daily_posts=body.max_daily_posts or settings.IG_DEFAULT_MAX_DAILY_POSTS,
        notes=body.notes,
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    await log_event("INFO", "account", f"Account @{body.username} added")
    return _out(acc)


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return _out(acc)


@router.put("/{account_id}", response_model=AccountOut)
async def update_account(account_id: int, body: AccountUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    if body.max_daily_posts is not None:
        acc.max_daily_posts = body.max_daily_posts
    if body.notes is not None:
        acc.notes = body.notes
    if body.proxy_id is not None:
        acc.proxy_id = body.proxy_id
    if body.status is not None:
        try:
            acc.status = AccountStatus(body.status)
        except ValueError:
            raise HTTPException(400, "Invalid status")
    await db.commit()
    await db.refresh(acc)
    return _out(acc)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(__import__("app.api.deps", fromlist=["get_db"]).get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    await db.delete(acc)
    await db.commit()
    await log_event("INFO", "account", f"Account @{acc.username} removed")
    return None


def _blocking_login(username: str, password: str, proxy_url: str | None, session_path: str):
    from app.services.instagram_service import InstagramService

    return InstagramService(proxy_url=proxy_url, session_path=session_path).login(username, password)


@router.post("/{account_id}/login")
async def force_login(account_id: int, _: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.config import settings
    from app.models import Proxy
    from app.services.proxy_service import proxy_url_for
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        proxy = await db.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        username, password = acc.username, decrypt_secret(acc.password_enc)
        purl = proxy_url_for(proxy) if proxy else None
        spath = session_path_for(username, settings.MEDIA_ROOT)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        ok, detail = pool.submit(_blocking_login, username, password, purl, spath).result(timeout=180)
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if acc:
            if ok:
                acc.status = AccountStatus.active
                acc.last_login = dt.datetime.now(dt.timezone.utc)
                acc.session_file_path = spath
            elif detail.startswith("challenge"):
                acc.status = AccountStatus.challenge_required
            await db.commit()
    await log_event("INFO" if ok else "WARNING", "account", f"Manual login @{username}: {detail}")
    return {"ok": ok, "detail": detail}


@router.post("/{account_id}/test-session")
async def test_session(account_id: int, _: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.config import settings
    from app.models import Proxy
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        proxy = await db.get(Proxy, acc.proxy_id) if acc.proxy_id else None
        username = acc.username
        purl = proxy_url_for(proxy) if proxy else None
        spath = acc.session_file_path or session_path_for(username, settings.MEDIA_ROOT)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        valid = pool.submit(InstagramService(proxy_url=purl, session_path=spath).check_session, username).result(timeout=120)
    return {"valid": valid}


@router.post("/{account_id}/cooldown")
async def set_cooldown(account_id: int, hours: int = 24, _: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        acc.status = AccountStatus.cooldown
        acc.cooldown_until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
        await db.commit()
    return {"ok": True}


@router.post("/{account_id}/activate")
async def activate(account_id: int, _: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        acc.status = AccountStatus.active
        acc.cooldown_until = None
        await db.commit()
    return {"ok": True}


@router.get("/{account_id}/analytics")
async def account_analytics(account_id: int, _: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        acc = await db.get(Account, account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        rows = (
            await db.execute(
                select(
                    func.count(Post.id),
                    func.coalesce(func.sum(Post.views_7d), 0),
                    func.coalesce(func.sum(Post.likes_7d), 0),
                    func.avg(Post.engagement_rate),
                ).where(Post.account_id == account_id, Post.status == PostStatus.posted)
            )
        ).one()
        recent = (
            await db.execute(
                select(Post).where(Post.account_id == account_id).order_by(Post.created_at.desc()).limit(10)
            )
        ).scalars().all()
        return {
            "posts": rows[0],
            "views": int(rows[1] or 0),
            "likes": int(rows[2] or 0),
            "avg_engagement": round(float(rows[3] or 0), 2),
            "recent": [{"id": p.id, "status": p.status.value, "views_7d": p.views_7d, "posted_at": p.posted_at} for p in recent],
        }
```

### `backend/app/api/auth.py`

لاگین ادمین (اعتبار از `.env`، پشتیبانی از هش bcrypt)، تمدید توکن و دریافت مشخصات کاربر جاری؛ لاگین محدود به ۵ درخواست در دقیقه.

```python
"""Admin login — credentials come from .env (single admin, never in DB)."""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import limiter
from app.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.auth import LoginIn, MeOut, RefreshIn, TokenOut
from app.services.log_service import log_event

router = APIRouter()


@router.post("/login", response_model=TokenOut)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginIn):
    ok_user = body.username == settings.ADMIN_USERNAME
    # ADMIN_PASSWORD is stored in plaintext in .env; compare safely (allow bcrypt hash too).
    stored = settings.ADMIN_PASSWORD
    ok_pass = (body.password == stored) or (
        stored.startswith("$2") and bcrypt.checkpw(body.password.encode(), stored.encode())
    )
    if not (ok_user and ok_pass):
        await log_event("WARNING", "auth", f"Failed login attempt for '{body.username}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    await log_event("INFO", "auth", f"Admin '{body.username}' logged in")
    return TokenOut(
        access_token=create_access_token(body.username),
        refresh_token=create_refresh_token(body.username),
    )


@router.post("/refresh", response_model=TokenOut)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshIn):
    try:
        subject = decode_token(body.refresh_token, expected_type="refresh")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenOut(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


@router.get("/me", response_model=MeOut)
async def me(username: str = Depends(__import__("app.api.deps", fromlist=["get_current_admin"]).get_current_admin)):
    return MeOut(username=username)
```

### `backend/app/api/deps.py`

وابستگی‌های مشترک: استخراج کاربر ادمین از توکن JWT، لیمیتر slowapi و دسترسی به سشن دیتابیس.

```python
"""Shared dependencies: DB session, JWT auth guard, rate limiting."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.database import get_db

limiter = Limiter(key_func=get_remote_address)
bearer = HTTPBearer(auto_error=False)


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def admin_username() -> str:
    return settings.ADMIN_USERNAME

__all__ = ["get_db", "get_current_admin", "limiter", "admin_username"]
```

### `backend/app/api/resources.py`

مدیریت بایوها (ثبت، ویرایش، حذف، اعمال فوری روی پیج با لینک بات خارجی)، مدیریت پروکسی‌ها (تست سلامت تکی و گروهی) و افکت‌های ویدیویی. بخش تلگرام حذف شده است.

```python
"""Bios, proxies, effects."""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.security import decrypt_secret, encrypt_secret
from app.database import SessionLocal
from app.models import Account, BioConfig, EffectPreset, Proxy, ProxyProtocol
from app.schemas.account import ProxyCreate, ProxyOut, ProxyUpdate
from app.schemas.content import BioIn, BioOut, EffectIn, EffectOut
from app.services.log_service import log_event

bio_router = APIRouter()
proxy_router = APIRouter()
effect_router = APIRouter()


# ---- Bios ----

@bio_router.get("", response_model=list[BioOut])
async def list_bios(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BioConfig))).scalars().all()
    return [BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied) for b in rows]


@bio_router.post("", response_model=BioOut, status_code=201)
async def create_bio(body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, body.account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    b = BioConfig(**body.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied)


@bio_router.put("/{bid}", response_model=BioOut)
async def update_bio(bid: int, body: BioIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    await db.commit()
    await db.refresh(b)
    return BioOut(id=b.id, account_id=b.account_id, text=b.text, link_url=b.link_url, is_active=b.is_active, rotation_interval_days=b.rotation_interval_days, last_applied=b.last_applied)


@bio_router.delete("/{bid}", status_code=204)
async def delete_bio(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    await db.delete(b)
    await db.commit()
    return None


@bio_router.post("/{bid}/apply")
async def apply_bio(bid: int, _: str = Depends(get_current_admin)):
    import concurrent.futures

    from app.config import settings
    from app.services.instagram_service import InstagramService
    from app.utils.instagram_helpers import session_path_for

    async with SessionLocal() as db:
        b = await db.get(BioConfig, bid)
        if not b:
            raise HTTPException(404, "Bio not found")
        acc = await db.get(Account, b.account_id)
        if not acc:
            raise HTTPException(404, "Account not found")
        username, password, text, link = acc.username, decrypt_secret(acc.password_enc), b.text, b.link_url
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        err = pool.submit(
            InstagramService(session_path=session_path_for(username, settings.MEDIA_ROOT)).apply_bio,
            username, password, text, link or "",
        ).result(timeout=180)
    if err:
        raise HTTPException(502, f"Bio apply failed: {err}")
    async with SessionLocal() as db:
        b = await db.get(BioConfig, bid)
        if b:
            b.last_applied = dt.datetime.now(dt.timezone.utc)
            await db.commit()
    await log_event("INFO", "account", f"Bio force-applied to account {acc.id if 'acc' in dir() else ''}")
    return {"ok": True}


@bio_router.get("/{bid}/history")
async def bio_history(bid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import SystemLog

    b = await db.get(BioConfig, bid)
    if not b:
        raise HTTPException(404, "Bio not found")
    rows = (
        await db.execute(
            select(SystemLog).where(SystemLog.category == "account").order_by(SystemLog.timestamp.desc()).limit(50)
        )
    ).scalars().all()
    return [{"message": r.message, "timestamp": r.timestamp} for r in rows]


# ---- Proxies ----

def _proxy_out(p: Proxy) -> ProxyOut:
    return ProxyOut(
        id=p.id, url=p.url, protocol=p.protocol.value, username=p.username, country=p.country,
        is_healthy=p.is_healthy, last_checked=p.last_checked, fail_count=p.fail_count,
        latency_ms=p.latency_ms, is_active=p.is_active, created_at=p.created_at,
    )


@proxy_router.get("", response_model=list[ProxyOut])
async def list_proxies(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Proxy).order_by(Proxy.id))).scalars().all()
    return [_proxy_out(p) for p in rows]


@proxy_router.post("", response_model=ProxyOut, status_code=201)
async def create_proxy(body: ProxyCreate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    try:
        proto = ProxyProtocol(body.protocol)
    except ValueError:
        raise HTTPException(400, "Invalid protocol")
    p = Proxy(url=body.url, protocol=proto, username=body.username,
              password_enc=encrypt_secret(body.password) if body.password else None, country=body.country)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _proxy_out(p)


@proxy_router.put("/{pid}", response_model=ProxyOut)
async def update_proxy(pid: int, body: ProxyUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    if body.url is not None:
        p.url = body.url
    if body.protocol is not None:
        try:
            p.protocol = ProxyProtocol(body.protocol)
        except ValueError:
            raise HTTPException(400, "Invalid protocol")
    if body.username is not None:
        p.username = body.username
    if body.password is not None:
        p.password_enc = encrypt_secret(body.password)
    if body.country is not None:
        p.country = body.country
    if body.is_active is not None:
        p.is_active = body.is_active
    await db.commit()
    await db.refresh(p)
    return _proxy_out(p)


@proxy_router.delete("/{pid}", status_code=204)
async def delete_proxy(pid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    await db.delete(p)
    await db.commit()
    return None


@proxy_router.post("/{pid}/test")
async def test_proxy(pid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt2

    from app.services.proxy_service import check_proxy

    p = await db.get(Proxy, pid)
    if not p:
        raise HTTPException(404, "Proxy not found")
    ok, latency = await check_proxy(p)
    p.is_healthy = ok
    p.latency_ms = latency
    p.last_checked = dt2.datetime.now(dt2.timezone.utc)
    p.fail_count = 0 if ok else p.fail_count + 1
    await db.commit()
    return {"healthy": ok, "latency_ms": latency}


@proxy_router.post("/check-all")
async def check_all(_: str = Depends(get_current_admin)):
    from app.tasks.periodic_tasks import check_all_proxies

    check_all_proxies.delay()
    return {"queued": True}


# ---- Effects ----

@effect_router.get("", response_model=list[EffectOut])
async def list_effects(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(EffectPreset).order_by(EffectPreset.name))).scalars().all()
    return [EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement) for e in rows]


@effect_router.post("", response_model=EffectOut, status_code=201)
async def create_effect(body: EffectIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(EffectPreset).where(EffectPreset.name == body.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Effect preset already exists")
    e = EffectPreset(**body.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement)


@effect_router.put("/{eid}", response_model=EffectOut)
async def update_effect(eid: int, body: EffectIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    e = await db.get(EffectPreset, eid)
    if not e:
        raise HTTPException(404, "Effect not found")
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    await db.commit()
    await db.refresh(e)
    return EffectOut(id=e.id, name=e.name, description=e.description, ffmpeg_filter=e.ffmpeg_filter, is_active=e.is_active, use_count=e.use_count, avg_engagement=e.avg_engagement)


@effect_router.delete("/{eid}", status_code=204)
async def delete_effect(eid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    e = await db.get(EffectPreset, eid)
    if not e:
        raise HTTPException(404, "Effect not found")
    await db.delete(e)
    await db.commit()
    return None
```

### `backend/app/api/router.py`

روتر اصلی: سوار کردن همه زیرروترها زیر پیشوند `/api/v1` (بدون روتر تلگرام) و جدا نگه داشتن وب‌سوکت برای نصب در ریشه.

```python
"""Main API router â€” mounts every resource under /api/v1."""
from fastapi import APIRouter

from app.api import auth
from app.api.accounts import router as accounts_router
from app.api.resources import bio_router, effect_router, proxy_router
from app.api.scheduling import caption_router, hashtag_router, schedule_router
from app.api.system import analytics_router, logs_router, settings_router, ws_router
from app.api.videos import posts_router, router as videos_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(videos_router, prefix="/videos", tags=["videos"])
router.include_router(posts_router, prefix="/posts", tags=["posts"])
router.include_router(schedule_router, prefix="/schedule", tags=["schedule"])
router.include_router(caption_router, prefix="/captions", tags=["captions"])
router.include_router(hashtag_router, prefix="/hashtags", tags=["hashtags"])
router.include_router(bio_router, prefix="/bios", tags=["bios"])
router.include_router(proxy_router, prefix="/proxies", tags=["proxies"])
router.include_router(effect_router, prefix="/effects", tags=["effects"])
router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
router.include_router(logs_router, prefix="/logs", tags=["logs"])
router.include_router(settings_router, prefix="/settings", tags=["settings"])
# WebSocket is mounted on the app root (not under /api/v1) by main.py.
ws_mount = ws_router
```

### `backend/app/api/scheduling.py`

قوانین زمان‌بندی (ساخت/ویرایش/حذف/توقف)، داده نمای تقویم، مدیریت قالب‌های کپشن (با آمار عملکرد) و مجموعه‌های هشتگ.

```python
"""Schedule rules, captions, hashtag sets."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.models import CaptionTemplate, HashtagSet, ScheduleRule
from app.schemas.content import (
    CaptionIn, CaptionOut, HashtagSetIn, HashtagSetOut, ScheduleRuleIn, ScheduleRuleOut,
)

schedule_router = APIRouter()
caption_router = APIRouter()
hashtag_router = APIRouter()


def _rule_out(r: ScheduleRule) -> ScheduleRuleOut:
    return ScheduleRuleOut(
        id=r.id, name=r.name, day_of_week=r.day_of_week, hour=r.hour, minute=r.minute,
        account_id=r.account_id, is_active=r.is_active, preferred_effect=r.preferred_effect,
        caption_template_id=r.caption_template_id, created_at=r.created_at,
    )


@schedule_router.get("", response_model=list[ScheduleRuleOut])
async def list_rules(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ScheduleRule).order_by(ScheduleRule.hour, ScheduleRule.minute))).scalars().all()
    return [_rule_out(r) for r in rows]


@schedule_router.post("", response_model=ScheduleRuleOut, status_code=201)
async def create_rule(body: ScheduleRuleIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = ScheduleRule(**body.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _rule_out(r)


@schedule_router.put("/{rule_id}", response_model=ScheduleRuleOut)
async def update_rule(rule_id: int, body: ScheduleRuleIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    await db.commit()
    await db.refresh(r)
    return _rule_out(r)


@schedule_router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    await db.delete(r)
    await db.commit()
    return None


@schedule_router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(ScheduleRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    r.is_active = not r.is_active
    await db.commit()
    return {"is_active": r.is_active}


@schedule_router.get("/calendar/data")
async def calendar(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select as sel

    from app.models import Post, PostStatus

    rules = (await db.execute(select(ScheduleRule))).scalars().all()
    upcoming = (
        await db.execute(
            sel(Post).where(Post.status == PostStatus.scheduled).order_by(Post.scheduled_for.asc()).limit(200)
        )
    ).scalars().all()
    return {
        "rules": [_rule_out(r).model_dump() for r in rules],
        "upcoming": [{"id": p.id, "account_id": p.account_id, "scheduled_for": p.scheduled_for} for p in upcoming],
    }


# ---- Captions ----

@caption_router.get("", response_model=list[CaptionOut])
async def list_captions(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(CaptionTemplate).order_by(CaptionTemplate.name))).scalars().all()
    return [CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement) for c in rows]


@caption_router.post("", response_model=CaptionOut, status_code=201)
async def create_caption(body: CaptionIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = CaptionTemplate(**body.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement)


@caption_router.put("/{cid}", response_model=CaptionOut)
async def update_caption(cid: int, body: CaptionIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return CaptionOut(id=c.id, name=c.name, content=c.content, category=c.category, is_active=c.is_active, use_count=c.use_count, avg_engagement=c.avg_engagement)


@caption_router.delete("/{cid}", status_code=204)
async def delete_caption(cid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    await db.delete(c)
    await db.commit()
    return None


@caption_router.get("/{cid}/performance")
async def caption_performance(cid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func

    from app.models import Post, PostStatus

    c = await db.get(CaptionTemplate, cid)
    if not c:
        raise HTTPException(404, "Caption not found")
    # Approximate: posts whose caption matches this template exactly.
    row = (
        await db.execute(
            select(func.count(Post.id), func.avg(Post.engagement_rate), func.coalesce(func.sum(Post.views_7d), 0)).where(
                Post.caption == c.content, Post.status == PostStatus.posted
            )
        )
    ).one()
    return {"use_count": c.use_count, "matched_posts": row[0], "avg_engagement": round(float(row[1] or 0), 2), "total_views": int(row[2] or 0)}


# ---- Hashtags ----

@hashtag_router.get("", response_model=list[HashtagSetOut])
async def list_tags(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(HashtagSet).order_by(HashtagSet.name))).scalars().all()
    return [HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count) for h in rows]


@hashtag_router.post("", response_model=HashtagSetOut, status_code=201)
async def create_tags(body: HashtagSetIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = HashtagSet(**body.model_dump())
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count)


@hashtag_router.put("/{hid}", response_model=HashtagSetOut)
async def update_tags(hid: int, body: HashtagSetIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = await db.get(HashtagSet, hid)
    if not h:
        raise HTTPException(404, "Hashtag set not found")
    for k, v in body.model_dump().items():
        setattr(h, k, v)
    await db.commit()
    await db.refresh(h)
    return HashtagSetOut(id=h.id, name=h.name, tags=h.tags, is_active=h.is_active, use_count=h.use_count)


@hashtag_router.delete("/{hid}", status_code=204)
async def delete_tags(hid: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    h = await db.get(HashtagSet, hid)
    if not h:
        raise HTTPException(404, "Hashtag set not found")
    await db.delete(h)
    await db.commit()
    return None
```

### `backend/app/api/system.py`

آمار تحلیلی (نمای کلی، عملکرد پست‌ها/اکانت‌ها/افکت‌ها/کپشن‌ها/بازه‌های زمانی، خروجی CSV)، مشاهده و هرس لاگ‌ها، تنظیمات سراسری، تست اتصال اینستاگرام، و وب‌سوکت `/ws`. اندپوینت تست تلگرام حذف شده است.

```python
"""Analytics, logs, global settings, WebSocket feed."""
import csv
import datetime as dt
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_current_admin, get_db
from app.config import settings
from app.core.security import decode_token
from app.database import SessionLocal
from app.models import LogLevel, Post, PostStatus, Setting, SystemLog
from app.schemas.content import LogOut, SettingOut
from app.services import analytics_service, log_service

analytics_router = APIRouter()
logs_router = APIRouter()
settings_router = APIRouter()


@analytics_router.get("/overview")
async def overview(days: int = Query(default=30, le=365), _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    data = await analytics_service.overview(db, since)
    data["series"] = await analytics_service.views_over_time(db, days)
    return data


@analytics_router.get("/posts")
async def posts_breakdown(limit: int = 100, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Post).where(Post.status == PostStatus.posted).order_by(desc(Post.posted_at)).limit(limit))).scalars().all()
    return [
        {"id": p.id, "account_id": p.account_id, "views_7d": p.views_7d, "likes_7d": p.likes_7d,
         "comments_7d": p.comments_7d, "engagement_rate": p.engagement_rate, "posted_at": p.posted_at}
        for p in rows
    ]


@analytics_router.get("/accounts")
async def accounts_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await analytics_service.account_comparison(db)


@analytics_router.get("/effects")
async def effects_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import EffectPreset, Video

    presets = (await db.execute(select(EffectPreset))).scalars().all()
    out = []
    for preset in presets:
        row = (
            await db.execute(
                select(func.count(Post.id), func.avg(Post.engagement_rate), func.coalesce(func.sum(Post.views_7d), 0))
                .join(Video, Video.id == Post.video_id)
                .where(Video.effect_preset == preset.name, Post.status == PostStatus.posted)
            )
        ).one()
        out.append({"name": preset.name, "posts": row[0], "avg_engagement": round(float(row[1] or 0), 2), "views": int(row[2] or 0)})
    return out


@analytics_router.get("/captions")
async def captions_breakdown(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models import CaptionTemplate

    templates = (await db.execute(select(CaptionTemplate))).scalars().all()
    return [{"id": t.id, "name": t.name, "use_count": t.use_count, "avg_engagement": t.avg_engagement} for t in templates]


@analytics_router.get("/time-slots")
async def time_slots(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await analytics_service.time_slot_performance(db)


@analytics_router.get("/export")
async def export_csv(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Post).where(Post.status == PostStatus.posted).order_by(desc(Post.posted_at)).limit(2000))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "account_id", "posted_at", "views_7d", "likes_7d", "comments_7d", "engagement_rate", "url"])
    for p in rows:
        w.writerow([p.id, p.account_id, p.posted_at, p.views_7d, p.likes_7d, p.comments_7d, p.engagement_rate, p.ig_permalink])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=analytics.csv"})


# ---- Logs ----

@logs_router.get("", response_model=list[LogOut])
async def list_logs(
    level: str | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(SystemLog).order_by(desc(SystemLog.timestamp)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    if level:
        rows = [r for r in rows if r.level.value == level.upper()]
    if category:
        rows = [r for r in rows if r.category == category]
    if search:
        rows = [r for r in rows if search.lower() in r.message.lower()]
    return [LogOut(id=r.id, level=r.level.value, category=r.category, message=r.message, details=r.details, timestamp=r.timestamp) for r in rows]


@logs_router.get("/stats")
async def logs_stats(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SystemLog.level, func.count(SystemLog.id)).group_by(SystemLog.level))).all()
    return {r[0].value: r[1] for r in rows}


@logs_router.delete("", status_code=204)
async def clear_logs(older_than_days: int = 30, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than_days)
    await db.execute(delete(SystemLog).where(SystemLog.timestamp < cutoff))
    await db.commit()
    return None


# ---- Settings ----

DEFAULT_SETTINGS = {
    "auto_process_on_upload": ("true", "processing"),
    "default_effect": ("", "processing"),
    "watermark_enabled": ("true", "processing"),
    "post_jitter_minutes": ("5", "scheduler"),
    "analytics_refresh_hours": ("4", "scheduler"),
}

MASKED = "â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"


@settings_router.get("", response_model=list[SettingOut])
async def list_settings(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    for key, (val, cat) in DEFAULT_SETTINGS.items():
        if not await db.get(Setting, key):
            db.add(Setting(key=key, value=val, category=cat))
    await db.commit()
    rows = (await db.execute(select(Setting).order_by(Setting.category, Setting.key))).scalars().all()
    return [SettingOut(key=s.key, value=(MASKED if s.is_sensitive and s.value else s.value), category=s.category, is_sensitive=s.is_sensitive) for s in rows]


@settings_router.put("/{key}", response_model=SettingOut)
async def update_setting(key: str, value: str, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    s = await db.get(Setting, key)
    if not s:
        s = Setting(key=key, value=value, category="general")
        db.add(s)
    else:
        s.value = value
        s.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await db.refresh(s)
    return SettingOut(key=s.key, value=(MASKED if s.is_sensitive else s.value), category=s.category, is_sensitive=s.is_sensitive)


@settings_router.post("/test-instagram")
async def test_instagram(_: str = Depends(get_current_admin)):
    async with SessionLocal() as db:
        from app.models import Account

        count = (await db.execute(select(func.count(Account.id)))).scalar() or 0
    return {"ok": True, "accounts": count, "note": "Use /accounts/{id}/test-session for a live session check"}


# ---- WebSocket ----

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def ws_feed(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token", "")
    try:
        decode_token(token, expected_type="access")
    except ValueError:
        await websocket.close(code=4401)
        return
    client = None
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("igfunnel:events")
        await websocket.send_text(json.dumps({"event": "connected"}))
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20.0)
            if msg and msg.get("data"):
                await websocket.send_text(msg["data"])
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        try:
            if client is not None:
                await client.aclose()
        except Exception:
            pass
```

### `backend/app/api/videos.py`

آپلود استریمینگ با aiofiles (حافظه ثابت، هش MD5 لحظه‌ای، بستن فایل، اعتبارسنجی ffprobe قبل از کامیت)، لیست و فیلتر، حذف، شروع پردازش، وضعیت پیشرفت، تنظیمات هر ویدیو، پیش‌نمایش و بندانگشتی؛ به‌علاوه روتر پست‌ها.

```python
"""Video upload / processing / preview + post history endpoints."""
import asyncio
import hashlib
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.config import settings
from app.models import Post, PostStatus, Video, VideoStatus
from app.schemas.video import PostOut, SchedulePostIn, VideoOut, VideoSettingsUpdate
from app.services import realtime
from app.services.log_service import log_event
from app.services.video_processor import md5_of_file, media_dirs

router = APIRouter()

ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
UPLOAD_CHUNK = 4 * 1024 * 1024


def _out(v: Video) -> VideoOut:
    return VideoOut(
        id=v.id, original_filename=v.original_filename, duration=v.duration, file_size=v.file_size,
        status=v.status.value, effect_preset=v.effect_preset, add_watermark=v.add_watermark,
        trim_start=v.trim_start, trim_end=v.trim_end, failed_reason=v.failed_reason,
        processed_at=v.processed_at, thumbnail_path=v.thumbnail_path, created_at=v.created_at,
    )


def _post_out(p: Post) -> PostOut:
    return PostOut(
        id=p.id, video_id=p.video_id, account_id=p.account_id, ig_media_id=p.ig_media_id,
        ig_permalink=p.ig_permalink, caption=p.caption, hashtags=p.hashtags, status=p.status.value,
        scheduled_for=p.scheduled_for, posted_at=p.posted_at, views_24h=p.views_24h,
        views_7d=p.views_7d, likes_24h=p.likes_24h, engagement_rate=p.engagement_rate,
        fail_reason=p.fail_reason, retry_count=p.retry_count, created_at=p.created_at,
    )


@router.get("", response_model=list[VideoOut])
async def list_videos(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Video).order_by(desc(Video.created_at)).limit(limit)
    if status:
        try:
            q = select(Video).where(Video.status == VideoStatus(status)).order_by(desc(Video.created_at)).limit(limit)
        except ValueError:
            raise HTTPException(400, "Invalid status")
    rows = (await db.execute(q)).scalars().all()
    if search:
        rows = [v for v in rows if search.lower() in v.original_filename.lower()]
    return [_out(v) for v in rows]


@router.post("/upload", response_model=VideoOut, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.utils import ffmpeg as ff

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type {ext}. Allowed: {sorted(ALLOWED_EXT)}")
    dirs = media_dirs()
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    raw_path = os.path.join(dirs["raw"], tmp_name)
    size = 0
    h = hashlib.md5()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    try:
        # Stream straight to disk (constant memory, regardless of file size).
        async with aiofiles.open(raw_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")
                h.update(chunk)
                await f.write(chunk)
    except HTTPException:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        await file.close()
        raise
    except Exception as exc:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        await file.close()
        raise HTTPException(400, f"Upload failed: {exc}")
    finally:
        try:
            await file.close()
        except Exception:
            pass
    if size == 0:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        raise HTTPException(400, "Empty file")
    digest = h.hexdigest()
    dup = (await db.execute(select(Video).where(Video.md5_hash == digest))).scalar_one_or_none()
    if dup:
        os.remove(raw_path)
        raise HTTPException(409, f"Duplicate of video #{dup.id} ({dup.original_filename})")
    # Validate the container before committing: reject corrupt/non-video uploads early.
    try:
        probe = await asyncio.wait_for(asyncio.to_thread(ff.probe_sync, raw_path), timeout=90)
    except Exception:
        os.remove(raw_path)
        raise HTTPException(422, "File is not a valid video (ffprobe validation failed)")
    video = Video(
        original_filename=file.filename or tmp_name,
        raw_path=raw_path,
        file_size=size,
        md5_hash=digest,
        duration=probe.get("duration"),
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    await log_event("INFO", "video", f"Uploaded {video.original_filename} (#{video.id})")
    if settings.AUTO_PROCESS_ON_UPLOAD:
        from app.tasks.video_tasks import process_video_task

        process_video_task.delay(video.id)
    return _out(video)


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _out(v)


@router.delete("/{video_id}", status_code=204)
async def delete_video(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    for path in (v.raw_path, v.processed_path, v.thumbnail_path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    await db.delete(v)
    await db.commit()
    return None


@router.post("/{video_id}/process")
async def trigger_process(video_id: int, effect_filter: str = "", _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status == VideoStatus.processing:
        raise HTTPException(409, "Already processing")
    from app.tasks.video_tasks import process_video_task

    process_video_task.delay(video_id, effect_filter)
    return {"queued": True}


@router.post("/{video_id}/reprocess")
async def reprocess(video_id: int, effect_filter: str = "", _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    from app.tasks.video_tasks import process_video_task

    process_video_task.delay(video_id, effect_filter)
    return {"queued": True}


@router.get("/{video_id}/status")
async def processing_status(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    progress = await realtime.get_progress(video_id)
    return {"status": v.status.value, "progress": progress, "failed_reason": v.failed_reason}


@router.put("/{video_id}/settings", response_model=VideoOut)
async def update_settings(video_id: int, body: VideoSettingsUpdate, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    for field in ("effect_preset", "custom_filters", "trim_start", "trim_end", "add_watermark"):
        val = getattr(body, field)
        if val is not None:
            setattr(v, field, val)
    await db.commit()
    await db.refresh(v)
    return _out(v)


def _serve(path: str | None, media_type: str):
    if not path or not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=media_type)


@router.get("/{video_id}/preview")
async def preview(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _serve(v.processed_path or v.raw_path, "video/mp4")


@router.get("/{video_id}/thumbnail")
async def thumbnail(video_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    v = await db.get(Video, video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return _serve(v.thumbnail_path, "image/jpeg")


# ---- Posts ----

posts_router = APIRouter()


@posts_router.get("", response_model=list[PostOut])
async def list_posts(
    status: str | None = Query(default=None),
    account_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    _: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Post).order_by(desc(Post.created_at)).limit(limit)
    if status:
        try:
            q = select(Post).where(Post.status == PostStatus(status)).order_by(desc(Post.created_at)).limit(limit)
        except ValueError:
            raise HTTPException(400, "Invalid status")
    rows = (await db.execute(q)).scalars().all()
    if account_id:
        rows = [p for p in rows if p.account_id == account_id]
    return [_post_out(p) for p in rows]


@posts_router.get("/queue", response_model=list[PostOut])
async def post_queue(_: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt

    rows = (
        await db.execute(
            select(Post)
            .where(Post.status == PostStatus.scheduled)
            .order_by(Post.scheduled_for.asc().nulls_first())
            .limit(100)
        )
    ).scalars().all()
    return [_post_out(p) for p in rows]


@posts_router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    return _post_out(p)


@posts_router.post("/schedule", response_model=PostOut, status_code=201)
async def schedule_post(body: SchedulePostIn, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    import datetime as dt

    v = await db.get(Video, body.video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    if v.status != VideoStatus.processed:
        raise HTTPException(400, f"Video must be processed first (now: {v.status.value})")
    account_id = body.account_id
    if not account_id:
        from app.services import scheduler_service

        acc = await scheduler_service.eligible_account(db, None)
        if not acc:
            raise HTTPException(400, "No eligible account available")
        account_id = acc.id
    post = Post(
        video_id=body.video_id, account_id=account_id, caption=body.caption,
        hashtags=body.hashtags, status=PostStatus.scheduled,
        scheduled_for=body.scheduled_for or dt.datetime.now(dt.timezone.utc),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_out(post)


@posts_router.post("/{post_id}/retry")
async def retry_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    if p.status != PostStatus.failed:
        raise HTTPException(400, "Only failed posts can be retried")
    p.status = PostStatus.scheduled
    import datetime as dt

    p.scheduled_for = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    from app.tasks.post_tasks import execute_post

    execute_post.delay(post_id)
    return {"queued": True}


@posts_router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int, _: str = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    p = await db.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Post not found")
    await db.delete(p)
    await db.commit()
    return None
```

### `backend/app/config.py`

تنظیمات مرکزی با pydantic-settings. `SYNC_DATABASE_URL` با مشتق خودکار از `DATABASE_URL` (`+aiosqlite`→حذف، `+asyncpg`→`+psycopg2`).

```python
"""Central application settings (pydantic-settings, loaded from .env)."""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"
DEFAULT_SYNC_DATABASE_URL = "sqlite:///./data/app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "IG Funnel"
    ENV: str = "production"
    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = ""
    APP_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    # Sync URL for Celery workers (sync SQLAlchemy engine — never asyncio in tasks).
    SYNC_DATABASE_URL: str = DEFAULT_SYNC_DATABASE_URL
    REDIS_URL: str = "redis://localhost:6379/0"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme-please"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_DAYS: int = 7

    MEDIA_ROOT: str = "./media"
    MAX_UPLOAD_MB: int = 500
    AUTO_PROCESS_ON_UPLOAD: bool = True

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    IG_DEFAULT_MAX_DAILY_POSTS: int = 3
    IG_PRE_POST_DELAY_MIN: int = 30
    IG_PRE_POST_DELAY_MAX: int = 120

    @model_validator(mode="after")
    def _derive_sync_url(self):
        """If only the async URL was customized, derive the sync one from it."""
        if self.SYNC_DATABASE_URL == DEFAULT_SYNC_DATABASE_URL and self.DATABASE_URL != DEFAULT_DATABASE_URL:
            if "+aiosqlite" in self.DATABASE_URL:
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace("+aiosqlite", "")
            elif "+asyncpg" in self.DATABASE_URL:
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.FERNET_KEY:
        from cryptography.fernet import Fernet

        settings.FERNET_KEY = Fernet.generate_key().decode()
        import logging

        logging.getLogger(__name__).warning(
            "FERNET_KEY not set — generated an ephemeral key. "
            "Encrypted credentials will be unreadable after restart. "
            "Set FERNET_KEY in .env (see .env.example)."
        )
    return settings


settings = get_settings()
```

### `backend/app/core/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/core/exceptions.py`

سلسله‌مراتب خطاهای سفارشی (اکانت، پردازش ویدیو، اینستاگرام، زمان‌بند، ۴۰۴، احراز هویت). کلاس `TelegramError` حذف شده است.

```python
"""Custom exception hierarchy â†’ mapped to HTTP responses in main.py."""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AccountError(AppError):
    code = "account_error"
    status_code = 400


class VideoProcessingError(AppError):
    code = "video_processing_error"
    status_code = 422


class InstagramError(AppError):
    code = "instagram_error"
    status_code = 502



class ScheduleError(AppError):
    code = "schedule_error"
    status_code = 400


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class AuthError(AppError):
    code = "auth_error"
    status_code = 401
```

### `backend/app/core/middleware.py`

میدل‌ویر CORS (محدود به دامنه فرانت) و لاگ هر درخواست با شناسه یکتا و زمان پاسخ.

```python
"""CORS + request logging. Auth is enforced per-route via dependencies."""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

log = logging.getLogger("igfunnel.http")


def setup_middleware(app: FastAPI) -> None:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()
        try:
            response = await call_next(request)
            log.info(
                "%s %s -> %s (%.1fms) [%s]",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started) * 1000,
                request_id,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log.exception("Unhandled error for %s %s [%s]", request.method, request.url.path, request_id)
            raise
```

### `backend/app/core/security.py`

امنیت: رمزنگاری فرنت برای اسرار ذخیره‌شده، هش bcrypt، ساخت و اعتبارسنجی توکن‌های دسترسی (۱۵ دقیقه) و تمدید (۷ روزه).

```python
"""JWT auth, bcrypt passwords, Fernet encryption for stored secrets."""
import datetime as dt

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt_secret(plaintext: str | None) -> str | None:
    if not plaintext:
        return plaintext
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return token
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        # Legacy plaintext value stored before encryption was enabled.
        return token


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def _encode(payload: dict, expires: dt.timedelta) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_access_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "access"}, dt.timedelta(minutes=settings.JWT_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "refresh"}, dt.timedelta(days=settings.JWT_REFRESH_DAYS))


def decode_token(token: str, expected_type: str = "access") -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Wrong token type")
    return str(payload["sub"])
```

### `backend/app/database.py`

موتور آسنکرون برای API وب + موتور سینک (`sync_engine`/`SyncSessionLocal`) برای ورکرهای سلری، به‌همراه کانتکست‌منجر `get_sync_db` با کامیت/رول‌بک.

```python
"""Async engine for the web API + sync engine for Celery workers.

Celery tasks are fully synchronous and must NEVER create an event loop
(via asyncio.run) — they use SyncSessionLocal below.
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_connect_args: dict = {}
if settings.SYNC_DATABASE_URL.startswith("sqlite"):
    sync_connect_args = {"check_same_thread": False, "timeout": 30}

sync_engine = create_engine(settings.SYNC_DATABASE_URL, echo=False, connect_args=sync_connect_args)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_sync_db():
    """Sync session helper for Celery tasks and scripts (commit/rollback included)."""
    with SyncSessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
```

### `backend/app/main.py`

نقطه ورود فست‌ای‌پی: میدل‌ویر، هندلر خطای یکدست، مسیر سلامت `/health`، سوار کردن روتر و وب‌سوکت؛ در استارتاپ پوشه‌های مدیا را می‌سازد و جدول‌ها را ایجاد می‌کند.

```python
"""FastAPI entrypoint: middleware, error envelope, health, routers, startup init."""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import limiter
from app.api.router import router, ws_mount
from app.config import settings
from app.core.exceptions import AppError
from app.core.middleware import setup_middleware
from app.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("igfunnel")

app = FastAPI(title="IG Funnel API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
setup_middleware(app)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


@app.get("/health")
async def health():
    return {"ok": True, "env": settings.ENV}


app.include_router(router)
app.include_router(ws_mount)


@app.on_event("startup")
async def startup():
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    for sub in ("raw", "processed", "thumbnails", "watermarks", "sessions"):
        os.makedirs(os.path.join(settings.MEDIA_ROOT, sub), exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("IG Funnel API ready (env=%s)", settings.ENV)
```

### `backend/app/models/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python
from app.models.account import Account, AccountStatus, Proxy, ProxyProtocol
from app.models.content import (
    BioConfig,
    CaptionTemplate,
    EffectPreset,
    HashtagSet,
    LogLevel,
    ScheduleRule,
    Setting,
    SystemLog
)
from app.models.video import Post, PostStatus, Video, VideoStatus

__all__ = [
    "Account",
    "AccountStatus",
    "Proxy",
    "ProxyProtocol",
    "Video",
    "VideoStatus",
    "Post",
    "PostStatus",
    "ScheduleRule",
    "CaptionTemplate",
    "HashtagSet",
    "BioConfig",
    "EffectPreset",
    "SystemLog",
    "LogLevel",
    "Setting",
]
```

### `backend/app/models/account.py`

مدل‌های اکانت اینستاگرام (وضعیت، سشن، سهمیه روزانه، آمار تجمیعی) و پروکسی (پروتکل، سلامت، تأخیر، شمار خطا).

```python
"""IG account + proxy models."""
import datetime as dt
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class AccountStatus(str, enum.Enum):
    active = "active"
    cooldown = "cooldown"
    banned = "banned"
    challenge_required = "challenge_required"
    disabled = "disabled"


class ProxyProtocol(str, enum.Enum):
    http = "http"
    socks5 = "socks5"
    socks4 = "socks4"


class Proxy(Base, TimestampMixin):
    __tablename__ = "proxies"

    url: Mapped[str] = mapped_column(String(512), nullable=False)
    protocol: Mapped[ProxyProtocol] = mapped_column(Enum(ProxyProtocol), default=ProxyProtocol.http)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    accounts: Mapped[list["Account"]] = relationship(back_populates="proxy")


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_enc: Mapped[str] = mapped_column(String(1024), nullable=False)
    proxy_id: Mapped[int | None] = mapped_column(ForeignKey("proxies.id"), nullable=True)
    status: Mapped[AccountStatus] = mapped_column(Enum(AccountStatus), default=AccountStatus.active)
    session_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_login: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_post: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posts_today: Mapped[int] = mapped_column(Integer, default=0)
    max_daily_posts: Mapped[int] = mapped_column(Integer, default=3)
    cooldown_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_posts: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_likes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    proxy: Mapped[Proxy | None] = relationship(back_populates="accounts")
    posts: Mapped[list["Post"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    bio_configs: Mapped[list["BioConfig"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
```

### `backend/app/models/base.py`

میکسین `id` و `created_at` و `updated_at` که همه مدل‌ها از آن ارث می‌برند.

```python
"""Shared columns: id / created_at / updated_at."""
import datetime as dt

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### `backend/app/models/content.py`

مدل‌های قانون زمان‌بندی، قالب کپشن، مجموعه هشتگ، بایو (با `link_url` برای لینک بات خارجی)، افکت، لاگ سیستمی و تنظیمات. مدل `TelegramConfig` حذف شده است.

```python
"""Schedule rules, captions, hashtags, bios, effects, logs, settings."""
import datetime as dt

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base
from app.models.base import TimestampMixin


class ScheduleRule(Base, TimestampMixin):
    __tablename__ = "schedule_rules"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, default=-1)  # -1 = every day
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_effect: Mapped[str | None] = mapped_column(String(128), nullable=True)
    caption_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("caption_templates.id"), nullable=True
    )


class CaptionTemplate(Base, TimestampMixin):
    __tablename__ = "caption_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class HashtagSet(Base, TimestampMixin):
    __tablename__ = "hashtag_sets"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)


class BioConfig(Base, TimestampMixin):
    __tablename__ = "bio_configs"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_applied: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotation_interval_days: Mapped[int] = mapped_column(Integer, default=14)

    account: Mapped["Account"] = relationship(back_populates="bio_configs")


class EffectPreset(Base, TimestampMixin):
    __tablename__ = "effect_presets"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    ffmpeg_filter: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_engagement: Mapped[float | None] = mapped_column(Float, nullable=True)


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    level: Mapped[LogLevel] = mapped_column(SQLEnum(LogLevel), default=LogLevel.INFO)
    category: Mapped[str] = mapped_column(String(64), default="system", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, index=True
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )
```

### `backend/app/models/video.py`

مدل ویدیو (مسیر فایل‌ها، هش، وضعیت، تنظیمات پردازش هر ویدیو) و مدل پست (کپشن، هشتگ، وضعیت، زمان‌بندی، اسنپ‌شات‌های تحلیلی ۱/۶/۲۴/۴۸ ساعته و ۷ روزه).

```python
"""Video + Post models."""
import datetime as dt
import enum

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class VideoStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    posting = "posting"
    posted = "posted"
    failed = "failed"
    archived = "archived"


class PostStatus(str, enum.Enum):
    scheduled = "scheduled"
    posting = "posting"
    posted = "posted"
    failed = "failed"
    deleted = "deleted"
    shadowbanned_check = "shadowbanned_check"


class Video(Base, TimestampMixin):
    __tablename__ = "videos"

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    processed_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    md5_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus), default=VideoStatus.uploaded)
    upload_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    effect_preset: Mapped[str | None] = mapped_column(String(128), nullable=True)
    custom_filters: Mapped[str | None] = mapped_column(Text, nullable=True)
    trim_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    trim_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    add_watermark: Mapped[bool] = mapped_column(Boolean, default=True)

    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    post: Mapped["Post | None"] = relationship(back_populates="video", uselist=False)


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    ig_media_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ig_permalink: Mapped[str | None] = mapped_column(String(512), nullable=True)
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.scheduled)
    scheduled_for: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    views_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_6h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_48h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_analytics_check: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    video: Mapped[Video] = relationship(back_populates="post")
    account: Mapped["Account"] = relationship(back_populates="posts")
```

### `backend/app/schemas/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python
from app.schemas.account import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    ProxyCreate,
    ProxyOut,
    ProxyUpdate,
)
from app.schemas.auth import LoginIn, MeOut, RefreshIn, TokenOut
from app.schemas.content import (
    BioIn,
    BioOut,
    CaptionIn,
    CaptionOut,
    EffectIn,
    EffectOut,
    HashtagSetIn,
    HashtagSetOut,
    LogOut,
    ScheduleRuleIn,
    ScheduleRuleOut,
    SettingOut,
)
from app.schemas.video import PostOut, SchedulePostIn, VideoOut, VideoSettingsUpdate

__all__ = [
    "AccountCreate", "AccountOut", "AccountUpdate", "ProxyCreate", "ProxyOut", "ProxyUpdate",
    "LoginIn", "MeOut", "RefreshIn", "TokenOut",
    "BioIn", "BioOut", "CaptionIn", "CaptionOut", "EffectIn", "EffectOut",
    "HashtagSetIn", "HashtagSetOut", "LogOut", "ScheduleRuleIn", "ScheduleRuleOut",
    "SettingOut", "PostOut", "SchedulePostIn", "VideoOut", "VideoSettingsUpdate",
]
```

### `backend/app/schemas/account.py`

اسکیماهای اعتبارسنجی ورود/خروجی اکانت و پروکسی.

```python
"""Pydantic schemas shared across resources."""
import datetime as dt

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1)
    proxy_id: int | None = None
    max_daily_posts: int = Field(default=3, ge=1, le=20)
    notes: str | None = None


class AccountUpdate(BaseModel):
    max_daily_posts: int | None = Field(default=None, ge=1, le=20)
    notes: str | None = None
    status: str | None = None
    proxy_id: int | None = None


class AccountOut(BaseModel):
    id: int
    username: str
    proxy_id: int | None
    status: str
    last_login: dt.datetime | None
    last_post: dt.datetime | None
    posts_today: int
    max_daily_posts: int
    cooldown_until: dt.datetime | None
    total_posts: int
    total_views: int
    total_likes: int
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ProxyCreate(BaseModel):
    url: str
    protocol: str = "http"
    username: str | None = None
    password: str | None = None
    country: str | None = None


class ProxyUpdate(BaseModel):
    url: str | None = None
    protocol: str | None = None
    username: str | None = None
    password: str | None = None
    country: str | None = None
    is_active: bool | None = None


class ProxyOut(BaseModel):
    id: int
    url: str
    protocol: str
    username: str | None
    country: str | None
    is_healthy: bool
    last_checked: dt.datetime | None
    fail_count: int
    latency_ms: int | None
    is_active: bool
    created_at: dt.datetime
```

### `backend/app/schemas/auth.py`

اسکیماهای لاگین، جفت توکن، تمدید و مشخصات کاربر.

```python
from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    username: str
```

### `backend/app/schemas/content.py`

اسکیماهای قوانین زمان‌بندی، کپشن، هشتگ، بایو، افکت، تنظیمات و لاگ. اسکیماهای `TelegramIn/Out` حذف شده‌اند.

```python
import datetime as dt

from pydantic import BaseModel, Field


class ScheduleRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    day_of_week: int = Field(default=-1, ge=-1, le=6)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    account_id: int | None = None
    is_active: bool = True
    preferred_effect: str | None = None
    caption_template_id: int | None = None


class ScheduleRuleOut(ScheduleRuleIn):
    id: int
    created_at: dt.datetime


class CaptionIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    category: str | None = None
    is_active: bool = True


class CaptionOut(CaptionIn):
    id: int
    use_count: int
    avg_engagement: float | None


class HashtagSetIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tags: str = Field(min_length=1)
    is_active: bool = True


class HashtagSetOut(HashtagSetIn):
    id: int
    use_count: int


class BioIn(BaseModel):
    account_id: int
    text: str = Field(min_length=1)
    link_url: str = ""
    is_active: bool = True
    rotation_interval_days: int = Field(default=14, ge=1, le=365)


class BioOut(BioIn):
    id: int
    last_applied: dt.datetime | None


class EffectIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    ffmpeg_filter: str = ""
    is_active: bool = True


class EffectOut(EffectIn):
    id: int
    use_count: int
    avg_engagement: float | None


class SettingOut(BaseModel):
    key: str
    value: str
    category: str
    is_sensitive: bool


class LogOut(BaseModel):
    id: int
    level: str
    category: str
    message: str
    details: dict | None
    timestamp: dt.datetime
```

### `backend/app/schemas/video.py`

اسکیماهای خروجی ویدیو و پست، به‌روزرسانی تنظیمات ویدیو و زمان‌بندی دستی پست.

```python
import datetime as dt

from pydantic import BaseModel, Field


class VideoOut(BaseModel):
    id: int
    original_filename: str
    duration: float | None
    file_size: int | None
    status: str
    effect_preset: str | None
    add_watermark: bool
    trim_start: float | None
    trim_end: float | None
    failed_reason: str | None
    processed_at: dt.datetime | None
    thumbnail_path: str | None
    created_at: dt.datetime


class VideoSettingsUpdate(BaseModel):
    effect_preset: str | None = None
    custom_filters: str | None = None
    trim_start: float | None = None
    trim_end: float | None = None
    add_watermark: bool | None = None


class PostOut(BaseModel):
    id: int
    video_id: int
    account_id: int
    ig_media_id: str | None
    ig_permalink: str | None
    caption: str
    hashtags: str
    status: str
    scheduled_for: dt.datetime | None
    posted_at: dt.datetime | None
    views_24h: int | None
    views_7d: int | None
    likes_24h: int | None
    engagement_rate: float | None
    fail_reason: str | None
    retry_count: int
    created_at: dt.datetime


class SchedulePostIn(BaseModel):
    video_id: int
    account_id: int | None = None
    scheduled_for: dt.datetime | None = None
    caption: str = ""
    hashtags: str = ""
```

### `backend/app/services/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/services/analytics_service.py`

کوئری‌های تجمیعی آمار: نمای کلی داشبورد، نمودار بازدید در طول زمان، مقایسه اکانت‌ها و عملکرد بازه‌های زمانی.

```python
"""Analytics aggregation queries."""
import datetime as dt

from sqlalchemy import func, select

from app.models import Account, Post, PostStatus, Video


async def overview(session, since: dt.datetime | None = None) -> dict:
    post_q = select(func.count(Post.id), func.coalesce(func.sum(Post.views_7d), 0)).where(
        Post.status == PostStatus.posted
    )
    if since:
        post_q = post_q.where(Post.posted_at >= since)
    total_posts, total_views = (await session.execute(post_q)).one()

    eng_q = select(func.avg(Post.engagement_rate)).where(
        Post.status == PostStatus.posted, Post.engagement_rate.is_not(None)
    )
    if since:
        eng_q = eng_q.where(Post.posted_at >= since)
    avg_eng = (await session.execute(eng_q)).scalar() or 0.0

    active_accounts = (
        await session.execute(select(func.count(Account.id)).where(Account.status == "active"))
    ).scalar() or 0
    queue = (
        await session.execute(select(func.count(Video.id)).where(Video.status.in_(["uploaded", "processing", "processed"])))
    ).scalar() or 0
    scheduled = (
        await session.execute(select(func.count(Post.id)).where(Post.status == PostStatus.scheduled))
    ).scalar() or 0
    return {
        "total_posts": total_posts,
        "total_views": int(total_views or 0),
        "avg_engagement_rate": round(float(avg_eng), 2),
        "active_accounts": active_accounts,
        "queue_size": queue,
        "scheduled_count": scheduled,
    }


async def views_over_time(session, days: int = 30) -> list[dict]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (
        await session.execute(
            select(
                func.date(Post.posted_at).label("day"),
                func.count(Post.id),
                func.coalesce(func.sum(Post.views_7d), 0),
            )
            .where(Post.status == PostStatus.posted, Post.posted_at >= since)
            .group_by(func.date(Post.posted_at))
            .order_by(func.date(Post.posted_at))
        )
    ).all()
    return [{"date": str(r[0]), "posts": r[1], "views": int(r[2] or 0)} for r in rows]


async def account_comparison(session) -> list[dict]:
    rows = (
        await session.execute(
            select(
                Account.username,
                func.count(Post.id),
                func.coalesce(func.sum(Post.views_7d), 0),
                func.avg(Post.engagement_rate),
            )
            .outer_join(Post, (Post.account_id == Account.id) & (Post.status == PostStatus.posted))
            .group_by(Account.id, Account.username)
            .order_by(func.coalesce(func.sum(Post.views_7d), 0).desc())
        )
    ).all()
    return [
        {"username": r[0], "posts": r[1], "views": int(r[2] or 0), "avg_engagement": round(float(r[3] or 0), 2)}
        for r in rows
    ]


async def time_slot_performance(session) -> list[dict]:
    """Avg views by weekday × hour of posting."""
    rows = (
        await session.execute(
            select(
                func.extract("dow", Post.posted_at).label("dow"),
                func.extract("hour", Post.posted_at).label("hour"),
                func.count(Post.id),
                func.avg(Post.views_7d),
            )
            .where(Post.status == PostStatus.posted, Post.posted_at.is_not(None))
            .group_by("dow", "hour")
        )
    ).all()
    return [
        {"dow": int(r[0] or 0), "hour": int(r[1] or 0), "posts": r[2], "avg_views": int(r[3] or 0)}
        for r in rows
    ]
```

### `backend/app/services/instagram_service.py`

پوشش instagrapi: لاگین با استفاده مجدد از سشن، آپلود ریلز، ویرایش بایو و خواندن آمار مدیا؛ به‌علاوه دسته‌بندی خطا (چالش، محدودیت نرخ، نیاز به لاگین) و اثر انگشت ثابت دستگاه برای هر اکانت.

```python
"""instagrapi wrapper: login w/ session reuse, reel upload, bio edit, media info."""
import asyncio
import logging
import random
import time

log = logging.getLogger("igfunnel.instagram")

CHALLENGE_MARKERS = ("challenge_required", "checkpoint_required", "feedback_required")
THROTTLE_MARKERS = ("throttled", "slow down", "try again later", "rate limit")


def _classify(exc: Exception) -> str:
    msg = f"{type(exc).__name__}: {exc}".lower()
    if any(m in msg for m in CHALLENGE_MARKERS):
        return "challenge"
    if "login_required" in msg or "login required" in msg:
        return "login_required"
    if any(m in msg for m in THROTTLE_MARKERS):
        return "throttled"
    return "generic"


class InstagramService:
    def __init__(self, proxy_url: str | None = None, session_path: str | None = None):
        self.proxy_url = proxy_url
        self.session_path = session_path

    def _make_client(self, username: str):
        from instagrapi import Client
        from app.utils.instagram_helpers import device_settings_for

        cl = Client()
        cl.set_device(device_settings_for(username))
        cl.delay_range = [1, 3]
        if self.proxy_url:
            cl.set_proxy(self.proxy_url)
        if self.session_path:
            try:
                cl.load_settings(self.session_path)
            except Exception:
                log.info("No usable session file for %s", username)
        return cl

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Blocking (run in thread). Returns (ok, detail)."""
        import os

        cl = self._make_client(username)
        try:
            if self.session_path and os.path.exists(self.session_path):
                try:
                    cl.get_timeline_feed()  # cheap session validity check
                    log.info("Reused session for %s", username)
                    return True, "session_reused"
                except Exception:
                    log.info("Stored session invalid for %s — logging in fresh", username)
            cl.login(username, password)
            if self.session_path:
                cl.dump_settings(self.session_path)
            return True, "logged_in"
        except Exception as exc:
            kind = _classify(exc)
            log.warning("Login failed for %s (%s): %s", username, kind, exc)
            return False, f"{kind}: {exc}"

    def check_session(self, username: str) -> bool:
        cl = self._make_client(username)
        try:
            cl.get_timeline_feed()
            return True
        except Exception:
            return False

    def upload_reel(self, username: str, password: str, video_path: str, caption: str) -> tuple[str | None, str | None, str]:
        """Blocking. Returns (media_id, permalink, error)."""
        cl = self._make_client(username)
        try:
            try:
                cl.get_timeline_feed()
            except Exception:
                cl.login(username, password)
                if self.session_path:
                    try:
                        cl.dump_settings(self.session_path)
                    except Exception:
                        pass
            # Random pre-post delay is applied by the caller (needs async sleep).
            media = cl.clip_upload(video_path, caption=caption)
            media_id = str(getattr(media, "id", "") or getattr(media, "pk", ""))
            code = getattr(media, "code", None)
            permalink = f"https://www.instagram.com/reel/{code}/" if code else None
            return media_id or None, permalink, ""
        except Exception as exc:
            kind = _classify(exc)
            return None, None, f"{kind}: {exc}"

    def apply_bio(self, username: str, password: str, biography: str, external_url: str) -> str:
        cl = self._make_client(username)
        try:
            try:
                cl.get_timeline_feed()
            except Exception:
                cl.login(username, password)
            cl.account_edit(biography=biography, external_url=external_url or "")
            if self.session_path:
                try:
                    cl.dump_settings(self.session_path)
                except Exception:
                    pass
            return ""
        except Exception as exc:
            return f"{_classify(exc)}: {exc}"

    def media_info(self, username: str, media_id: str) -> dict:
        cl = self._make_client(username)
        try:
            info = cl.media_info(media_id).dict()
            return {
                "like_count": info.get("like_count", 0),
                "comment_count": info.get("comment_count", 0),
                "view_count": info.get("view_count") or info.get("play_count") or 0,
            }
        except Exception as exc:
            log.warning("media_info failed for %s: %s", media_id, exc)
            return {}


async def random_pre_post_delay(min_s: int, max_s: int) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


def classify_error(exc: Exception) -> str:
    return _classify(exc)
```

### `backend/app/services/log_service.py`

ثبت رویداد در جدول لاگ (و لاگ استاندارد)؛ خطا در ذخیره لاگ هرگز مسیر اصلی را خراب نمی‌کند.

```python
"""DB-backed audit log helper (also mirrors to stdlib logging)."""
import logging
from typing import Any

from app.database import SessionLocal
from app.models import LogLevel, SystemLog

log = logging.getLogger("igfunnel")


async def log_event(level: str, category: str, message: str, details: dict[str, Any] | None = None) -> None:
    try:
        lvl = LogLevel[level.upper()]
    except KeyError:
        lvl = LogLevel.INFO
    getattr(log, lvl.name.lower(), log.info)("[%s] %s", category, message)
    try:
        async with SessionLocal() as session:
            session.add(SystemLog(level=lvl, category=category, message=message, details=details))
            await session.commit()
    except Exception:
        log.exception("Failed to persist system log")
```

### `backend/app/services/proxy_service.py`

ساخت URL پروکسی با احراز هویت و بررسی سلامت در دو نسخه آسنکرون (`check_proxy`) و سینک (`check_proxy_sync` با سوکت بلاکینگ برای سلری).

```python
"""Proxy helpers: URL building + health checks (async + sync variants)."""
import logging
import socket
import time

from app.core.security import decrypt_secret

log = logging.getLogger("igfunnel.proxy")


def proxy_url_for(proxy) -> str | None:
    if proxy is None:
        return None
    base = proxy.url
    if proxy.username:
        pwd = decrypt_secret(proxy.password_enc) or ""
        scheme, _, rest = base.partition("://")
        auth = proxy.username + (f":{pwd}" if pwd else "")
        return f"{scheme}://{auth}@{rest}"
    return base


def check_proxy_sync(proxy) -> tuple[bool, int | None]:
    """Blocking TCP-connect check (Celery-safe). Returns (healthy, latency_ms)."""
    from urllib.parse import urlparse

    url = proxy_url_for(proxy) or proxy.url
    try:
        parts = urlparse(url if "://" in url else f"http://{url}")
        host, port = parts.hostname, parts.port or 80
        if not host:
            return False, None
        start = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        return True, int((time.perf_counter() - start) * 1000)
    except Exception as exc:
        log.info("Proxy %s unhealthy: %s", proxy.id, exc)
        return False, None


async def check_proxy(proxy) -> tuple[bool, int | None]:
    """TCP-connect check. Returns (healthy, latency_ms)."""
    import asyncio
    from urllib.parse import urlparse

    url = proxy_url_for(proxy) or proxy.url
    try:
        parts = urlparse(url if "://" in url else f"http://{url}")
        host, port = parts.hostname, parts.port or 80
        if not host:
            return False, None
        start = time.perf_counter()
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, int((time.perf_counter() - start) * 1000)
    except Exception as exc:
        log.info("Proxy %s unhealthy: %s", proxy.id, exc)
        return False, None
```

### `backend/app/services/realtime.py`

انتشار رویداد بلادرنگ روی کانال ردیس و ذخیره/خواندن درصد پیشرفت پردازش ویدیو (نسخه آسنکرون برای API).

```python
"""Tiny Redis-backed pub/sub for realtime dashboard updates + progress tracking."""
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_channel = "igfunnel:events"


def _client() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def publish(event: str, payload: dict[str, Any]) -> None:
    try:
        client = _client()
        try:
            await client.publish(_channel, json.dumps({"event": event, **payload}))
        finally:
            await client.aclose()
    except Exception:
        pass  # realtime is best-effort; never break the request path


async def set_progress(video_id: int, percentage: float, stage: str) -> None:
    try:
        client = _client()
        try:
            await client.set(f"igfunnel:progress:{video_id}", json.dumps({"percentage": percentage, "stage": stage}), ex=3600)
        finally:
            await client.aclose()
        await publish("video_processing_progress", {"video_id": video_id, "percentage": percentage, "stage": stage})
    except Exception:
        pass


async def get_progress(video_id: int) -> dict[str, Any] | None:
    try:
        client = _client()
        try:
            raw = await client.get(f"igfunnel:progress:{video_id}")
        finally:
            await client.aclose()
        return json.loads(raw) if raw else None
    except Exception:
        return None
```

### `backend/app/services/scheduler_service.py`

منطق زمان‌بند نسخه آسنکرون برای API وب (قوانین سررسیده، اکانت واجد شرایط، ویدیو، جلوگیری از تکراری، کپشن و هشتگ چرخشی).

```python
"""Scheduler helpers: due-rule detection + eligible-account/video selection."""
import datetime as dt
import random

from sqlalchemy import func, select

from app.models import Account, AccountStatus, Post, PostStatus, ScheduleRule, Video, VideoStatus


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def due_rules(session, at: dt.datetime | None = None) -> list[ScheduleRule]:
    """Rules whose (day/hour/minute) match the current minute and are active."""
    at = at or _now()
    q = select(ScheduleRule).where(
        ScheduleRule.is_active.is_(True),
        ((ScheduleRule.day_of_week == -1) | (ScheduleRule.day_of_week == at.weekday())),
        ScheduleRule.hour == at.hour,
        ScheduleRule.minute == at.minute,
    )
    return list((await session.execute(q)).scalars().all())


async def eligible_account(session, account_id: int | None = None) -> Account | None:
    now = _now()
    if account_id:
        acc = await session.get(Account, account_id)
        if acc and acc.status == AccountStatus.active and acc.posts_today < acc.max_daily_posts:
            if not acc.cooldown_until or acc.cooldown_until <= now:
                return acc
        return None
    q = (
        select(Account)
        .where(
            Account.status == AccountStatus.active,
            Account.posts_today < Account.max_daily_posts,
            ((Account.cooldown_until.is_(None)) | (Account.cooldown_until <= now)),
            ((Account.last_post.is_(None)) | (Account.last_post <= now - dt.timedelta(hours=2))),
        )
        .order_by(Account.last_post.asc().nulls_first())
    )
    return (await session.execute(q)).scalars().first()


async def next_video(session, effect: str | None = None) -> Video | None:
    q = select(Video).where(Video.status == VideoStatus.processed).order_by(Video.created_at.asc())
    video = (await session.execute(q)).scalars().first()
    return video


async def already_scheduled(session, rule: ScheduleRule, window_min: int = 10) -> bool:
    """Avoid double-scheduling when beat fires twice in the same window."""
    now = _now()
    q = select(func.count(Post.id)).where(
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
        (Post.account_id == rule.account_id) if rule.account_id else True,
    )
    return ((await session.execute(q)).scalar() or 0) > 0


async def pick_caption(session, template_id: int | None) -> tuple[str, int | None]:
    from app.models import CaptionTemplate

    if template_id:
        t = await session.get(CaptionTemplate, template_id)
        if t and t.is_active:
            return t.content, t.id
    rows = (await session.execute(select(CaptionTemplate).where(CaptionTemplate.is_active.is_(True)))).scalars().all()
    if not rows:
        return "", None
    weights = [1.0 / (1.0 + (r.use_count or 0)) for r in rows]
    chosen = random.choices(rows, weights=weights, k=1)[0]
    return chosen.content, chosen.id


async def pick_hashtags(session, last_tags: str = "") -> str:
    from app.models import HashtagSet

    rows = (
        await session.execute(select(HashtagSet).where(HashtagSet.is_active.is_(True)))
    ).scalars().all()
    rows = [r for r in rows if r.tags.strip() and r.tags.strip() != last_tags.strip()]
    if not rows:
        return ""
    chosen = random.choice(rows)
    tags = [t.strip() for t in chosen.tags.replace("\n", ",").split(",") if t.strip()]
    chosen.use_count += 1
    selected = random.sample(tags, k=min(len(tags), random.randint(3, 5)))
    return " ".join(t if t.startswith("#") else f"#{t}" for t in selected)
```

### `backend/app/services/video_processor.py`

ارکستر پایپ‌لاین در دو نسخه: آسنکرون (`process_video`) برای API و کاملاً سینک (`process_video_sync`) برای سلری با `probe_sync` و `run_sync_with_progress` و `extract_thumbnail_sync`.

```python
"""FFmpeg processing pipeline orchestrator.

Async variant (web API) + fully synchronous variant (Celery workers).
Celery must ONLY use process_video_sync — it never touches an event loop.
"""
import hashlib
import logging
import os
import subprocess
import uuid

from app.config import settings
from app.utils import ffmpeg as ff

log = logging.getLogger("igfunnel.video")


def media_dirs() -> dict[str, str]:
    root = settings.MEDIA_ROOT
    dirs = {
        "raw": os.path.join(root, "raw"),
        "processed": os.path.join(root, "processed"),
        "thumbnails": os.path.join(root, "thumbnails"),
        "watermarks": os.path.join(root, "watermarks"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_watermark() -> str | None:
    p = os.path.join(media_dirs()["watermarks"], "watermark.png")
    return p if os.path.exists(p) else None


async def extract_thumbnail(src: str, duration: float, dst: str) -> None:
    import asyncio

    at = max(0.1, duration * 0.25)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", "-q:v", "3", dst,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()


def extract_thumbnail_sync(src: str, duration: float, dst: str) -> None:
    """Blocking thumbnail extraction (Celery-safe)."""
    at = max(0.1, duration * 0.25)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", "-q:v", "3", dst],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )


def process_video_sync(video_id: int, effect_filter: str = "", color_grade: str = "") -> str:
    """Run the full pipeline synchronously. Returns processed_path. Raises on failure."""
    import datetime as dt

    from app.database import SyncSessionLocal
    from app.models import Video, VideoStatus
    from app.tasks.sync_helpers import log_event_sync, set_progress_sync

    with SyncSessionLocal() as s:
        video = s.get(Video, video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")
        raw_path = video.raw_path
        trim_start, trim_end = video.trim_start, video.trim_end
        effect_preset = video.effect_preset
        custom_filters = video.custom_filters
        add_watermark = video.add_watermark
        video.status = VideoStatus.processing
        s.commit()

    dirs = media_dirs()
    set_progress_sync(video_id, 2, "probing")
    info = ff.probe_sync(raw_path)
    if info["duration"] < 3:
        raise ValueError(f"Video too short ({info['duration']:.1f}s < 3s)")
    set_progress_sync(video_id, 8, "validated")

    out_name = f"{uuid.uuid4().hex}.mp4"
    dst = os.path.join(dirs["processed"], out_name)
    watermark = default_watermark() if add_watermark else None
    cmd = ff.build_command(
        raw_path, dst,
        trim_start=trim_start, trim_end=trim_end,
        effect_filter=effect_filter or (effect_preset or ""),
        custom_filters=custom_filters or "",
        color_grade=color_grade,
        watermark_path=watermark,
        has_audio=info["has_audio"],
    )

    def on_progress(pct: float, stage: str):
        set_progress_sync(video_id, 8 + pct * 0.85, stage)

    ff.run_sync_with_progress(cmd, info["duration"], on_progress)

    thumb_name = f"{uuid.uuid4().hex}.jpg"
    thumb_path = os.path.join(dirs["thumbnails"], thumb_name)
    try:
        extract_thumbnail_sync(dst, info["duration"], thumb_path)
    except Exception:
        log.warning("Thumbnail extraction failed for video %s", video_id)
        thumb_path = None

    digest = md5_of_file(dst)
    with SyncSessionLocal() as s:
        video = s.get(Video, video_id)
        if video:
            video.processed_path = dst
            video.thumbnail_path = thumb_path
            video.duration = info["duration"]
            video.file_size = os.path.getsize(dst)
            video.processed_at = dt.datetime.now(dt.timezone.utc)
            video.status = VideoStatus.processed
            s.commit()
    log_event_sync("INFO", "video", f"Video {video_id} processed", {"md5": digest})
    set_progress_sync(video_id, 100, "done")
    return dst


async def process_video(
    video_id: int,
    get_video,   # async callable returning a DB-attached Video
    save_video,  # async callable persisting changes
    effect_filter: str = "",
    color_grade: str = "",
) -> str:
    """Async pipeline (web API use). Celery workers must use process_video_sync."""
    from app.services import realtime

    video = await get_video(video_id)
    dirs = media_dirs()
    await realtime.set_progress(video_id, 2, "probing")
    info = await ff.probe(video.raw_path)
    if info["duration"] < 3:
        raise ValueError(f"Video too short ({info['duration']:.1f}s < 3s)")
    await realtime.set_progress(video_id, 8, "validated")

    out_name = f"{uuid.uuid4().hex}.mp4"
    dst = os.path.join(dirs["processed"], out_name)
    watermark = default_watermark() if video.add_watermark else None
    cmd = ff.build_command(
        video.raw_path, dst,
        trim_start=video.trim_start, trim_end=video.trim_end,
        effect_filter=effect_filter or (video.effect_preset or ""),
        custom_filters=video.custom_filters or "",
        color_grade=color_grade,
        watermark_path=watermark,
        has_audio=info["has_audio"],
    )

    async def on_progress(pct: float, stage: str):
        await realtime.set_progress(video_id, 8 + pct * 0.85, stage)

    await ff.run_with_progress(cmd, info["duration"], on_progress)

    thumb_name = f"{uuid.uuid4().hex}.jpg"
    thumb_path = os.path.join(dirs["thumbnails"], thumb_name)
    try:
        await extract_thumbnail(dst, info["duration"], thumb_path)
    except Exception:
        log.warning("Thumbnail extraction failed for video %s", video_id)
        thumb_path = None

    digest = md5_of_file(dst)
    await save_video(video_id, {
        "processed_path": dst,
        "thumbnail_path": thumb_path,
        "duration": info["duration"],
        "file_size": os.path.getsize(dst),
        "md5_hash_processed": digest,
        "processed_at": True,
    })
    await realtime.set_progress(video_id, 100, "done")
    return dst
```

### `backend/app/tasks/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/tasks/celery_app.py`

نمونه سلری (بروکر و بک‌اند ردیس، صف‌های جدا برای ویدیو و پست) و برنامه Celery Beat با ۶ تسک دوره‌ای (بدون `daily-summary`).

```python
"""Celery app + beat schedule (all periodic tasks defined here)."""
import os

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("igfunnel", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "tasks.video_tasks.*": {"queue": "video"},
        "tasks.post_tasks.*": {"queue": "posts"},
    },
)
celery.autodiscover_tasks(["app.tasks"])

celery.conf.beat_schedule = {
    "check-scheduled-posts": {"task": "tasks.post_tasks.check_and_post", "schedule": crontab(minute="*")},
    "fetch-analytics": {"task": "tasks.analytics_tasks.fetch_all_analytics", "schedule": crontab(hour="*/4")},
    "check-bio-rotation": {"task": "tasks.bio_tasks.check_bio_rotation", "schedule": crontab(hour=6, minute=0)},
    "proxy-health-check": {"task": "tasks.proxy_tasks.check_all_proxies", "schedule": crontab(minute="*/30")},
    "media-cleanup": {"task": "tasks.cleanup_tasks.clean_old_media", "schedule": crontab(hour=4, minute=0)},
    "reset-daily-counts": {"task": "tasks.account_tasks.reset_daily_counts", "schedule": crontab(hour=0, minute=0)},
}
```

### `backend/app/tasks/periodic_tasks.py`

۵ تسک دوره‌ای سینک (آمار، چرخش بایو، سلامت پروکسی، پاک‌سازی، ریست شمارنده). تسک `send_daily_summary` حذف شده است.

```python
"""Periodic tasks â€” all fully synchronous (Celery-safe, no event loop)."""
import datetime as dt
import logging
import os

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks")


@celery.task(name="tasks.analytics_tasks.fetch_all_analytics")
def fetch_all_analytics():
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, Post, PostStatus, Proxy
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        with SyncSessionLocal() as s:
            posts = (
                s.execute(
                    select(Post).where(Post.status == PostStatus.posted, Post.posted_at >= cutoff)
                )
            ).scalars().all()
            items = [(p.id, p.account_id, p.ig_media_id, p.posted_at) for p in posts]
        updated = 0
        for pid, acc_id, media_id, posted_at in items:
            if not media_id:
                continue
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    proxy = s.get(Proxy, acc.proxy_id) if acc.proxy_id else None
                    username = acc.username
                    password = decrypt_secret(acc.password_enc)
                    purl = proxy_url_for(proxy) if proxy else None
                svc = InstagramService(
                    proxy_url=purl, session_path=session_path_for(username, settings.MEDIA_ROOT)
                )
                info = svc.media_info(username, media_id)
                likes = info.get("like_count", 0)
                comments = info.get("comment_count", 0)
                views = info.get("view_count", 0)
                age_h = max(
                    1,
                    (dt.datetime.now(dt.timezone.utc) - (posted_at or dt.datetime.now(dt.timezone.utc))).total_seconds() / 3600,
                )
                eng = round((likes + comments) / max(1, views) * 100, 2) if views else 0.0
                with SyncSessionLocal() as s:
                    p = s.get(Post, pid)
                    if p:
                        if age_h <= 1.5:
                            p.views_1h, p.likes_1h = views, likes
                        if age_h <= 8:
                            p.views_6h = views
                        if age_h <= 30:
                            p.views_24h, p.likes_24h, p.comments_24h = views, likes, comments
                        if age_h <= 54:
                            p.views_48h = views
                        p.views_7d, p.likes_7d, p.comments_7d = views, likes, comments
                        p.engagement_rate = eng
                        p.last_analytics_check = dt.datetime.now(dt.timezone.utc)
                        s.commit()
                        updated += 1
            except Exception:
                log.exception("analytics fetch failed for post %s", pid)
        log_event_sync("INFO", "system", f"Analytics refresh: {updated} posts updated")
        return {"updated": updated}
    except Exception:  # noqa: BLE001
        log.exception("fetch_all_analytics failed")
        return {"error": "failed"}


@celery.task(name="tasks.bio_tasks.check_bio_rotation")
def check_bio_rotation():
    from sqlalchemy import select

    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, BioConfig
    from app.services.instagram_service import InstagramService
    from app.tasks.sync_helpers import log_event_sync
    from app.utils.instagram_helpers import session_path_for

    try:
        now = dt.datetime.now(dt.timezone.utc)
        with SyncSessionLocal() as s:
            bios = s.execute(select(BioConfig).where(BioConfig.is_active.is_(True))).scalars().all()
            due = [b for b in bios if not b.last_applied or (now - b.last_applied).days >= b.rotation_interval_days]
            items = [(b.id, b.account_id, b.text, b.link_url) for b in due]
        applied = 0
        for bid, acc_id, text, link in items:
            try:
                with SyncSessionLocal() as s:
                    acc = s.get(Account, acc_id)
                    if not acc:
                        continue
                    username, password = acc.username, decrypt_secret(acc.password_enc)
                svc = InstagramService(session_path=session_path_for(username, settings.MEDIA_ROOT))
                err = svc.apply_bio(username, password, text, link or "")
                if not err:
                    with SyncSessionLocal() as s:
                        b = s.get(BioConfig, bid)
                        if b:
                            b.last_applied = now
                            s.commit()
                    applied += 1
                    log_event_sync("INFO", "account", f"Bio rotated for account {acc_id}")
            except Exception:
                log.exception("bio rotation failed for %s", bid)
        return {"due": len(items), "applied": applied}
    except Exception:  # noqa: BLE001
        log.exception("check_bio_rotation failed")
        return {"error": "failed"}


@celery.task(name="tasks.proxy_tasks.check_all_proxies")
def check_all_proxies():
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Proxy
    from app.services.proxy_service import check_proxy_sync
    from app.tasks.sync_helpers import log_event_sync

    try:
        with SyncSessionLocal() as s:
            proxies = s.execute(select(Proxy).where(Proxy.is_active.is_(True))).scalars().all()
            ids = [p.id for p in proxies]
        results = []
        for pid in ids:
            with SyncSessionLocal() as s:
                p = s.get(Proxy, pid)
                if not p:
                    continue
                ok, latency = check_proxy_sync(p)
                p.is_healthy = ok
                p.latency_ms = latency
                p.last_checked = dt.datetime.now(dt.timezone.utc)
                p.fail_count = 0 if ok else p.fail_count + 1
                s.commit()
                results.append({"id": pid, "healthy": ok})
        log_event_sync("INFO", "system", f"Proxy health check: {len(results)} checked")
        return results
    except Exception:  # noqa: BLE001
        log.exception("check_all_proxies failed")
        return {"error": "failed"}


@celery.task(name="tasks.cleanup_tasks.clean_old_media")
def clean_old_media(days: int = 30):
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Video, VideoStatus
    from app.tasks.sync_helpers import log_event_sync

    try:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        with SyncSessionLocal() as s:
            olds = (
                s.execute(
                    select(Video).where(Video.status == VideoStatus.posted, Video.processed_at < cutoff)
                )
            ).scalars().all()
            removed = 0
            for v in olds:
                for path in (v.raw_path, v.processed_path):
                    try:
                        if path and os.path.exists(path):
                            os.remove(path)
                            removed += 1
                    except OSError:
                        pass
                v.status = VideoStatus.archived
            s.commit()
        log_event_sync("INFO", "system", f"Media cleanup: {removed} files removed")
        return {"removed": removed}
    except Exception:  # noqa: BLE001
        log.exception("clean_old_media failed")
        return {"error": "failed"}


@celery.task(name="tasks.account_tasks.reset_daily_counts")
def reset_daily_counts():
    from sqlalchemy import update

    from app.database import SyncSessionLocal
    from app.models import Account
    from app.tasks.sync_helpers import log_event_sync

    try:
        with SyncSessionLocal() as s:
            s.execute(update(Account).values(posts_today=0))
            s.commit()
        log_event_sync("INFO", "system", "Daily post counts reset")
        return {"ok": True}
    except Exception:  # noqa: BLE001
        log.exception("reset_daily_counts failed")
        return {"error": "failed"}
```

### `backend/app/tasks/post_tasks.py`

تسک‌های `check_and_post` و `execute_post` کاملاً سینک: خواب بلاکینگ، فراخوانی مستقیم instagrapi، ثبت موفقیت/شکست فقط در لاگ دیتابیس (تابع `notify` تلگرام حذف شده است).

```python
"""Posting tasks: per-minute scheduler + single-post executor with retries.

Fully synchronous: no asyncio.run, no ThreadPoolExecutor, no event loop.
instagrapi calls are already blocking, so they run directly in the task.
"""
import datetime as dt
import logging
import random
import time

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks.post")


@celery.task(name="tasks.post_tasks.check_and_post", bind=True, max_retries=0)
def check_and_post(self):
    """Beat entry: create scheduled posts from due rules, then fire due posts."""
    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import Post, PostStatus
    from app.tasks import sync_helpers as sched

    try:
        with SyncSessionLocal() as s:
            rules = sched.due_rules(s)
            created = 0
            for rule in rules:
                if sched.already_scheduled(s, rule):
                    continue
                account = sched.eligible_account(s, rule.account_id)
                video = sched.next_video(s, rule.preferred_effect)
                if not account or not video:
                    continue
                caption, _ = sched.pick_caption(s, rule.caption_template_id)
                tags = sched.pick_hashtags(s)
                # Â±5 min jitter
                when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=random.randint(-5, 5))
                s.add(
                    Post(
                        video_id=video.id,
                        account_id=account.id,
                        caption=caption,
                        hashtags=tags,
                        status=PostStatus.scheduled,
                        scheduled_for=when,
                    )
                )
                created += 1
            s.commit()

            now = dt.datetime.now(dt.timezone.utc)
            due = (
                s.execute(
                    select(Post).where(Post.status == PostStatus.scheduled, Post.scheduled_for <= now)
                )
            ).scalars().all()
            due_ids = [p.id for p in due]
            rule_count = len(rules)
        for pid in due_ids:
            execute_post.delay(pid)
        return {"rules_matched": rule_count, "created": created, "fired": len(due_ids)}
    except Exception:  # noqa: BLE001
        log.exception("check_and_post failed")
        return {"error": "tick failed"}


@celery.task(name="tasks.post_tasks.execute_post", bind=True, max_retries=3)
def execute_post(self, post_id: int):
    from app.config import settings
    from app.core.security import decrypt_secret
    from app.database import SyncSessionLocal
    from app.models import Account, AccountStatus, Post, PostStatus, Proxy, Video, VideoStatus
    from app.services.instagram_service import InstagramService
    from app.services.proxy_service import proxy_url_for
    from app.tasks.sync_helpers import log_event_sync, publish_sync
    from app.utils.instagram_helpers import session_path_for

    def set_status(status: PostStatus, **fields):
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if not post:
                return
            post.status = status
            for k, v in fields.items():
                setattr(post, k, v)
            s.commit()
        publish_sync("post_status_update", {"post_id": post_id, "status": status.value})

    def touch_account(ok: bool, err: str = ""):
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            account = s.get(Account, post.account_id) if post else None
            if not account:
                return
            now = dt.datetime.now(dt.timezone.utc)
            if ok:
                account.last_post = now
                account.posts_today += 1
                account.total_posts += 1
            else:
                kind = err.split(":")[0]
                if kind == "challenge":
                    account.status = AccountStatus.challenge_required
                elif kind == "throttled":
                    account.status = AccountStatus.cooldown
                    account.cooldown_until = now + dt.timedelta(hours=24)
            s.commit()

    try:
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if not post:
                return {"post_id": post_id, "status": "missing"}
            account = s.get(Account, post.account_id)
            video = s.get(Video, post.video_id)
            proxy = s.get(Proxy, account.proxy_id) if account and account.proxy_id else None
            caption, tags, retries = post.caption, post.hashtags, post.retry_count
            username, password = account.username, decrypt_secret(account.password_enc)
            video_path = video.processed_path or video.raw_path
            proxy_url = proxy_url_for(proxy) if proxy else None

        set_status(PostStatus.posting)

        # Anti-detection pre-post delay (blocking sleep â€” task is sync).
        time.sleep(random.uniform(settings.IG_PRE_POST_DELAY_MIN, settings.IG_PRE_POST_DELAY_MAX))

        svc = InstagramService(proxy_url=proxy_url, session_path=session_path_for(username, settings.MEDIA_ROOT))
        full_caption = (caption + "\n" + tags).strip()
        media_id, permalink, error = svc.upload_reel(username, password, video_path, full_caption)

        if error:
            kind = error.split(":")[0]
            set_status(PostStatus.failed, fail_reason=error[:2000], retry_count=retries + 1)
            touch_account(False, error)
            log_event_sync("ERROR", "post", f"Post {post_id} to @{username} failed: {error}")
            if kind in ("throttled", "login_required") and retries < 3:
                raise self.retry(exc=RuntimeError(error), countdown=2 ** retries * 60)
            return {"post_id": post_id, "status": "failed", "error": error}

        set_status(
            PostStatus.posted,
            ig_media_id=media_id,
            ig_permalink=permalink,
            posted_at=dt.datetime.now(dt.timezone.utc),
        )
        touch_account(True)
        # Archive the video so it is never posted twice.
        with SyncSessionLocal() as s:
            post = s.get(Post, post_id)
            if post:
                v = s.get(Video, post.video_id)
                if v:
                    v.status = VideoStatus.posted
                s.commit()
        log_event_sync("INFO", "post", f"Posted to @{username}", {"post_id": post_id, "url": permalink})
        return {"post_id": post_id, "status": "posted", "url": permalink}
    except Exception as exc:  # noqa: BLE001
        log.exception("execute_post %s failed", post_id)
        try:
            set_status(PostStatus.failed, fail_reason=str(exc)[:2000])
        except Exception:
            pass
        return {"post_id": post_id, "status": "failed", "error": str(exc)}
```

### `backend/app/tasks/sync_helpers.py`

کمک‌های سینک سلری: انتشار بلادرنگ بلاکینگ (`publish_sync`/`set_progress_sync`)، ثبت لاگ سینک (`log_event_sync`) و نسخه سینک توابع زمان‌بند.

```python
"""Sync helpers for Celery tasks: blocking realtime pub/sub, sync logging, sync scheduler."""
import json
import logging
import random

import redis

from app.config import settings

_channel = "igfunnel:events"
log = logging.getLogger("igfunnel")


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def publish_sync(event: str, payload: dict) -> None:
    """Blocking publish (Celery-safe). Failures are swallowed — best effort."""
    try:
        client = _redis_client()
        try:
            client.publish(_channel, json.dumps({"event": event, **payload}))
        finally:
            client.close()
    except Exception:
        pass


def set_progress_sync(video_id: int, percentage: float, stage: str) -> None:
    try:
        client = _redis_client()
        try:
            client.set(
                f"igfunnel:progress:{video_id}",
                json.dumps({"percentage": percentage, "stage": stage}),
                ex=3600,
            )
        finally:
            client.close()
        publish_sync(
            "video_processing_progress",
            {"video_id": video_id, "percentage": percentage, "stage": stage},
        )
    except Exception:
        pass


def log_event_sync(level: str, category: str, message: str, details: dict | None = None) -> None:
    """Sync audit-log write for Celery tasks (commit included)."""
    from app.database import SyncSessionLocal
    from app.models import LogLevel, SystemLog

    try:
        lvl = LogLevel[level.upper()]
    except KeyError:
        lvl = LogLevel.INFO
    getattr(log, lvl.name.lower(), log.info)("[%s] %s", category, message)
    try:
        with SyncSessionLocal() as session:
            session.add(SystemLog(level=lvl, category=category, message=message, details=details))
            session.commit()
    except Exception:
        log.exception("Failed to persist system log")


# ---- Sync scheduler helpers (mirrors the async service used by the web API) ----

import datetime as dt

from sqlalchemy import func, select


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def due_rules(session, at: "dt.datetime | None" = None):
    from app.models import ScheduleRule

    at = at or _now()
    q = select(ScheduleRule).where(
        ScheduleRule.is_active.is_(True),
        ((ScheduleRule.day_of_week == -1) | (ScheduleRule.day_of_week == at.weekday())),
        ScheduleRule.hour == at.hour,
        ScheduleRule.minute == at.minute,
    )
    return list(session.execute(q).scalars().all())


def eligible_account(session, account_id: "int | None" = None):
    from app.models import Account, AccountStatus

    now = _now()
    if account_id:
        acc = session.get(Account, account_id)
        if acc and acc.status == AccountStatus.active and acc.posts_today < acc.max_daily_posts:
            if not acc.cooldown_until or acc.cooldown_until <= now:
                return acc
        return None
    q = (
        select(Account)
        .where(
            Account.status == AccountStatus.active,
            Account.posts_today < Account.max_daily_posts,
            ((Account.cooldown_until.is_(None)) | (Account.cooldown_until <= now)),
            ((Account.last_post.is_(None)) | (Account.last_post <= now - dt.timedelta(hours=2))),
        )
        .order_by(Account.last_post.asc().nulls_first())
    )
    return session.execute(q).scalars().first()


def next_video(session, effect: "str | None" = None):
    from app.models import Video, VideoStatus

    q = select(Video).where(Video.status == VideoStatus.processed).order_by(Video.created_at.asc())
    return session.execute(q).scalars().first()


def already_scheduled(session, rule, window_min: int = 10) -> bool:
    from app.models import Post, PostStatus

    now = _now()
    q = select(func.count(Post.id)).where(
        Post.status == PostStatus.scheduled,
        Post.scheduled_for >= now - dt.timedelta(minutes=window_min),
        Post.scheduled_for <= now + dt.timedelta(minutes=window_min),
        (Post.account_id == rule.account_id) if rule.account_id else True,
    )
    return (session.execute(q).scalar() or 0) > 0


def pick_caption(session, template_id: "int | None") -> "tuple[str, int | None]":
    from app.models import CaptionTemplate

    if template_id:
        t = session.get(CaptionTemplate, template_id)
        if t and t.is_active:
            return t.content, t.id
    rows = session.execute(select(CaptionTemplate).where(CaptionTemplate.is_active.is_(True))).scalars().all()
    if not rows:
        return "", None
    weights = [1.0 / (1.0 + (r.use_count or 0)) for r in rows]
    chosen = random.choices(rows, weights=weights, k=1)[0]
    return chosen.content, chosen.id


def pick_hashtags(session, last_tags: str = "") -> str:
    from app.models import HashtagSet

    rows = session.execute(select(HashtagSet).where(HashtagSet.is_active.is_(True))).scalars().all()
    rows = [r for r in rows if r.tags.strip() and r.tags.strip() != last_tags.strip()]
    if not rows:
        return ""
    chosen = random.choice(rows)
    tags = [t.strip() for t in chosen.tags.replace("\n", ",").split(",") if t.strip()]
    chosen.use_count += 1
    selected = random.sample(tags, k=min(len(tags), random.randint(3, 5)))
    return " ".join(t if t.startswith("#") else f"#{t}" for t in selected)
```

### `backend/app/tasks/video_tasks.py`

تسک پردازش کاملاً سینک: بدون asyncio، با `SyncSessionLocal` و `process_video_sync`؛ هیچ خطایی ورکر را از پا نمی‌اندازد.

```python
"""Video processing celery task — never crashes the worker.

Fully synchronous: no asyncio.run, no event loop. Uses SyncSessionLocal
and the sync FFmpeg pipeline.
"""
import logging
import random

from app.tasks.celery_app import celery

log = logging.getLogger("igfunnel.tasks.video")


@celery.task(name="tasks.video_tasks.process_video", bind=True, max_retries=2)
def process_video_task(self, video_id: int, effect_filter: str = "", color_grade: str = ""):
    import datetime as dt

    from sqlalchemy import select

    from app.database import SyncSessionLocal
    from app.models import EffectPreset, Video, VideoStatus
    from app.services.video_processor import process_video_sync
    from app.tasks.sync_helpers import log_event_sync, publish_sync

    def mark(status: VideoStatus, reason: str | None = None):
        with SyncSessionLocal() as s:
            v = s.get(Video, video_id)
            if v:
                v.status = status
                if reason is not None:
                    v.failed_reason = reason[:2000]
                s.commit()

    try:
        mark(VideoStatus.processing)
        if not effect_filter:
            with SyncSessionLocal() as s:
                presets = s.execute(
                    select(EffectPreset).where(EffectPreset.is_active.is_(True))
                ).scalars().all()
                if presets:
                    effect_filter = random.choice(presets).ffmpeg_filter or ""
        process_video_sync(video_id, effect_filter, color_grade)
        publish_sync("video_processing_complete", {"video_id": video_id, "status": "processed"})
        log_event_sync("INFO", "video", f"Video {video_id} processed successfully")
        return {"video_id": video_id, "status": "processed"}
    except Exception as exc:  # noqa: BLE001 — must never crash worker
        log.exception("process_video_task failed for %s", video_id)
        mark(VideoStatus.failed, str(exc))
        publish_sync("video_processing_complete", {"video_id": video_id, "status": "failed"})
        log_event_sync("ERROR", "video", f"Video {video_id} failed: {exc}")
        return {"video_id": video_id, "status": "failed", "error": str(exc)}
```

### `backend/app/utils/__init__.py`

فایل خالی که فقط برای تبدیل پوشه به پکیج پایتون لازم است.

```python

```

### `backend/app/utils/ffmpeg.py`

سازنده دستور FFmpeg + دو رانر: آسنکرون (`run_with_progress`) و سینک (`run_sync_with_progress` با `subprocess.Popen` و خواندن خط‌به‌خط stderr)؛ به‌علاوه `probe_sync` بلاکینگ.

```python
"""FFmpeg command builder + runner with progress parsing.

Both async (web API) and sync (Celery workers) runners are provided.
Celery must ONLY use the sync variants — never create an event loop in a task.
"""
import json
import logging
import os
import shlex
import subprocess

log = logging.getLogger("igfunnel.ffmpeg")

TARGET_W, TARGET_H = 720, 1280


def _parse_probe_json(raw: bytes) -> dict:
    info = json.loads(raw.decode() or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "has_audio": audio is not None,
    }


def probe_sync(path: str) -> dict:
    """Blocking ffprobe (Celery-safe)."""
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed — file is not a valid video")
    return _parse_probe_json(proc.stdout)


async def probe(path: str) -> dict:
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed — file is not a valid video")
    return _parse_probe_json(out)


def build_filter(
    effect_filter: str = "",
    custom_filters: str = "",
    color_grade: str = "",
    watermark_path: str | None = None,
    has_audio: bool = True,
) -> tuple[str, bool]:
    """Return (filter_complex, needs_watermark_input)."""
    parts: list[str] = []
    # Center-crop to 9:16 then scale to 720x1280.
    parts.append(
        "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H}"
    )
    if effect_filter.strip():
        parts.append(effect_filter.strip())
    if color_grade.strip():
        parts.append(color_grade.strip())
    if custom_filters.strip():
        parts.append(custom_filters.strip())
    parts.append("format=yuv420p")
    video_chain = ",".join(p for p in parts if p)
    if watermark_path:
        # [0:v]<chain>[v]; [1:v]scale=120:-1[wm]; [v][wm]overlay=W-w-20:20
        fc = (
            f"[0:v]{video_chain}[v];"
            f"[1:v]scale=120:-1[wm];"
            f"[v][wm]overlay=W-w-20:20[outv]"
        )
        return fc, True
    return f"[0:v]{video_chain}[outv]", False


def build_command(
    src: str,
    dst: str,
    trim_start: float | None = None,
    trim_end: float | None = None,
    effect_filter: str = "",
    custom_filters: str = "",
    color_grade: str = "",
    watermark_path: str | None = None,
    has_audio: bool = True,
) -> list[str]:
    filter_complex, needs_wm = build_filter(
        effect_filter, custom_filters, color_grade,
        watermark_path if watermark_path and os.path.exists(watermark_path) else None,
        has_audio,
    )
    cmd = ["ffmpeg", "-y"]
    if trim_start:
        cmd += ["-ss", str(trim_start)]
    if trim_end and trim_start is not None and trim_end > trim_start:
        cmd += ["-t", str(trim_end - trim_start)]
    elif trim_end:
        cmd += ["-t", str(trim_end)]
    cmd += ["-i", src]
    if needs_wm:
        cmd += ["-i", watermark_path]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-movflags", "+faststart",
    ]
    if has_audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k", "-af", "loudnorm"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:a", "aac"]
    cmd += [dst]
    log.info("FFmpeg: %s", " ".join(shlex.quote(c) for c in cmd))
    return cmd


def _parse_time_token(line: str, duration: float) -> float | None:
    if "time=" not in line or duration <= 0:
        return None
    try:
        t = line.split("time=")[1].split()[0]
        h, m, s = t.split(":")
        secs = int(h) * 3600 + int(m) * 60 + float(s)
        return max(0.0, min(100.0, secs / duration * 100))
    except Exception:
        return None


def run_sync_with_progress(cmd: list[str], duration: float, on_progress) -> None:
    """Blocking ffmpeg runner (Celery-safe). Reads stderr line by line via Popen."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace", bufsize=1
    )
    assert proc.stderr is not None
    stderr_tail: list[str] = []
    for line in proc.stderr:
        line = line.strip()
        if line:
            stderr_tail.append(line[-500:])
            pct = _parse_time_token(line, duration)
            if pct is not None:
                on_progress(pct, "processing")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("FFmpeg failed: " + " | ".join(stderr_tail[-8:]))


async def run_with_progress(cmd: list[str], duration: float, on_progress) -> None:
    """Run ffmpeg, parsing `time=` tokens from stderr to report 0-100%."""
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    assert proc.stderr is not None
    stderr_tail: list[str] = []
    async for raw in proc.stderr:
        line = raw.decode(errors="replace").strip()
        if line:
            stderr_tail.append(line[-500:])
            pct = _parse_time_token(line, duration)
            if pct is not None:
                await on_progress(pct, "processing")
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed: " + " | ".join(stderr_tail[-8:]))
```

### `backend/app/utils/instagram_helpers.py`

مسیر فایل سشن هر اکانت و اثر انگشت قطعی دستگاه بر اساس نام کاربری.

```python
"""Session persistence + anti-detection helpers for instagrapi."""
import logging
import os

log = logging.getLogger("igfunnel.instagram")


def session_path_for(username: str, media_root: str) -> str:
    d = os.path.join(media_root, "sessions")
    os.makedirs(d, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    return os.path.join(d, f"{safe}.json")


def device_settings_for(username: str) -> dict:
    """Deterministic per-account device fingerprint (stable across restarts)."""
    import hashlib

    h = hashlib.md5(username.encode()).hexdigest()
    return {
        "app_version": "302.0.0.34.111",
        "android_version": 28,
        "android_release": "9.0",
        "dpi": "420dpi",
        "resolution": "1080x1920",
        "manufacturer": "samsung",
        "device": f"starlte_{h[:4]}",
        "model": "SM-G960F",
        "cpu": "exynos9810",
        "version_code": "471750796",
        "uuid": h,
    }
```

### `backend/requirements.txt`

وابستگی‌های پایتون: فست‌ای‌پی، یوی‌کورن، SQLAlchemy، درایورهای asyncpg و aiosqlite، آلمبیک، سلری، ردیس، instagrapi، رمزنگاری، محدودسازی نرخ و aiofiles برای آپلود استریمینگ.

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
asyncpg==0.30.0
aiosqlite==0.20.0
alembic==1.14.0
celery[redis]==5.4.0
redis==5.2.1
instagrapi==2.1.3
python-telegram-bot==21.6
pydantic>=2.9
pydantic-settings==2.6.1
pyjwt==2.10.1
bcrypt==4.2.1
cryptography==43.0.3
slowapi==0.1.9
python-multipart==0.0.19
aiofiles==24.1.0
httpx==0.28.1
psutil==6.1.0
```

### `docker-compose.yml`

استک داکر با انکر مشترک `x-backend-env` (هر دو `DATABASE_URL` و `SYNC_DATABASE_URL`)، مونت `./data:/data` برای ماندگاری SQLite، ورکر با `--pool=solo` و پروفایل اختیاری `postgres`.

```yaml
version: "3.9"

x-backend-env: &backend-env
  DATABASE_URL: ${DATABASE_URL:-sqlite+aiosqlite:////data/app.db}
  SYNC_DATABASE_URL: ${SYNC_DATABASE_URL:-sqlite:////data/app.db}
  REDIS_URL: redis://redis:6379/0
  MEDIA_ROOT: /data/media

x-app-volumes: &app-volumes
  - appdata:/data
  - ./data:/data
  - ./media:/data/media

services:
  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-igfunnel}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      POSTGRES_DB: ${POSTGRES_DB:-igfunnel}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-igfunnel}"]
      interval: 10s
      timeout: 5s
      retries: 5
    profiles: ["postgres"]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    environment:
      <<: *backend-env
    volumes: *app-volumes
    depends_on:
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  worker:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    environment:
      <<: *backend-env
    volumes: *app-volumes
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app.celery worker --loglevel=info --concurrency=2 --pool=solo

  beat:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    environment:
      <<: *backend-env
    volumes: *app-volumes
    depends_on:
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app.celery beat --loglevel=info

  frontend:
    build: ./frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: ${FRONTEND_API_URL:-http://localhost:8000}
    depends_on:
      - backend

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "${NGINX_PORT:-8080}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./media:/srv/media:ro
    depends_on:
      - backend
      - frontend
    profiles: ["nginx"]

volumes:
  pgdata:
  redisdata:
  appdata:
```

### `frontend/Dockerfile`

بیلد چندمرحله‌ای فرانت (نصب، بیلد، اجرای standalone) روی پورت ۳۰۰۰.

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### `frontend/next.config.js`

تنظیم نکست با خروجی standalone و بازنویسی `/backend/*` به API برای محیط توسعه.

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${api}/:path*` }];
  },
};

module.exports = nextConfig;
```

### `frontend/package.json`

وابستگی‌های فرانت: نکست ۱۴، ری‌اکت ۱۸، TanStack Query، axios، zustand، recharts، lucide و tailwind.

```json
{
  "name": "ig-funnel-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "axios": "^1.7.7",
    "clsx": "^2.1.1",
    "framer-motion": "^11.11.0",
    "lucide-react": "^0.453.0",
    "next": "^14.2.15",
    "next-themes": "^0.3.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.13.0",
    "tailwind-merge": "^2.5.3",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.7.5",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.3"
  }
}
```

### `frontend/src/app/dashboard/accounts/[id]/page.tsx`

جزئیات و آمار هر اکانت با ۱۰ پست اخیر.

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardTitle, Spinner, StatusBadge } from "@/components/ui";
import { fmt, timeAgo } from "@/lib/utils";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [acc, setAcc] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    (async () => {
      const [{ data: a }, { data: s }] = await Promise.all([
        api.get(`/accounts/${id}`),
        api.get(`/accounts/${id}/analytics`),
      ]);
      setAcc(a);
      setStats(s);
    })();
  }, [id]);

  if (!acc) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">@{acc.username}</h1>
        <StatusBadge status={acc.status} />
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {[["Posts", stats?.posts], ["Views", fmt(stats?.views)], ["Likes", fmt(stats?.likes)], ["Engagement", `${stats?.avg_engagement ?? 0}%`]].map(([k, v]) => (
          <Card key={k as string}><p className="text-2xl font-extrabold">{v as string}</p><p className="text-xs text-zinc-500">{k}</p></Card>
        ))}
      </div>
      <Card>
        <CardTitle>Recent posts</CardTitle>
        {(stats?.recent ?? []).length === 0
          ? <p className="text-sm text-zinc-500">No posts yet.</p>
          : (stats.recent as any[]).map((p: any) => (
            <div key={p.id} className="flex items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <span>Post #{p.id}</span>
              <StatusBadge status={p.status} />
              <span className="ml-auto text-zinc-500">{fmt(p.views_7d)} views · {timeAgo(p.posted_at)}</span>
            </div>
          ))}
      </Card>
    </div>
  );
}
```

### `frontend/src/app/dashboard/accounts/page.tsx`

مدیریت اکانت‌ها: افزودن، لاگین، تست سشن، خواب/فعال‌سازی و حذف.

```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { Card, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { useAccounts, useApiMutation } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Account } from "@/types/models";

export default function AccountsPage() {
  const { data, isLoading } = useAccounts();
  const create = useApiMutation("post", [["accounts"]]);
  const remove = useApiMutation("delete", [["accounts"]]);
  const action = useApiMutation("post", [["accounts"]]);
  const [form, setForm] = useState({ username: "", password: "", max_daily_posts: 3 });
  const accounts = (data ?? []) as Account[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Instagram accounts</h1>
      <Card>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Username"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="instagram_user" /></Field>
          <Field label="Password"><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <Field label="Max posts/day"><input className="input" type="number" min={1} max={20} value={form.max_daily_posts} onChange={(e) => setForm({ ...form, max_daily_posts: Number(e.target.value) })} /></Field>
          <div className="flex items-end">
            <button
              className="btn-primary w-full" disabled={!form.username || !form.password || create.isPending}
              onClick={() => { create.mutate({ url: "/accounts", body: form }); setForm({ username: "", password: "", max_daily_posts: 3 }); }}
            >
              Add account
            </button>
          </div>
        </div>
      </Card>
      {isLoading ? <Spinner /> : accounts.length === 0 ? (
        <EmptyState title="No accounts" hint="Add your first Instagram account above." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {accounts.map((a) => (
            <Card key={a.id}>
              <div className="flex items-center gap-2">
                <Link href={`/dashboard/accounts/${a.id}`} className="font-semibold hover:text-emerald-500">@{a.username}</Link>
                <span className="ml-auto"><StatusBadge status={a.status} /></span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {a.posts_today}/{a.max_daily_posts} today · {a.total_posts} total · {a.total_views} views · last post {timeAgo(a.last_post)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/login` })}>Login</button>
                <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/test-session` })}>Test session</button>
                {a.status === "active"
                  ? <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/cooldown` })}>Cooldown</button>
                  : <button className="btn-ghost !px-3 !py-1.5 text-xs" onClick={() => action.mutate({ url: `/accounts/${a.id}/activate` })}>Activate</button>}
                <button
                  className="btn-ghost !px-3 !py-1.5 text-xs text-red-500"
                  onClick={() => { if (confirm(`Remove @${a.username}?`)) remove.mutate({ url: `/accounts/${a.id}` }); }}
                >
                  Remove
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/analytics/page.tsx`

تحلیل کامل: انتخاب بازه، روند بازدید، مقایسه اکانت‌ها و خروجی CSV.

```tsx
"use client";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardTitle, Spinner } from "@/components/ui";
import { useAccounts, useOverview } from "@/hooks/use-api";
import { apiBase, authHeaders } from "@/lib/api";
import { fmt } from "@/lib/utils";
import axios from "axios";

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useOverview(days);
  const { data: accounts } = useAccounts();

  async function exportCsv() {
    const { data: csv } = await axios.get(`${apiBase()}/api/v1/analytics/export`, { headers: authHeaders() });
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "analytics.csv";
    a.click();
  }

  if (isLoading || !data) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Analytics</h1>
        <select className="input ml-auto !w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[7, 14, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
        <button className="btn-ghost" onClick={exportCsv}>Export CSV</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><p className="text-2xl font-extrabold">{fmt(data.total_posts)}</p><p className="text-xs text-zinc-500">Posts</p></Card>
        <Card><p className="text-2xl font-extrabold">{fmt(data.total_views)}</p><p className="text-xs text-zinc-500">Views</p></Card>
        <Card><p className="text-2xl font-extrabold">{data.avg_engagement_rate}%</p><p className="text-xs text-zinc-500">Avg engagement</p></Card>
      </div>
      <Card>
        <CardTitle>Views trend</CardTitle>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="views" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <CardTitle>Posts per day</CardTitle>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="posts" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <CardTitle>Account comparison</CardTitle>
        {(accounts ?? []).length === 0
          ? <p className="text-sm text-zinc-500">No accounts yet.</p>
          : (accounts as { username: string; posts_today?: number; total_posts: number; total_views: number }[]).map((a: any) => (
            <div key={a.username ?? a.id} className="flex items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <strong>@{a.username}</strong>
              <span className="ml-auto text-zinc-500">{a.total_posts ?? 0} posts · {fmt(a.total_views)} views</span>
            </div>
          ))}
      </Card>
    </div>
  );
}
```

### `frontend/src/app/dashboard/bios/page.tsx`

مدیریت بایوهای چرخشی هر اکانت با فیلد لینک بات خارجی و دکمه اعمال فوری. (حفظ شده — تنها نقطه تماس با تلگرام خارجی.)

```tsx
"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useAccounts, useApiMutation, useBios } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Account, Bio } from "@/types/models";

export default function BiosPage() {
  const { data, isLoading } = useBios();
  const { data: accounts } = useAccounts();
  const create = useApiMutation("post", [["bios"]]);
  const remove = useApiMutation("delete", [["bios"]]);
  const apply = useApiMutation("post", [["bios"]]);
  const [form, setForm] = useState({ account_id: "", text: "", link_url: "", rotation_interval_days: 14 });
  const bios = (data ?? []) as Bio[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Bio rotation</h1>
      <Card>
        <CardTitle>New bio config</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Account">
            <select className="input" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Select…</option>
              {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
            </select>
          </Field>
          <Field label="Link URL"><input className="input" value={form.link_url} onChange={(e) => setForm({ ...form, link_url: e.target.value })} placeholder="https://t.me/…" /></Field>
          <Field label="Rotate every (days)"><input className="input" type="number" min={1} max={365} value={form.rotation_interval_days} onChange={(e) => setForm({ ...form, rotation_interval_days: Number(e.target.value) })} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!form.account_id || !form.text} onClick={() => { create.mutate({ url: "/bios", body: { ...form, account_id: Number(form.account_id) } }); setForm({ account_id: "", text: "", link_url: "", rotation_interval_days: 14 }); }}>Add</button></div>
        </div>
        <div className="mt-3"><Field label="Bio text"><textarea className="input" rows={2} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></Field></div>
      </Card>
      {isLoading ? <Spinner /> : bios.length === 0 ? <EmptyState title="No bio configs" /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {bios.map((b) => (
            <Card key={b.id}>
              <p className="text-sm font-semibold">Account #{b.account_id} · every {b.rotation_interval_days}d · last applied {timeAgo(b.last_applied)}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm">{b.text}</p>
              {b.link_url && <a href={b.link_url} target="_blank" className="text-sm text-sky-500 hover:underline">{b.link_url}</a>}
              <div className="mt-2 flex gap-2">
                <button className="btn-primary !py-1.5 text-xs" onClick={() => apply.mutate({ url: `/bios/${b.id}/apply` })}>Apply now</button>
                <button className="btn-ghost !py-1.5 text-xs text-red-500" onClick={() => { if (confirm("Delete this bio?")) remove.mutate({ url: `/bios/${b.id}` }); }}>Delete</button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/captions/page.tsx`

دو تب کپشن (ویرایشگر + پیش‌نمایش شبیه اینستاگرام) و هشتگ.

```tsx
"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useApiMutation, useCaptions, useHashtags } from "@/hooks/use-api";
import type { Caption, HashtagSet } from "@/types/models";

export default function CaptionsPage() {
  const [tab, setTab] = useState<"captions" | "hashtags">("captions");
  const { data: caps, isLoading: l1 } = useCaptions();
  const { data: tags, isLoading: l2 } = useHashtags();
  const createCap = useApiMutation("post", [["captions"]]);
  const delCap = useApiMutation("delete", [["captions"]]);
  const createTag = useApiMutation("post", [["hashtags"]]);
  const delTag = useApiMutation("delete", [["hashtags"]]);
  const [cap, setCap] = useState({ name: "", content: "", category: "" });
  const [tag, setTag] = useState({ name: "", tags: "" });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Captions & hashtags</h1>
      <div className="flex gap-2">
        {(["captions", "hashtags"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === t ? "bg-emerald-600 text-white" : "btn-ghost"}`}>
            {t === "captions" ? "Captions" : "Hashtags"}
          </button>
        ))}
      </div>

      {tab === "captions" ? (
        <>
          <Card>
            <CardTitle>New caption template</CardTitle>
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Name"><input className="input" value={cap.name} onChange={(e) => setCap({ ...cap, name: e.target.value })} /></Field>
              <Field label="Category"><input className="input" value={cap.category} onChange={(e) => setCap({ ...cap, category: e.target.value })} placeholder="optional" /></Field>
              <div className="flex items-end"><button className="btn-primary w-full" disabled={!cap.name || !cap.content} onClick={() => { createCap.mutate({ url: "/captions", body: { ...cap, category: cap.category || null } }); setCap({ name: "", content: "", category: "" }); }}>Add</button></div>
            </div>
            <div className="mt-3"><Field label="Content (emoji + line breaks supported)"><textarea className="input" rows={3} value={cap.content} onChange={(e) => setCap({ ...cap, content: e.target.value })} /></Field></div>
          </Card>
          {l1 ? <Spinner /> : ((caps ?? []) as Caption[]).length === 0 ? <EmptyState title="No captions" /> : (
            <div className="grid gap-4 md:grid-cols-2">
              {((caps ?? []) as Caption[]).map((c) => (
                <Card key={c.id}>
                  <div className="flex items-center gap-2">
                    <strong>{c.name}</strong>
                    {c.category && <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">{c.category}</span>}
                    <span className="ml-auto text-xs text-zinc-500">used {c.use_count}× · {c.avg_engagement ?? 0}% eng.</span>
                  </div>
                  <div className="mt-2 rounded-lg bg-zinc-50 p-3 text-sm whitespace-pre-wrap dark:bg-zinc-800/60">{c.content}</div>
                  <div className="mt-2 rounded-lg border border-zinc-200 p-3 text-xs text-zinc-500 dark:border-zinc-800">
                    <p className="font-semibold text-zinc-700 dark:text-zinc-300">Instagram preview</p>
                    <p className="whitespace-pre-wrap"><strong>yourpage</strong> {c.content.slice(0, 140)}{c.content.length > 140 ? "…" : ""}</p>
                  </div>
                  <button className="btn-ghost mt-2 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete "${c.name}"?`)) delCap.mutate({ url: `/captions/${c.id}` }); }}>Delete</button>
                </Card>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          <Card>
            <CardTitle>New hashtag set</CardTitle>
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Name"><input className="input" value={tag.name} onChange={(e) => setTag({ ...tag, name: e.target.value })} /></Field>
              <Field label="Tags (comma separated)">
                <input className="input" value={tag.tags} onChange={(e) => setTag({ ...tag, tags: e.target.value })} placeholder="#reels, #viral, …" />
              </Field>
              <div className="flex items-end"><button className="btn-primary w-full" disabled={!tag.name || !tag.tags} onClick={() => { createTag.mutate({ url: "/hashtags", body: tag }); setTag({ name: "", tags: "" }); }}>Add</button></div>
            </div>
          </Card>
          {l2 ? <Spinner /> : ((tags ?? []) as HashtagSet[]).length === 0 ? <EmptyState title="No hashtag sets" /> : (
            <div className="grid gap-4 md:grid-cols-2">
              {((tags ?? []) as HashtagSet[]).map((h) => (
                <Card key={h.id}>
                  <div className="flex items-center gap-2"><strong>{h.name}</strong><span className="ml-auto text-xs text-zinc-500">used {h.use_count}×</span></div>
                  <p className="mt-2 text-sm text-sky-600 dark:text-sky-400">{h.tags}</p>
                  <button className="btn-ghost mt-2 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete "${h.name}"?`)) delTag.mutate({ url: `/hashtags/${h.id}` }); }}>Delete</button>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/effects/page.tsx`

مدیریت افکت‌های FFmpeg با آمار استفاده.

```tsx
"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useApiMutation, useEffects } from "@/hooks/use-api";
import type { Effect } from "@/types/models";

export default function EffectsPage() {
  const { data, isLoading } = useEffects();
  const create = useApiMutation("post", [["effects"]]);
  const remove = useApiMutation("delete", [["effects"]]);
  const [form, setForm] = useState({ name: "", description: "", ffmpeg_filter: "" });
  const effects = (data ?? []) as Effect[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Video effect presets</h1>
      <Card>
        <CardTitle>New preset</CardTitle>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="warm_boost" /></Field>
          <Field label="Description"><input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Warm color grade + slight sharpen" /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!form.name} onClick={() => { create.mutate({ url: "/effects", body: form }); setForm({ name: "", description: "", ffmpeg_filter: "" }); }}>Add</button></div>
        </div>
        <div className="mt-3"><Field label="FFmpeg video filter (applied after crop/scale)"><input className="input font-mono text-xs" value={form.ffmpeg_filter} onChange={(e) => setForm({ ...form, ffmpeg_filter: e.target.value })} placeholder="eq=saturation=1.2:contrast=1.05,unsharp=5:5:0.5" /></Field></div>
      </Card>
      {isLoading ? <Spinner /> : effects.length === 0 ? <EmptyState title="No presets" hint="Leave empty to seed defaults, or add your own FFmpeg filters." /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {effects.map((e) => (
            <Card key={e.id}>
              <div className="flex items-center gap-2"><strong>{e.name}</strong><span className="ml-auto text-xs text-zinc-500">used {e.use_count}× · {e.avg_engagement ?? 0}% eng.</span></div>
              <p className="mt-1 text-sm text-zinc-500">{e.description}</p>
              <code className="mt-2 block rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">{e.ffmpeg_filter || "(no filter — plain crop/scale/encode)"}</code>
              <button className="btn-ghost mt-2 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete "${e.name}"?`)) remove.mutate({ url: `/effects/${e.id}` }); }}>Delete</button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/layout.tsx`

قاب داشبورد: محافظ لاگین، سایدبار، هدر، ناوبری موبایل و اتصال فید بلادرنگ.

```tsx
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Header, MobileNav, Sidebar, TopBar } from "@/components/layout";
import { useAuth } from "@/stores/stores";
import { useRealtimeFeed } from "@/hooks/use-realtime";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { username, ready, setAuth } = useAuth();
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.replace("/login");
    } else if (!username) {
      setAuth(localStorage.getItem("username") ?? "admin");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useRealtimeFeed(!!token);

  if (!token) return null;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <TopBar />
        <main className="flex-1 space-y-6 p-4 pb-20 md:p-6 md:pb-6">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
```

### `frontend/src/app/dashboard/logs/page.tsx`

نمایش لاگ‌ها با فیلتر سطح و دسته (بدون دسته `telegram`) و هرس دوره‌ای.

```tsx
"use client";
import { useState } from "react";
import { Card, EmptyState, Spinner } from "@/components/ui";
import { useApiMutation, useLogs } from "@/hooks/use-api";
import type { LogEntry } from "@/types/models";

const COLORS: Record<string, string> = {
  DEBUG: "text-zinc-400", INFO: "text-sky-500", WARNING: "text-amber-500",
  ERROR: "text-red-500", CRITICAL: "text-red-700 font-bold",
};

export default function LogsPage() {
  const { data, isLoading } = useLogs();
  const clear = useApiMutation("delete", [["logs"]]);
  const [level, setLevel] = useState("");
  const [category, setCategory] = useState("");
  const logs = ((data ?? []) as LogEntry[]).filter(
    (l) => (!level || l.level === level) && (!category || l.category === category)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">System logs</h1>
        <select className="input ml-auto !w-auto" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className="input !w-auto" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {["auth", "video", "post", "account", "scheduler", "system"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn-ghost !py-2 text-xs" onClick={() => { if (confirm("Delete logs older than 30 days?")) clear.mutate({ url: "/logs?older_than_days=30" }); }}>Prune 30d+</button>
      </div>
      {isLoading ? <Spinner /> : logs.length === 0 ? <EmptyState title="No logs" /> : (
        <Card className="!p-2 font-mono text-xs">
          {logs.map((l) => (
            <div key={l.id} className="flex gap-2 border-b border-zinc-100 px-2 py-1.5 last:border-0 dark:border-zinc-800">
              <span className="shrink-0 text-zinc-400">{new Date(l.timestamp).toLocaleString()}</span>
              <span className={`shrink-0 font-semibold ${COLORS[l.level] ?? ""}`}>{l.level}</span>
              <span className="shrink-0 rounded bg-zinc-100 px-1 dark:bg-zinc-800">{l.category}</span>
              <span className="break-all">{l.message}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/page.tsx`

نمای کلی: ۴ کارت KPI، نمودار بازدید و تعداد پست، جدول پست‌های اخیر، سلامت اکانت‌ها و وضعیت صف.

```tsx
"use client";
import Link from "next/link";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Clapperboard, Eye, Heart, Radio, Users } from "lucide-react";
import { Card, CardTitle, EmptyState, Spinner, StatusBadge } from "@/components/ui";
import { useAccounts, useOverview, usePosts, useQueue } from "@/hooks/use-api";
import { fmt, timeAgo } from "@/lib/utils";
import type { Account, Overview, Post } from "@/types/models";

function Kpi({ icon: Icon, label, value, sub }: { icon: typeof Eye; label: string; value: string; sub?: string }) {
  return (
    <Card>
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-emerald-600/10 p-2.5"><Icon className="h-5 w-5 text-emerald-500" /></div>
        <div>
          <p className="text-2xl font-extrabold tracking-tight">{value}</p>
          <p className="text-xs font-medium text-zinc-500">{label}{sub ? ` · ${sub}` : ""}</p>
        </div>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: overview, isLoading } = useOverview(30);
  const { data: accounts } = useAccounts();
  const { data: posts } = usePosts();
  const { data: queue } = useQueue();

  if (isLoading || !overview) return <Spinner />;
  const ov = overview as Overview;
  const recent = ((posts ?? []) as Post[]).slice(0, 10);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={Clapperboard} label="Total posts" value={fmt(ov.total_posts)} />
        <Kpi icon={Eye} label="Total views" value={fmt(ov.total_views)} />
        <Kpi icon={Heart} label="Avg engagement" value={`${ov.avg_engagement_rate}%`} />
        <Kpi icon={Users} label="Active accounts" value={String(ov.active_accounts)} sub={`${ov.queue_size} in queue`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardTitle>Views over time (30d)</CardTitle>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={ov.series}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="views" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardTitle>Posts per day (30d)</CardTitle>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ov.series}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="posts" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <CardTitle>Recent posts</CardTitle>
            <Link href="/dashboard/posts" className="text-xs font-semibold text-emerald-500 hover:underline">View all</Link>
          </div>
          {recent.length === 0 ? (
            <EmptyState title="No posts yet" hint="Upload a video and create a schedule rule to get started." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-zinc-400">
                    <th className="py-2 pr-4">Account</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4 text-right">Views</th>
                    <th className="py-2 pr-4 text-right">Likes</th>
                    <th className="py-2 text-right">When</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((p) => (
                    <tr key={p.id} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-2 pr-4 font-medium">#{p.account_id} · video #{p.video_id}</td>
                      <td className="py-2 pr-4"><StatusBadge status={p.status} /></td>
                      <td className="py-2 pr-4 text-right">{fmt(p.views_7d ?? p.views_24h)}</td>
                      <td className="py-2 pr-4 text-right">{fmt(p.likes_24h)}</td>
                      <td className="py-2 text-right text-zinc-500">{timeAgo(p.posted_at ?? p.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardTitle>Account health</CardTitle>
            <div className="space-y-2">
              {((accounts ?? []) as Account[]).map((a) => (
                <div key={a.id} className="flex items-center gap-2 text-sm">
                  <span className={`h-2 w-2 rounded-full ${a.status === "active" ? "bg-emerald-500" : a.status === "cooldown" ? "bg-amber-500" : "bg-red-500"}`} />
                  <span className="font-medium">@{a.username}</span>
                  <span className="ml-auto text-xs text-zinc-500">{a.posts_today}/{a.max_daily_posts} today</span>
                </div>
              ))}
              {(accounts ?? []).length === 0 && <p className="text-sm text-zinc-500">No accounts yet. <Link href="/dashboard/accounts" className="text-emerald-500 hover:underline">Add one</Link>.</p>}
            </div>
          </Card>
          <Card>
            <CardTitle>Processing queue</CardTitle>
            <div className="flex items-center gap-2 text-sm">
              <Radio className="h-4 w-4 text-emerald-500" />
              <span><strong>{ov.queue_size}</strong> videos waiting · <strong>{ov.scheduled_count}</strong> posts scheduled</span>
            </div>
            <Link href="/dashboard/videos/upload" className="btn-primary mt-3 w-full">Upload video</Link>
            {(queue ?? []).length > 0 && (
              <p className="mt-2 text-xs text-zinc-500">Next: {(queue as Post[])[0].scheduled_for ? timeAgo((queue as Post[])[0].scheduled_for) : "asap"}</p>
            )}
          </Card>
        </div>
      </div>

      <Card>
        <CardTitle>Engagement trend (30d)</CardTitle>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={ov.series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Area type="monotone" dataKey="posts" stroke="#10b981" fill="#10b981" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
```

### `frontend/src/app/dashboard/posts/page.tsx`

تاریخچه پست‌ها، صف «پست‌های بعدی»، تلاش مجدد و حذف.

```tsx
"use client";
import { useState } from "react";
import { Card, EmptyState, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, usePosts, useQueue } from "@/hooks/use-api";
import { fmt, timeAgo } from "@/lib/utils";
import type { Post } from "@/types/models";

export default function PostsPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading } = usePosts(status);
  const { data: queue } = useQueue();
  const retry = useApiMutation("post", [["posts"]]);
  const remove = useApiMutation("delete", [["posts"]]);
  const posts = (data ?? []) as Post[];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Posts</h1>
        <select className="input ml-auto !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["scheduled", "posting", "posted", "failed"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <Card>
        <p className="mb-2 text-sm font-semibold">Up next ({((queue ?? []) as Post[]).length})</p>
        {((queue ?? []) as Post[]).slice(0, 5).map((p) => (
          <div key={p.id} className="flex items-center gap-2 border-t border-zinc-100 py-1.5 text-sm first:border-0 dark:border-zinc-800">
            <span>Post #{p.id}</span>
            <span className="text-zinc-500">account #{p.account_id} · video #{p.video_id}</span>
            <span className="ml-auto text-zinc-500">{p.scheduled_for ? timeAgo(p.scheduled_for) : "asap"}</span>
          </div>
        ))}
        {(queue ?? []).length === 0 && <p className="text-sm text-zinc-500">Nothing scheduled.</p>}
      </Card>

      {isLoading ? <Spinner /> : posts.length === 0 ? (
        <EmptyState title="No posts" hint="Schedule rules create posts automatically every minute." />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-zinc-400">
                  <th className="py-2 pr-4">Post</th><th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4 text-right">Views</th><th className="py-2 pr-4 text-right">Eng.</th>
                  <th className="py-2 pr-4">Link</th><th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((p) => (
                  <tr key={p.id} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-4">#{p.id} · acc #{p.account_id} · vid #{p.video_id}</td>
                    <td className="py-2 pr-4"><StatusBadge status={p.status} /></td>
                    <td className="py-2 pr-4 text-right">{fmt(p.views_7d ?? p.views_24h)}</td>
                    <td className="py-2 pr-4 text-right">{p.engagement_rate != null ? `${p.engagement_rate}%` : "—"}</td>
                    <td className="py-2 pr-4">{p.ig_permalink ? <a className="text-emerald-500 hover:underline" href={p.ig_permalink} target="_blank">Reel ↗</a> : "—"}</td>
                    <td className="py-2 text-right">
                      {p.status === "failed" && <button className="btn-ghost mr-2 !px-3 !py-1 text-xs" onClick={() => retry.mutate({ url: `/posts/${p.id}/retry` })}>Retry</button>}
                      <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete post #${p.id}?`)) remove.mutate({ url: `/posts/${p.id}` }); }}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/proxies/page.tsx`

افزودن پروکسی، تست تکی، بررسی سلامت گروهی و نمایش تأخیر.

```tsx
"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, useProxies } from "@/hooks/use-api";
import type { Proxy } from "@/types/models";

export default function ProxiesPage() {
  const { data, isLoading } = useProxies();
  const create = useApiMutation("post", [["proxies"]]);
  const remove = useApiMutation("delete", [["proxies"]]);
  const test = useApiMutation("post", [["proxies"]]);
  const checkAll = useApiMutation("post", [["proxies"]]);
  const [form, setForm] = useState({ url: "", protocol: "http", username: "", password: "", country: "" });
  const proxies = (data ?? []) as Proxy[];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Proxy pool</h1>
        <button className="btn-ghost ml-auto !py-1.5 text-xs" onClick={() => checkAll.mutate({ url: "/proxies/check-all" })}>Health-check all</button>
      </div>
      <Card>
        <CardTitle>Add proxy</CardTitle>
        <div className="grid gap-3 md:grid-cols-5">
          <Field label="URL"><input className="input" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://1.2.3.4:8080" /></Field>
          <Field label="Protocol">
            <select className="input" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })}>
              <option value="http">http</option><option value="socks5">socks5</option><option value="socks4">socks4</option>
            </select>
          </Field>
          <Field label="Username"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
          <Field label="Password"><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!form.url} onClick={() => { create.mutate({ url: "/proxies", body: { ...form, username: form.username || null, password: form.password || null, country: form.country || null } }); setForm({ url: "", protocol: "http", username: "", password: "", country: "" }); }}>Add</button></div>
        </div>
      </Card>
      {isLoading ? <Spinner /> : proxies.length === 0 ? <EmptyState title="No proxies" hint="Assign one proxy per IG account for best deliverability." /> : (
        <Card>
          {proxies.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <span className={`h-2 w-2 rounded-full ${p.is_healthy ? "bg-emerald-500" : "bg-red-500"}`} />
              <code className="text-xs">{p.protocol}://{p.url.replace(/^https?:\/\//, "")}</code>
              <span className="text-zinc-500">{p.country ?? ""} · {p.latency_ms != null ? `${p.latency_ms}ms` : "—"} · fails {p.fail_count}</span>
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => test.mutate({ url: `/proxies/${p.id}/test` })}>Test</button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm("Delete proxy?")) remove.mutate({ url: `/proxies/${p.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
          {test.data && <p className="mt-2 text-xs text-zinc-500">Last test: {JSON.stringify(test.data)}</p>}
        </Card>
      )}
      <p className="text-xs text-zinc-500">Assign a proxy to an account from the Accounts page (proxy_id). Health checks run every 30 minutes via Celery Beat.</p>
    </div>
  );
}
```

### `frontend/src/app/dashboard/schedule/page.tsx`

تقویم هفتگی قوانین، فرم ساخت قانون جدید و مدیریت فعال/حذف.

```tsx
"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useAccounts, useApiMutation, useCaptions, useEffects, useRules } from "@/hooks/use-api";
import { dayLabel } from "@/lib/utils";
import type { Account, Caption, Effect, ScheduleRule } from "@/types/models";

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export default function SchedulePage() {
  const { data: rules, isLoading } = useRules();
  const { data: accounts } = useAccounts();
  const { data: captions } = useCaptions();
  const { data: effects } = useEffects();
  const create = useApiMutation("post", [["rules"]]);
  const update = useApiMutation("put", [["rules"]]);
  const remove = useApiMutation("delete", [["rules"]]);
  const toggle = useApiMutation("post", [["rules"]]);
  const [form, setForm] = useState({ name: "", day_of_week: -1, hour: 12, minute: 0, account_id: "", preferred_effect: "", caption_template_id: "" });
  const list = (rules ?? []) as ScheduleRule[];

  function submit() {
    create.mutate({
      url: "/schedule",
      body: {
        name: form.name || `${dayLabel(form.day_of_week)} ${form.hour}:${String(form.minute).padStart(2, "0")}`,
        day_of_week: form.day_of_week, hour: form.hour, minute: form.minute,
        account_id: form.account_id ? Number(form.account_id) : null,
        preferred_effect: form.preferred_effect || null,
        caption_template_id: form.caption_template_id ? Number(form.caption_template_id) : null,
      },
    });
    setForm({ name: "", day_of_week: -1, hour: 12, minute: 0, account_id: "", preferred_effect: "", caption_template_id: "" });
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Posting schedule</h1>

      <Card>
        <CardTitle>Weekly calendar</CardTitle>
        <div className="grid grid-cols-8 gap-1 text-center text-xs">
          <div />
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="font-semibold text-zinc-500">{d}</div>)}
          {HOURS.filter((h) => list.some((r) => r.hour === h)).map((h) => (
            <>
              <div key={`h-${h}`} className="pr-1 text-right text-zinc-400">{h}:00</div>
              {[0, 1, 2, 3, 4, 5, 6].map((d) => {
                const hits = list.filter((r) => r.hour === h && (r.day_of_week === -1 || r.day_of_week === d));
                return (
                  <div key={`${h}-${d}`} className="min-h-6 rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                    {hits.map((r) => (
                      <span key={r.id} className={`mr-0.5 inline-block h-2 w-2 rounded-full ${r.is_active ? "bg-emerald-500" : "bg-zinc-400"}`} title={r.name} />
                    ))}
                  </div>
                );
              })}
            </>
          ))}
        </div>
        {list.length === 0 && !isLoading && <p className="mt-2 text-sm text-zinc-500">No rules yet — every active hour shows here once added.</p>}
      </Card>

      <Card>
        <CardTitle>New rule</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="auto" /></Field>
          <Field label="Day">
            <select className="input" value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: Number(e.target.value) })}>
              <option value={-1}>Every day</option>
              {[0, 1, 2, 3, 4, 5, 6].map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
            </select>
          </Field>
          <Field label="Hour"><input className="input" type="number" min={0} max={23} value={form.hour} onChange={(e) => setForm({ ...form, hour: Number(e.target.value) })} /></Field>
          <Field label="Minute"><input className="input" type="number" min={0} max={59} value={form.minute} onChange={(e) => setForm({ ...form, minute: Number(e.target.value) })} /></Field>
          <Field label="Account">
            <select className="input" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Auto-select</option>
              {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
            </select>
          </Field>
          <Field label="Effect">
            <select className="input" value={form.preferred_effect} onChange={(e) => setForm({ ...form, preferred_effect: e.target.value })}>
              <option value="">Any</option>
              {((effects ?? []) as Effect[]).map((e) => <option key={e.name} value={e.name}>{e.name}</option>)}
            </select>
          </Field>
          <Field label="Caption template">
            <select className="input" value={form.caption_template_id} onChange={(e) => setForm({ ...form, caption_template_id: e.target.value })}>
              <option value="">Random</option>
              {((captions ?? []) as Caption[]).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <div className="flex items-end"><button className="btn-primary w-full" onClick={submit} disabled={create.isPending}>Add rule</button></div>
        </div>
      </Card>

      {isLoading ? <Spinner /> : list.length === 0 ? <EmptyState title="No schedule rules" /> : (
        <Card>
          {list.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <strong>{r.name}</strong>
              <span className="text-zinc-500">{dayLabel(r.day_of_week)} · {r.hour}:{String(r.minute).padStart(2, "0")}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${r.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" : "bg-zinc-200 text-zinc-500"}`}>
                {r.is_active ? "active" : "paused"}
              </span>
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => toggle.mutate({ url: `/schedule/${r.id}/toggle` })}>Toggle</button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete rule "${r.name}"?`)) remove.mutate({ url: `/schedule/${r.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/settings/page.tsx`

تنظیمات سراسری گروه‌بندی‌شده و فقط تست اتصال اینستاگرام (دکمه تست تلگرام حذف شده است).

```tsx
"use client";
import { Card, CardTitle, Spinner } from "@/components/ui";
import { useApiMutation, useSettings } from "@/hooks/use-api";
import type { Setting } from "@/types/models";

export default function SettingsPage() {
  const { data, isLoading } = useSettings();
  const save = useApiMutation("put", [["settings"]]);
  const testIg = useApiMutation("post", []);
  const settings = (data ?? []) as Setting[];
  const groups = settings.reduce<Record<string, Setting[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Global settings</h1>
      {isLoading ? <Spinner /> : Object.entries(groups).map(([cat, items]) => (
        <Card key={cat}>
          <CardTitle>{cat}</CardTitle>
          {items.map((s) => (
            <form
              key={s.key}
              className="flex items-center gap-2 border-t border-zinc-100 py-2 first:border-0 dark:border-zinc-800"
              onSubmit={(e) => { e.preventDefault(); save.mutate({ url: `/settings/${s.key}`, body: (e.target as HTMLFormElement).value.value }); }}
            >
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs font-semibold">{s.key}</p>
                <p className="truncate text-xs text-zinc-500">{s.is_sensitive ? "(sensitive â€” masked)" : s.value || "(empty)"}</p>
              </div>
              <input name="value" className="input !w-48" placeholder="new value" />
              <button className="btn-ghost !px-3 !py-1.5 text-xs">Save</button>
            </form>
          ))}
        </Card>
      ))}
      <Card>
        <CardTitle>Connection tests</CardTitle>
        <div className="flex gap-2">
          <button className="btn-ghost flex-1" onClick={() => testIg.mutate({ url: "/settings/test-instagram" })}>Test Instagram</button>
        </div>
        {testIg.data && (
          <pre className="mt-2 overflow-auto rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">{JSON.stringify(testIg.data, null, 2)}</pre>
        )}
      </Card>
    </div>
  );
}
```

### `frontend/src/app/dashboard/videos/[id]/page.tsx`

جزئیات ویدیو با `LivePreview` (افکت و واترمارک زنده همگام با فرم تنظیمات)، نوار پیشرفت و پردازش مجدد.

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, apiBase } from "@/lib/api";
import { Card, CardTitle, Field, Spinner, StatusBadge } from "@/components/ui";
import { LivePreview } from "@/components/live-preview";
import { useApiMutation, useEffects } from "@/hooks/use-api";

interface Detail {
  id: number; original_filename: string; duration: number | null; status: string;
  effect_preset: string | null; add_watermark: boolean; trim_start: number | null;
  trim_end: number | null; failed_reason: string | null;
}

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo] = useState<Detail | null>(null);
  const [progress, setProgress] = useState<{ percentage: number; stage: string } | null>(null);
  const [form, setForm] = useState({ effect_preset: "", trim_start: "", trim_end: "", add_watermark: true });
  const { data: effects } = useEffects();
  const save = useApiMutation("put", [["videos"]]);
  const process = useApiMutation("post", [["videos"]]);

  async function load() {
    const { data } = await api.get(`/videos/${id}`);
    setVideo(data);
    setForm({
      effect_preset: data.effect_preset ?? "",
      trim_start: data.trim_start?.toString() ?? "",
      trim_end: data.trim_end?.toString() ?? "",
      add_watermark: data.add_watermark,
    });
    try {
      const s = await api.get(`/videos/${id}/status`);
      setProgress(s.data.progress);
    } catch { /* ignore */ }
  }

  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); /* eslint-disable-next-line */ }, [id]);

  if (!video) return <Spinner />;

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <div className="mb-2 flex items-center gap-2">
          <CardTitle>#{video.id} · {video.original_filename}</CardTitle>
          <StatusBadge status={video.status} />
        </div>
        <LivePreview
          key={`${video.status}-${form.effect_preset}-${form.add_watermark}`}
          src={`${apiBase()}/api/v1/videos/${id}/preview`}
          effectName={form.effect_preset}
          watermark={form.add_watermark}
        />
        <p className="mt-2 text-xs text-zinc-500">Preview shows the selected effect (CSS approximation) and watermark overlay live.</p>
        {video.status === "processing" && (
          <div className="mt-3">
            <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
              <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress?.percentage ?? 5}%` }} />
            </div>
            <p className="mt-1 text-xs text-zinc-500">{progress?.stage ?? "processing"} · {(progress?.percentage ?? 0).toFixed(0)}%</p>
          </div>
        )}
        {video.failed_reason && <p className="mt-2 text-sm text-red-500">{video.failed_reason}</p>}
      </Card>

      <Card>
        <CardTitle>Processing settings</CardTitle>
        <div className="space-y-3">
          <Field label="Effect preset">
            <select className="input" value={form.effect_preset} onChange={(e) => setForm({ ...form, effect_preset: e.target.value })}>
              <option value="">Auto (random active preset)</option>
              {((effects ?? []) as { name: string; description: string }[]).map((e) => (
                <option key={e.name} value={e.name}>{e.name} — {e.description.slice(0, 60)}</option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Trim start (s)">
              <input className="input" type="number" min={0} step={0.5} value={form.trim_start} onChange={(e) => setForm({ ...form, trim_start: e.target.value })} />
            </Field>
            <Field label="Trim end (s)">
              <input className="input" type="number" min={0} step={0.5} value={form.trim_end} onChange={(e) => setForm({ ...form, trim_end: e.target.value })} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.add_watermark} onChange={(e) => setForm({ ...form, add_watermark: e.target.checked })} />
            Add watermark overlay
          </label>
          <div className="flex gap-2">
            <button
              className="btn-primary flex-1"
              disabled={save.isPending}
              onClick={async () => {
                await save.mutateAsync({
                  url: `/videos/${id}/settings`,
                  body: {
                    effect_preset: form.effect_preset || null,
                    trim_start: form.trim_start ? Number(form.trim_start) : null,
                    trim_end: form.trim_end ? Number(form.trim_end) : null,
                    add_watermark: form.add_watermark,
                  },
                });
                load();
              }}
            >
              Save settings
            </button>
            <button
              className="btn-ghost flex-1"
              disabled={process.isPending}
              onClick={async () => { await process.mutateAsync({ url: `/videos/${id}/reprocess` }); load(); }}
            >
              Re-process
            </button>
          </div>
          <p className="text-xs text-zinc-500">Output: 720×1280 H.264 + loudnorm audio, thumbnail at 25% duration.</p>
        </div>
      </Card>
    </div>
  );
}
```

### `frontend/src/app/dashboard/videos/page.tsx`

کتابخانه ویدیوها با فیلتر وضعیت، دکمه پردازش و حذف.

```tsx
"use client";
import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Card, EmptyState, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, useVideos } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Video } from "@/types/models";

export default function VideosPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading } = useVideos(status);
  const del = useApiMutation("delete", [[ "videos" ]]);
  const process = useApiMutation("post", [["videos"]]);
  const videos = (data ?? []) as Video[];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Videos</h1>
        <div className="ml-auto flex gap-2">
          <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {["uploaded", "processing", "processed", "posting", "posted", "failed", "archived"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <Link href="/dashboard/videos/upload" className="btn-primary"><Plus className="h-4 w-4" /> Upload</Link>
        </div>
      </div>
      {isLoading ? <Spinner /> : videos.length === 0 ? (
        <EmptyState title="No videos" hint="Upload your first video to start the funnel." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {videos.map((v) => (
            <Card key={v.id}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <Link href={`/dashboard/videos/${v.id}`} className="truncate font-semibold hover:text-emerald-500">
                  #{v.id} · {v.original_filename}
                </Link>
                <StatusBadge status={v.status} />
              </div>
              <p className="text-xs text-zinc-500">
                {v.duration ? `${v.duration.toFixed(1)}s` : "—"} · {timeAgo(v.created_at)}
                {v.failed_reason ? ` · ${v.failed_reason.slice(0, 80)}` : ""}
              </p>
              <div className="mt-3 flex gap-2">
                <Link href={`/dashboard/videos/${v.id}`} className="btn-ghost flex-1 !py-1.5 text-xs">Detail</Link>
                {(v.status === "uploaded" || v.status === "failed") && (
                  <button
                    className="btn-primary flex-1 !py-1.5 text-xs"
                    disabled={process.isPending}
                    onClick={() => process.mutate({ url: `/videos/${v.id}/process` })}
                  >
                    Process
                  </button>
                )}
                <button
                  className="btn-ghost !py-1.5 text-xs text-red-500"
                  disabled={del.isPending}
                  onClick={() => { if (confirm(`Delete video #${v.id}?`)) del.mutate({ url: `/videos/${v.id}` }); }}
                >
                  Delete
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### `frontend/src/app/dashboard/videos/upload/page.tsx`

آپلود درگ-دراپ با پیش‌نمایش زنده (object URL + اورلی canvas واترمارک + فیلتر CSS افکت)، انتخاب افکت و واترمارک؛ پس از آپلود، تنظیمات به‌صورت خودکار ذخیره می‌شود.

```tsx
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { UploadCloud } from "lucide-react";
import { Card, Field } from "@/components/ui";
import { LivePreview } from "@/components/live-preview";
import { useEffects } from "@/hooks/use-api";
import { apiBase, authHeaders } from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [effect, setEffect] = useState("");
  const [watermark, setWatermark] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const router = useRouter();
  const { data: effects } = useEffects();

  useEffect(() => {
    if (!file) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await axios.post(`${apiBase()}/api/v1/videos/upload`, form, {
        headers: { ...authHeaders(), "Content-Type": "multipart/form-data" },
        timeout: 600000,
      });
      // Persist the preview choices as the video's processing settings.
      try {
        await axios.put(
          `${apiBase()}/api/v1/videos/${data.id}/settings`,
          {
            effect_preset: effect || null,
            add_watermark: watermark,
          },
          { headers: authHeaders() }
        );
      } catch {
        /* settings save is best-effort; processing still proceeds */
      }
      router.push(`/dashboard/videos/${data.id}`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Upload failed";
      setError(String(msg));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Upload video</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files?.[0] ?? null); }}
            className={`flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition ${drag ? "border-emerald-500 bg-emerald-500/5" : "border-zinc-300 dark:border-zinc-700"}`}
          >
            <UploadCloud className="h-10 w-10 text-zinc-400" />
            <p className="text-sm text-zinc-500">Drag & drop a video here, or</p>
            <label className="btn-ghost cursor-pointer">
              Choose file
              <input
                type="file" className="hidden" accept="video/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {file && <p className="text-sm font-medium">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>}
          </div>
          <div className="mt-4 space-y-3">
            <Field label="Effect preset (live preview)">
              <select className="input" value={effect} onChange={(e) => setEffect(e.target.value)}>
                <option value="">Auto (random active preset)</option>
                {((effects ?? []) as { name: string; description: string }[]).map((e) => (
                  <option key={e.name} value={e.name}>{e.name}</option>
                ))}
              </select>
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={watermark} onChange={(e) => setWatermark(e.target.checked)} />
              Watermark overlay (bottom-right, as in output)
            </label>
          </div>
          {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
          <button className="btn-primary mt-4 w-full" disabled={!file || busy} onClick={upload}>
            {busy ? "Uploading…" : "Upload & process"}
          </button>
          <p className="mt-2 text-xs text-zinc-500">MP4/MOV/MKV/WebM/AVI up to the MAX_UPLOAD_MB limit. Duplicate files are rejected by content hash.</p>
        </Card>

        <Card>
          <p className="mb-2 text-sm font-semibold">Live preview</p>
          {objectUrl ? (
            <>
              <LivePreview src={objectUrl} effectName={effect} watermark={watermark} />
              <p className="mt-2 text-xs text-zinc-500">
                Effect is a CSS approximation; the real FFmpeg filter runs during processing. Watermark matches the backend 120px / 20px overlay.
              </p>
            </>
          ) : (
            <div className="flex aspect-[9/16] max-h-[560px] items-center justify-center rounded-lg bg-zinc-100 text-sm text-zinc-500 dark:bg-zinc-800">
              Select a file to preview it here
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
```

### `frontend/src/app/globals.css`

استایل سراسری و کلاس‌های آماده کارت، ورودی، دکمه و لیبل.

```css
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap");

@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-feature-settings: "cv11", "ss01";
}

.card {
  @apply rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900;
}

.input {
  @apply w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 dark:border-zinc-700 dark:bg-zinc-900;
}

.btn-primary {
  @apply inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50;
}

.btn-ghost {
  @apply inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800;
}

.label {
  @apply mb-1 block text-xs font-semibold uppercase tracking-wide text-zinc-500;
}
```

### `frontend/src/app/layout.tsx`

لی‌آوت ریشه: عنوان و توضیح به‌روزشده (پردازش و پست اینستاگرام، بدون تلگرام) و پروایدرها.

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "IG Funnel - Admin Dashboard",
  description: "Manage Instagram content processing and posting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### `frontend/src/app/login/page.tsx`

صفحه لاگین: ارسال اعتبار به API و ذخیره توکن‌ها.

```tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { Clapperboard } from "lucide-react";
import { apiBase } from "@/lib/api";
import { useAuth } from "@/stores/stores";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const { setAuth } = useAuth();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await axios.post(`${apiBase()}/api/v1/auth/login`, { username, password });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      setAuth(username);
      router.push("/dashboard");
    } catch {
      setError("Invalid credentials. Check ADMIN_USERNAME / ADMIN_PASSWORD in the backend .env.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-8">
        <div className="flex items-center gap-2">
          <Clapperboard className="h-7 w-7 text-emerald-500" />
          <h1 className="text-xl font-extrabold tracking-tight">IG Funnel</h1>
        </div>
        <p className="text-sm text-zinc-500">Sign in to the admin dashboard.</p>
        <div>
          <span className="label">Username</span>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </div>
        <div>
          <span className="label">Password</span>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
```

### `frontend/src/app/page.tsx`

ریدایرکت ریشه به داشبورد.

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
```

### `frontend/src/app/providers.tsx`

پروایدر تم و کلاینت TanStack Query.

```tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 5000 } },
  }));
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}
```

### `frontend/src/app/tailwind.css`

فایل پشتیبان/سرویس.

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### `frontend/src/components/layout.tsx`

سایدبار ۱۲ بخشی (بدون آیتم Telegram)، هدر/تاپ‌بار با تغییر تم و ناوبری موبایل.

```tsx
"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3, CalendarClock, Captions, Clapperboard, FileText, Home, Instagram,
  LogOut, Menu, Moon, Settings, SlidersHorizontal, Sun, Users, History,
} from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useAuth, useUi } from "@/stores/stores";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/dashboard/videos", label: "Videos", icon: Clapperboard },
  { href: "/dashboard/accounts", label: "Accounts", icon: Instagram },
  { href: "/dashboard/posts", label: "Posts", icon: History },
  { href: "/dashboard/schedule", label: "Schedule", icon: CalendarClock },
  { href: "/dashboard/captions", label: "Captions", icon: Captions },
  { href: "/dashboard/bios", label: "Bios", icon: FileText },
  { href: "/dashboard/proxies", label: "Proxies", icon: Users },
  { href: "/dashboard/effects", label: "Effects", icon: SlidersHorizontal },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/logs", label: "Logs", icon: FileText },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen } = useUi();
  const { logout } = useAuth();
  if (!sidebarOpen) return null;
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 md:flex">
      <div className="flex h-16 items-center gap-2 border-b border-zinc-200 px-5 dark:border-zinc-800">
        <Clapperboard className="h-6 w-6 text-emerald-500" />
        <span className="text-lg font-extrabold tracking-tight">IG Funnel</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                active
                  ? "bg-emerald-600/10 text-emerald-600 dark:text-emerald-400"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <button onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900">
          <LogOut className="h-4 w-4" /> Log out
        </button>
      </div>
    </aside>
  );
}

export function Header() {
  const { toggleSidebar } = useUi();
  const { username } = useAuth();
  const { theme, setTheme } = useTheme();
  const router = useRouter();
  return (
    <header className="flex h-16 items-center gap-3 border-b border-zinc-200 bg-white/80 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80 md:hidden">
      <button onClick={toggleSidebar} className="btn-ghost !px-2"><Menu className="h-5 w-5" /></button>
      <span className="font-extrabold">IG Funnel</span>
      <div className="ml-auto flex items-center gap-2">
        <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="btn-ghost !px-2" aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <span className="text-xs text-zinc-500">{username}</span>
      </div>
    </header>
  );
}

export function TopBar() {
  const { toggleSidebar, sidebarOpen } = useUi();
  const { username } = useAuth();
  const { theme, setTheme } = useTheme();
  return (
    <header className="sticky top-0 z-10 hidden h-16 items-center gap-3 border-b border-zinc-200 bg-white/80 px-6 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80 md:flex">
      <button onClick={toggleSidebar} className="btn-ghost !px-2" aria-label="Toggle sidebar">
        <Menu className="h-5 w-5" />
      </button>
      <span className="text-xs text-zinc-400">{sidebarOpen ? "" : "IG Funnel"}</span>
      <div className="ml-auto flex items-center gap-3">
        <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="btn-ghost !px-2" aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-semibold dark:bg-zinc-800">{username ?? "admin"}</span>
      </div>
    </header>
  );
}

/** Mobile bottom nav â€” same links, horizontally scrollable. */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 flex gap-1 overflow-x-auto border-t border-zinc-200 bg-white p-2 dark:border-zinc-800 dark:bg-zinc-950 md:hidden">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex shrink-0 flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-[10px] font-medium",
            pathname === href ? "text-emerald-500" : "text-zinc-500"
          )}
        >
          <Icon className="h-4 w-4" />
          {label}
        </Link>
      ))}
    </nav>
  );
}
```

### `frontend/src/components/live-preview.tsx`

کامپوننت `LivePreview`: ویدیوی HTML5 + canvas اورلی واترمارک با بازطراحی در هر فریم (requestAnimationFrame) روی play/seek/resize و اعمال فیلتر CSS افکت.

```tsx
"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { EFFECT_CSS, drawWatermark, useWatermarkImage } from "@/components/video-preview";

/**
 * Live preview: HTML5 video + canvas watermark overlay + CSS effect approximation.
 * Canvas sits exactly on top of the video and redraws on play/seek/resize so
 * the watermark stays static over the moving frame.
 */
export function LivePreview({
  src,
  effectName,
  watermark,
  className,
}: {
  src: string;
  effectName: string;
  watermark: boolean;
  className?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wm = useWatermarkImage();
  const css = useMemo(() => EFFECT_CSS[effectName] ?? "", [effectName]);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    let raf = 0;
    let lastDrawn = -1;

    const draw = () => {
      const w = video.clientWidth;
      const h = video.clientHeight;
      if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
      }
      // Redraw when playing (time changes) or after a state change.
      if (watermark && wm && (!video.paused || video.currentTime !== lastDrawn)) {
        drawWatermark(canvas, wm);
        lastDrawn = video.currentTime;
      } else if (!watermark) {
        const ctx = canvas.getContext("2d");
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
        lastDrawn = video.currentTime;
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    const force = () => {
      lastDrawn = -1;
    };
    video.addEventListener("play", force);
    video.addEventListener("seeked", force);
    video.addEventListener("loadeddata", force);
    window.addEventListener("resize", force);
    return () => {
      cancelAnimationFrame(raf);
      video.removeEventListener("play", force);
      video.removeEventListener("seeked", force);
      video.removeEventListener("loadeddata", force);
      window.removeEventListener("resize", force);
    };
  }, [src, watermark, wm]);

  return (
    <div className={`relative overflow-hidden rounded-lg bg-black ${className ?? ""}`}>
      <video ref={videoRef} controls src={src} className="aspect-[9/16] max-h-[560px] w-full" style={{ filter: css }} />
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      />
    </div>
  );
}
```

### `frontend/src/components/ui.tsx`

کامپوننت‌های مشترک: کارت، بج وضعیت، حالت خالی، اسپینر و فیلد فرم.

```tsx
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("card p-5", className)}>{children}</div>;
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">{children}</h3>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    processed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    posted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    scheduled: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
    processing: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    posting: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    uploaded: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    cooldown: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    failed: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    banned: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    challenge_required: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    disabled: "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
    archived: "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  };
  const cls = map[status] ?? "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card flex flex-col items-center gap-1 p-10 text-center">
      <p className="font-semibold">{title}</p>
      {hint && <p className="text-sm text-zinc-500">{hint}</p>}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center p-10">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-emerald-600" />
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}
```

### `frontend/src/components/video-preview.tsx`

تقسیم‌بندی افکت‌های CSS (`EFFECT_CSS`)، لودر تصویر واترمارک (`/watermark.png` با fallback placeholder) و تابع `drawWatermark` منطبق بر منطق بک‌اند (عرض ۱۲۰px در خروجی ۷۲۰p با پدینگ ۲۰px).

```tsx
"use client";
import { useEffect, useState } from "react";

/**
 * CSS approximations of the FFmpeg effect presets (visual preview only —
 * the real filter runs server-side during processing).
 */
export const EFFECT_CSS: Record<string, string> = {
  warm_filter: "saturate(1.3) brightness(1.05) sepia(0.15)",
  cool_filter: "saturate(1.1) hue-rotate(-12deg) brightness(1.02)",
  vintage_filter: "saturate(0.75) contrast(1.05) sepia(0.35)",
  boost_filter: "saturate(1.5) contrast(1.12) brightness(1.03)",
  sharp_clean: "contrast(1.05) saturate(1.1)",
  soft_glow: "brightness(1.06) saturate(1.15) blur(0.3px)",
  noir_filter: "grayscale(1) contrast(1.15)",
};

const PLACEHOLDER_SVG =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80"><rect width="240" height="80" rx="12" fill="rgba(0,0,0,0.55)"/><text x="120" y="50" font-family="Arial" font-size="28" font-weight="bold" fill="white" text-anchor="middle">@yourbrand</text></svg>`
  );

export const WATERMARK_SRC = "/watermark.png";

/** Loads /watermark.png, falling back to a built-in placeholder badge. */
export function useWatermarkImage(): HTMLImageElement | null {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    let cancelled = false;
    const primary = new Image();
    primary.onload = () => {
      if (!cancelled) setImg(primary);
    };
    primary.onerror = () => {
      const fallback = new Image();
      fallback.onload = () => {
        if (!cancelled) setImg(fallback);
      };
      fallback.src = PLACEHOLDER_SVG;
    };
    primary.src = WATERMARK_SRC;
    return () => {
      cancelled = true;
    };
  }, []);
  return img;
}

/**
 * Draws the watermark bottom-right, mirroring the backend FFmpeg filter:
 *   [1:v]scale=120:-1[wm]; [v][wm]overlay=W-w-20:20
 * i.e. 120px wide at 720p output, 20px padding from right/bottom edges.
 * Scaled proportionally to the canvas size (output is 720 wide).
 */
export function drawWatermark(canvas: HTMLCanvasElement, wm: HTMLImageElement) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const scale = canvas.width / 720;
  const w = 120 * scale;
  const h = (wm.naturalHeight / wm.naturalWidth) * w || 40 * scale;
  const pad = 20 * scale;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = 0.85;
  ctx.drawImage(wm, canvas.width - w - pad, canvas.height - h - pad, w, h);
  ctx.globalAlpha = 1;
}
```

### `frontend/src/hooks/use-api.ts`

هوک‌های TanStack Query برای همه منابع (بدون `useTelegram`) با رفرش خودکار و موتاسیون عمومی.

```ts
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

async function get<T = any>(url: string): Promise<T> {
  const { data } = await api.get(url);
  return data;
}

export function useOverview(days = 30) {
  return useQuery({ queryKey: ["overview", days], queryFn: () => get(`/analytics/overview?days=${days}`), refetchInterval: 15000 });
}
export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: () => get("/accounts"), refetchInterval: 15000 });
}
export function useVideos(status = "") {
  return useQuery({
    queryKey: ["videos", status],
    queryFn: () => get(status ? `/videos?status=${status}` : "/videos"),
    refetchInterval: 5000,
  });
}
export function usePosts(status = "") {
  return useQuery({
    queryKey: ["posts", status],
    queryFn: () => get(status ? `/posts?status=${status}` : "/posts"),
    refetchInterval: 10000,
  });
}
export function useQueue() {
  return useQuery({ queryKey: ["queue"], queryFn: () => get("/posts/queue"), refetchInterval: 10000 });
}
export function useRules() {
  return useQuery({ queryKey: ["rules"], queryFn: () => get("/schedule") });
}
export function useCaptions() {
  return useQuery({ queryKey: ["captions"], queryFn: () => get("/captions") });
}
export function useHashtags() {
  return useQuery({ queryKey: ["hashtags"], queryFn: () => get("/hashtags") });
}
export function useBios() {
  return useQuery({ queryKey: ["bios"], queryFn: () => get("/bios") });
}
export function useProxies() {
  return useQuery({ queryKey: ["proxies"], queryFn: () => get("/proxies") });
}
export function useEffects() {
  return useQuery({ queryKey: ["effects"], queryFn: () => get("/effects") });
}
export function useLogs() {
  return useQuery({ queryKey: ["logs"], queryFn: () => get("/logs?limit=200"), refetchInterval: 8000 });
}
export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => get("/settings") });
}
export function useApiMutation(method: "post" | "put" | "delete", invalidate: string[][] = []) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ url, body }: { url: string; body?: unknown }) => {
      const { data } = await api.request({ method, url, data: body });
      return data;
    },
    onSuccess: () => {
      for (const key of invalidate) qc.invalidateQueries({ queryKey: key });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}
```

### `frontend/src/hooks/use-realtime.ts`

اتصال وب‌سوکت احرازهویت‌شده با تلاش مجدد نمایی و ابطال کوئری‌ها هنگام رویداد.

```ts
"use client";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiBase } from "@/lib/api";

const EVENTS = [
  "video_processing_progress",
  "video_processing_complete",
  "post_status_update",
  "account_status_change",
  "new_log",
];

/** Opens an authenticated WS feed; invalidates related queries on events (polling fallback lives in hooks). */
export function useRealtimeFeed(enabled: boolean) {
  const qc = useQueryClient();
  const tries = useRef(0);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const token = localStorage.getItem("access_token");
      if (!token) return;
      try {
        ws = new WebSocket(`${apiBase().replace(/^http/, "ws")}/ws?token=${encodeURIComponent(token)}`);
      } catch {
        return;
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (!EVENTS.includes(msg.event) && msg.event !== "connected") return;
          tries.current = 0;
          if (msg.event.startsWith("video")) {
            qc.invalidateQueries({ queryKey: ["videos"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("post")) {
            qc.invalidateQueries({ queryKey: ["posts"] });
            qc.invalidateQueries({ queryKey: ["queue"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("account")) {
            qc.invalidateQueries({ queryKey: ["accounts"] });
          } else if (msg.event === "new_log") {
            qc.invalidateQueries({ queryKey: ["logs"] });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        tries.current += 1;
        setTimeout(connect, Math.min(15000, 1000 * 2 ** tries.current));
      };
    };

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [enabled, qc]);
}
```

### `frontend/src/lib/api.ts`

نمونه axios با تزریق توکن و تمدید خودکار آن هنگام ۴۰۱.

```ts
import axios from "axios";

const baseURL =
  (typeof window !== "undefined" && (window as unknown as { __API_URL?: string }).__API_URL) ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const api = axios.create({ baseURL: `${baseURL}/api/v1`, timeout: 30000 });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing = false;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried && typeof window !== "undefined") {
      original._retried = true;
      const refresh = localStorage.getItem("refresh_token");
      if (refresh && !refreshing) {
        refreshing = true;
        try {
          const { data } = await axios.post(`${baseURL}/api/v1/auth/refresh`, { refresh_token: refresh });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        } finally {
          refreshing = false;
        }
      }
    }
    return Promise.reject(error);
  }
);

export function apiBase(): string {
  return baseURL;
}

export function authHeaders() {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}
```

### `frontend/src/lib/utils.ts`

توابع کمکی: ترکیب کلاس، قالب اعداد، زمان نسبی و نام روزها.

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function dayLabel(dow: number): string {
  return dow === -1 ? "Every day" : DAYS[dow] ?? `Day ${dow}`;
}
```

### `frontend/src/stores/stores.ts`

استورهای zustand برای احراز هویت و وضعیت رابط کاربری.

```ts
"use client";
import { create } from "zustand";

interface AuthState {
  username: string | null;
  ready: boolean;
  setAuth: (username: string | null) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  username: typeof window !== "undefined" ? localStorage.getItem("username") : null,
  ready: false,
  setAuth: (username) => {
    if (username) localStorage.setItem("username", username);
    else localStorage.removeItem("username");
    set({ username, ready: true });
  },
  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("username");
    set({ username: null, ready: true });
    window.location.href = "/login";
  },
}));

interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useUi = create<UiState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

### `frontend/src/types/models.ts`

تایپ‌های دامنه منطبق با خروجی API (بدون تایپ تلگرام؛ `Bio.link_url` برای لینک خارجی حفظ شده است).

```ts
export interface Account {
  id: number; username: string; proxy_id: number | null; status: string;
  last_login: string | null; last_post: string | null; posts_today: number;
  max_daily_posts: number; cooldown_until: string | null; total_posts: number;
  total_views: number; total_likes: number; notes: string | null;
}

export interface Video {
  id: number; original_filename: string; duration: number | null; file_size: number | null;
  status: string; effect_preset: string | null; add_watermark: boolean;
  trim_start: number | null; trim_end: number | null; failed_reason: string | null;
  processed_at: string | null; thumbnail_path: string | null; created_at: string;
}

export interface Post {
  id: number; video_id: number; account_id: number; ig_media_id: string | null;
  ig_permalink: string | null; caption: string; hashtags: string; status: string;
  scheduled_for: string | null; posted_at: string | null; views_24h: number | null;
  views_7d: number | null; likes_24h: number | null; engagement_rate: number | null;
  fail_reason: string | null; retry_count: number; created_at: string;
}

export interface ScheduleRule {
  id: number; name: string; day_of_week: number; hour: number; minute: number;
  account_id: number | null; is_active: boolean; preferred_effect: string | null;
  caption_template_id: number | null; created_at?: string;
}

export interface Caption { id: number; name: string; content: string; category: string | null; is_active: boolean; use_count: number; avg_engagement: number | null; }
export interface HashtagSet { id: number; name: string; tags: string; is_active: boolean; use_count: number; }
export interface Bio { id: number; account_id: number; text: string; link_url: string; is_active: boolean; rotation_interval_days: number; last_applied: string | null; }
export interface Proxy { id: number; url: string; protocol: string; username: string | null; country: string | null; is_healthy: boolean; last_checked: string | null; fail_count: number; latency_ms: number | null; is_active: boolean; }
export interface Effect { id: number; name: string; description: string; ffmpeg_filter: string; is_active: boolean; use_count: number; avg_engagement: number | null; }
export interface LogEntry { id: number; level: string; category: string; message: string; details: Record<string, unknown> | null; timestamp: string; }
export interface Setting { key: string; value: string; category: string; is_sensitive: boolean; }

export interface Overview {
  total_posts: number; total_views: number; avg_engagement_rate: number;
  active_accounts: number; queue_size: number; scheduled_count: number;
  series: { date: string; posts: number; views: number }[];
}
```

### `frontend/tailwind.config.ts`

تم تیلویند: حالت دارک کلاسی، فونت Inter و رنگ تاکیدی سبز.

```ts
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: { accent: { DEFAULT: "#10b981", soft: "#a7f3d0" } },
    },
  },
  plugins: [],
};
```

### `frontend/tsconfig.json`

تنظیمات تایپ‌اسکریپت با آلیاس `@/*` به `src/*`.

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### `nginx/nginx.conf`

ریورس‌پروکسی: فرانت در `/`، بک‌اند در `/api` و `/health`، وب‌سوکت در `/ws` و فایل‌های مدیا در `/media`.

```nginx
events {}
http {
  upstream backend { server backend:8000; }
  upstream frontend { server frontend:3000; }

  server {
    listen 80;

    # API + websocket
    location /api/ { proxy_pass http://backend; proxy_set_header Host $host; }
    location /ws { proxy_pass http://backend; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
    location /health { proxy_pass http://backend; }

    # Raw media (thumbnails/previews served by API, but allow direct access)
    location /media/ { alias /srv/media/; }

    # Everything else → Next.js
    location / { proxy_pass http://frontend; proxy_set_header Host $host; }
  }
}
```
