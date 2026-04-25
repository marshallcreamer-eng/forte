# Forte — Social Media Content Creator

Part of the Automatey platform. See `~/Automatey/CLAUDE.md` for full platform context.

## Purpose
AI-powered social media content tool for charter schools. Staff describe what's happening, click Generate, and get platform-ready drafts for Facebook, Instagram, LinkedIn, X, ClassDojo, and newsletter — all written in the school's tone of voice. Includes photo briefs, post status tracking, a content calendar, and file import.

Initial client: Belton Preparatory Academy (BPA), Belton SC. Portfolio piece and free gift — Marshall's kids attend.
Network opportunity: Charter Institute at Erskine (28 schools). Target contact: Katie Graybill, Director of Communications — kgraybill@erskinecharters.org

## Stack
- Python Flask + SQLAlchemy
- SQLite locally, Postgres on Railway
- Flask-Login (bcrypt passwords)
- Google Gemini 2.5 Flash — draft generation + photo briefs + file import extraction
- pdfplumber, python-docx — file parsing
- Vanilla JS + HTML/CSS — no framework, no build step

## Run Locally
```bash
cd /Users/marshallcreamer/Automatey/platform/forte
DEV_MODE=1 GEMINI_API_KEY="your-gemini-key-here" python3.11 app.py
```
Runs on port 5002 (Cadence=5000, Pitch=5001).
`DEV_MODE=1` auto-logs in as admin@beltonprep.us — skips login screen.

## Login Credentials (BPA)
- admin@beltonprep.us / BPA2025admin!
- staff@beltonprep.us / BPAstaff2025!

## Deploy (Railway)
```bash
# Set env vars in Railway dashboard:
# GEMINI_API_KEY, SECRET_KEY, DATABASE_URL (auto-set by Railway Postgres)
git push origin main  # Railway auto-deploys from GitHub
```
Service name: `forte` · GitHub: github.com/marshallcreamer-eng/forte

## Key Files
```
forte/
├── app.py             # All Flask routes + seed data
├── models.py          # User, Event, Draft (with status + photo_brief)
├── config.py          # SQLite ↔ Postgres switching, env vars
├── data/
│   └── tov_bpa.json   # BPA tone of voice — drives all AI generation
├── templates/
│   ├── dashboard.html  # Landing: "What to post this week"
│   ├── calendar.html   # Monthly calendar grid
│   ├── base.html       # Header, nav
│   └── login.html
├── static/
│   ├── style.css       # Navy + gold BPA theme
│   └── app.js          # Calendar, generator panel, import, status
```

## Platforms Supported
Facebook, Instagram, LinkedIn, X/Twitter, ClassDojo, Newsletter/Email

## Features
- **Dashboard** — events this week + next 2 weeks with per-platform post status
- **Content calendar** — monthly grid, color-coded by category, click to generate
- **Draft generator** — Gemini 2.5 Flash, BPA TOV, all 6 platforms in one click
- **Photo brief** — alongside every draft: exactly what photo to capture
- **Post status** — needs post → draft ready → scheduled → posted per platform
- **Best time to post** — per-platform recommendations shown on every draft card
- **File import** — drag-drop PDF/DOCX/CSV → AI extracts events into calendar
- **Canva button** — copies text + opens Canva template for visual platforms

## Client Data
- School profile: `~/Automatey/clients/bpa/forte/school_profile.json`
- CIE network: `~/Automatey/clients/bpa/cie_network.json`

## Naming
Tool name pending confirmation. Sound theme: Pulse → Pitch → Cadence → **Forte** (or Echo/Tempo/Chorus).

## Working Conventions
Follow `~/Automatey/CLAUDE.md` conventions — plan mode before features, one thing at a time, commit after each piece.
