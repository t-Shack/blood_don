# BDMIS — Blood Donor Management Information System

A Django web application that connects blood donors with Nigerian hospitals facing
shortages. Donors register themselves, hospitals publish live inventory per blood
type, and whenever a blood request cannot be met from stock the system emails every
eligible, compatible donor automatically.

Scope is Nigeria-wide; this deployment is seeded with and tested against hospitals in
the **Nsukka metropolis, Enugu State**.

---

## Stack

| Layer      | Choice                                            |
|------------|---------------------------------------------------|
| Backend    | Python 3.11+ · Django 5.2                         |
| Frontend   | Vanilla JS, HTML5, CSS3 (no framework), self-hosted fonts and icons |
| Database   | PostgreSQL 16 on Neon (serverless) — never SQLite |
| Email      | Gmail SMTP, HTML templates                        |
| Deployment | Render (gunicorn + whitenoise)                    |

`psycopg[binary]` (psycopg 3) is used as the adapter instead of `psycopg2-binary`;
it is the supported driver for Django 5.x and ships wheels for current Pythons.

---

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      
python manage.py migrate
python manage.py seed_data --demo
python manage.py createsuperuser
python manage.py runserver
```

`manage.py` defaults to `bdmis.settings.development`; gunicorn and `wsgi.py` default
to `bdmis.settings.production`.

### Neon database

Create two branches in the Neon dashboard:

* `main` — production, used by Render
* `dev` — local development, so local migrations never touch production data

Copy the branch's connection string into `DATABASE_URL`. Keep `?sslmode=require`;
Neon rejects unencrypted connections, and `ssl_require=True` is set in settings.
Connections are pooled with `conn_max_age=600` to survive Neon's cold starts. Under
load, switch to Neon's pooled endpoint (Connection Details → Pooled connection).

Use the **pooled** endpoint (the host containing `-pooler`) in `DATABASE_URL`.

Running the test suite creates and drops a `test_...` database on whichever branch
`DATABASE_URL` points at — always point it at `dev` locally. Neon's pooler runs
PgBouncer, which cannot execute `CREATE DATABASE`, so a test run against a pooled
host would hang with no error message; `settings/base.py` detects `test` in `argv`
and swaps to the direct endpoint automatically.

### Gmail SMTP

`EMAIL_HOST_PASSWORD` must be a **Gmail App Password**, not the account password:

1. Enable 2-Factor Authentication on the Google account.
2. Google Account → Security → App Passwords.
3. Generate one for "Mail" on "Other device".
4. Use the 16-character value.

Development uses the console email backend by default, so nothing is sent locally.
Set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` in `.env` to test
real delivery.

---

## Project layout

```
bdmis/
├── bdmis/settings/{base,development,production}.py
├── apps/
│   ├── accounts/      custom User, DonorProfile, roles, blood-type constants
│   ├── hospitals/     hospital directory (admin-managed)
│   ├── inventory/     BloodInventory, 8 rows per hospital, status thresholds
│   ├── requests/      BloodRequest, stock fulfilment, compatibility
│   ├── donations/     DonationRecord — updates stock and eligibility on save
│   ├── notifications/ Notification log, HTML email dispatch
│   └── core/          landing page, criteria CMS, JSON API, admin panel
├── templates/         base layout, per-app pages, HTML emails
└── static/           css (tokens, base, components, pages), js, fonts, img
```

The `requests` app uses the Django app label **`bloodrequests`** so it never collides
with the `requests` HTTP library; the Python package is still `apps.requests`.

---

## Roles

| Role   | Can                                                                       |
|--------|---------------------------------------------------------------------------|
| donor  | register, dashboard, own profile and history, public pages                |
| staff  | everything a donor can, plus raise requests, record donations, view their hospital's requests |
| admin  | everything, plus manage hospitals, inventory, users, criteria content, notification log |

Enforced by `apps/accounts/decorators.py` (`donor_required`, `staff_required`,
`admin_required`, `RoleRequiredMixin`). The custom panel at `/admin-panel/` is the
day-to-day admin tool; Django's own `/admin/` is superuser-only emergency access.

---

## Blood compatibility

Strict ABO + Rh, defined once in `apps/accounts/constants.py` and used by both the
request matcher and the donor filter:

```
O-  → everyone (universal donor)      AB+ ← everyone (universal recipient)
O+  → O+, A+, B+, AB+                 AB- ← A-, B-, AB-, O-
A-  → A-, A+, AB-, AB+                A+  ← A+, A-, O+, O-
A+  → A+, AB+                         B+  ← B+, B-, O+, O-
B-  → B-, B+, AB-, AB+                B-  ← B-, O-
B+  → B+, AB+                         O+  ← O+, O-
AB- → AB-, AB+                        O-  ← O- only
```

All eight recipient types are covered by tests, including a consistency check that
the donor-side and recipient-side lookups agree.

---

## Key flows

**Request submitted** → stock for that exact type at that hospital is checked →
enough on the shelf, the request is fulfilled and stock decremented in one atomic
transaction → not enough, whatever exists is drawn, the request stays `pending`, and
a daemon thread emails every eligible compatible donor, logging each attempt in
`Notification`.

**Donation recorded** → the donor's `last_donation_date` moves forward (never
backwards for a late-entered record), eligibility recomputes against the 56-day rule,
and the hospital's stock for that donor's blood type increments via an `F()`
expression so concurrent writes cannot lose each other.

**Eligibility** is enforced in two places, as required: after every donation, and by
`python manage.py update_donor_eligibility` (Render cron, nightly at 02:00) which
catches donors who simply waited out their window.

---

## Real-time inventory

`static/js/inventory.js` polls `GET /api/inventory/<hospital_id>/` every 30 seconds
and patches the DOM in place — no reload, no WebSockets. Polling pauses while the tab
is hidden and refreshes immediately on return. Every inventory view shows a
"last updated" stamp that ticks in relative time.

### API

All responses use the envelope `{success, data, message}`.

| Method | Endpoint                          | Auth   |
|--------|-----------------------------------|--------|
| GET    | `/api/inventory/`                 | public |
| GET    | `/api/inventory/<hospital_id>/`   | public |
| GET    | `/api/hospitals/in-shortage/`     | public |
| GET    | `/api/donor/eligibility/`         | donor  |
| POST   | `/api/requests/<id>/fulfill/`     | staff  |

---

## Management commands

```bash
python manage.py seed_data            # Nsukka hospitals + criteria content
python manage.py seed_data --demo     # plus demo donors, staff, stock levels
python manage.py update_donor_eligibility [--dry-run]
python manage.py refresh_statistics
```

Demo credentials created by `--demo`: `admin@bdmis.ng` / `BdmisAdmin2025`,
`staff1@bdmis.ng` / `BdmisStaff2025`, `donor1@example.com` / `BdmisDonor2025`.
Change or remove these before any real deployment.

---

## Tests

```bash
python manage.py test
```

Covers the compatibility matrix (all eight types), the 56-day rule, inventory
increment on donation and decrement on fulfilment, donor selection for dispatch,
and role-based access control for every protected URL.

---

## Theming

Light and dark themes are pure CSS custom properties in `static/css/themes.css`.
`theme.js` loads in `<head>` and applies the stored choice before first paint, so
there is no flash of the wrong theme. With no stored choice it follows the
system's light/dark setting. The preference persists in `localStorage`; every
storage access is wrapped in `try/catch` for private-browsing mode.

---

## Design system

| Piece        | Where                                  | Notes |
|--------------|----------------------------------------|-------|
| Tokens       | `static/css/themes.css`                | One blood-red accent; green/amber/red only ever mean stock status. Every text pairing is checked against WCAG AA. |
| Layout, type | `static/css/base.css`                  | Archivo at two widths: condensed for headings and figures, normal for reading. |
| Components   | `static/css/components.css`            | Header, buttons, forms, tags, tables, live inventory grid, toasts, admin shell. |
| Pages        | `static/css/pages.css`                 | Home stage and sections, sign-in split, donor dashboard, About chart. |
| Typeface     | `static/fonts/`                        | Archivo (SIL OFL 1.1), self-hosted; no request to Google Fonts. |
| Icons        | `apps/core/templatetags/icons.py`      | Phosphor Icons (MIT, notice in `PHOSPHOR-ICONS-LICENSE.txt` beside it), inlined by `{% icon %}`. Old Lucide-era names still work as aliases. |
| Photographs  | `static/img/`                          | Wikimedia Commons, CC0 or public domain only, so no on-page credit is owed. Toned so only genuine reds keep their colour. Check the licence before adding any photo: CC BY or CC BY-SA would require a visible credit. |

`{% load ui %}` provides the `rh` filter, which typesets blood types with a true
minus sign on screen (`O-` becomes `O−`). Stored values, forms and the API keep
the ASCII hyphen.

Shape rule: controls use a 10px radius, panels and photographs 16px, status tags
6px, and only the live indicator is round.
