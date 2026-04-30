from flask import (Flask, render_template, redirect, url_for,
                   request, flash, jsonify, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from datetime import date, datetime, timedelta
from werkzeug.utils import secure_filename
import calendar as cal_module
import json, os, io, uuid, shutil

from config import Config
from models import db, User, Event, Draft, Category, InsightRun


PLATFORM_CONFIG = {
    'facebook':  'Facebook post (100–200 words). Warm community tone. 1–2 emojis. 1–2 hashtags. End with a question or call to action for parents.',
    'instagram': 'Instagram caption (40–80 words). Punchy opening line. 3–5 emojis. 5–8 hashtags. Always start hashtags with #BeltonPrepAcademy.',
    'linkedin':  'LinkedIn post (100–200 words). Professional but warm. Focus on student outcomes and school mission. 3–4 hashtags. No casual slang.',
    'x':         'X/Twitter post (max 260 characters). One punchy sentence or stat. 1–2 hashtags. Optional emoji. Link hook if needed.',
    'classdojo': 'ClassDojo parent announcement (50–120 words). Warm, direct, parent-facing tone. No hashtags. Plain English only. Start with the key information. End with any action parents need to take. Think Friday note from the teacher tone.',
    'email':     'Parent newsletter paragraph (80–150 words). Suitable for a school newsletter or email blast. Clear headline opening, key details, what parents need to know or do. Warm, professional close. No hashtags, minimal emojis. Suitable for copy-paste into Mailchimp, ClassDojo story, or weekly newsletter.',
}

# Best times to post per platform (for school audience in SC)
BEST_TIMES = {
    'facebook':  {'days': 'Wed & Fri', 'time': '6–8 pm',  'note': 'Parents check after work — Sprout Social 2024'},
    'instagram': {'days': 'Mon & Wed', 'time': '6–8 pm',  'note': 'Peak reach for K–12 — Buffer Education Report 2024'},
    'linkedin':  {'days': 'Tue–Thu',   'time': '12–2 pm', 'note': 'Lunch break engagement — LinkedIn internal data'},
    'x':         {'days': 'Weekdays',  'time': '8–10 am', 'note': 'Morning commute window — Sprout Social 2024'},
    'classdojo': {'days': 'Sun–Tue',   'time': '7–9 pm',  'note': 'After school/dinner — parent app usage patterns'},
    'email':     {'days': 'Tue or Thu','time': '7–9 am',  'note': 'Highest open rates for school emails — Mailchimp 2024'},
}
BEST_TIMES_SOURCE = 'General industry benchmarks for K–12 school audiences (Sprout Social, Buffer, Mailchimp 2024). Update once BPA posts regularly — real engagement data will be more accurate.'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please sign in to access Forte.'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── DEV: auto-login ────────────────────────────────────────────────────────
    if app.config.get('DEV_MODE'):
        @app.before_request
        def auto_login():
            if not current_user.is_authenticated:
                user = User.query.filter_by(email='admin@beltonprep.us').first()
                if user:
                    login_user(user)

    # ── Auth ───────────────────────────────────────────────────────────────────

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            email    = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password) and user.is_active:
                login_user(user)
                return redirect(request.args.get('next') or url_for('dashboard'))
            flash('Invalid email or password.', 'error')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    # ── Dashboard ──────────────────────────────────────────────────────────────

    @app.route('/')
    @login_required
    def index():
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        today     = date.today()
        week_end  = today + timedelta(days=6)
        next_end  = today + timedelta(days=20)

        this_week = Event.query.filter(
            Event.date >= today,
            Event.date <= week_end
        ).order_by(Event.date).all()

        coming_up = Event.query.filter(
            Event.date > week_end,
            Event.date <= next_end
        ).order_by(Event.date).all()

        # Attach latest draft per platform to each event
        def enrich(events):
            result = []
            for ev in events:
                drafts_by_platform = {}
                for d in sorted(ev.drafts, key=lambda x: x.generated_at, reverse=True):
                    if d.platform not in drafts_by_platform:
                        drafts_by_platform[d.platform] = d
                result.append({'event': ev, 'drafts': drafts_by_platform})
            return result

        # ── Coverage stats ─────────────────────────────────────────────
        # All upcoming events (from today through end of year)
        upcoming_all = Event.query.filter(Event.date >= today).order_by(Event.date).all()
        events_with_drafts    = [e for e in upcoming_all if e.drafts]
        events_without_drafts = [e for e in upcoming_all if not e.drafts]

        coverage = {
            'total':        len(upcoming_all),
            'has_content':  len(events_with_drafts),
            'needs_content': len(events_without_drafts),
            'pct': round(len(events_with_drafts) / len(upcoming_all) * 100) if upcoming_all else 0,
            # Next 3 events with no content at all
            'gaps': events_without_drafts[:3],
        }

        return render_template('dashboard.html',
            today=today,
            week_start=today,
            week_end=week_end,
            this_week=enrich(this_week),
            coming_up=enrich(coming_up),
            platforms=list(PLATFORM_CONFIG.keys()),
            best_times=BEST_TIMES,
            best_times_source=BEST_TIMES_SOURCE,
            coverage=coverage,
        )

    # ── Calendar View ──────────────────────────────────────────────────────────

    @app.route('/calendar')
    @login_required
    def calendar_view():
        today = date.today()
        try:
            year  = int(request.args.get('year',  today.year))
            month = int(request.args.get('month', today.month))
            if month < 1:   month = 12; year -= 1
            if month > 12:  month = 1;  year += 1
        except (ValueError, TypeError):
            year, month = today.year, today.month

        _, last_day = cal_module.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end   = date(year, month, last_day)

        events = Event.query.filter(
            Event.date >= month_start,
            Event.date <= month_end
        ).order_by(Event.date).all()

        events_by_day = {}
        for ev in events:
            events_by_day.setdefault(ev.date.day, []).append(ev)

        cal_grid   = cal_module.monthcalendar(year, month)
        month_name = cal_module.month_name[month]

        prev_month = month - 1 if month > 1 else 12
        prev_year  = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year  = year if month < 12 else year + 1

        open_event_id = request.args.get('open_event', type=int)

        return render_template('calendar.html',
            year=year, month=month, month_name=month_name,
            cal_grid=cal_grid, events_by_day=events_by_day,
            prev_year=prev_year, prev_month=prev_month,
            next_year=next_year, next_month=next_month,
            today=today,
            open_event_id=open_event_id,
        )

    # ── API: Events CRUD ───────────────────────────────────────────────────────

    @app.route('/api/events', methods=['GET'])
    @login_required
    def api_events_list():
        year  = request.args.get('year',  date.today().year,  type=int)
        month = request.args.get('month', date.today().month, type=int)
        _, last_day = cal_module.monthrange(year, month)
        events = Event.query.filter(
            Event.date >= date(year, month, 1),
            Event.date <= date(year, month, last_day)
        ).order_by(Event.date).all()
        return jsonify([e.to_dict() for e in events])

    @app.route('/api/events', methods=['POST'])
    @login_required
    def api_create_event():
        data = request.get_json(silent=True) or {}
        if not data.get('title') or not data.get('date'):
            return jsonify({'error': 'title and date are required'}), 400
        try:
            ev_date = date.fromisoformat(data['date'])
        except ValueError:
            return jsonify({'error': 'invalid date format (use YYYY-MM-DD)'}), 400
        ev = Event(
            title=data['title'].strip()[:200],
            description=data.get('description', '').strip(),
            date=ev_date,
            category=data.get('category', 'community'),
            source='manual',
            created_by=current_user.id,
        )
        db.session.add(ev)
        db.session.commit()
        return jsonify(ev.to_dict()), 201

    @app.route('/api/events/<int:event_id>', methods=['PUT'])
    @login_required
    def api_update_event(event_id):
        ev   = Event.query.get_or_404(event_id)
        data = request.get_json(silent=True) or {}
        if 'title'       in data: ev.title       = data['title'].strip()[:200]
        if 'description' in data: ev.description = data['description'].strip()
        if 'category'    in data: ev.category    = data['category']
        if 'date'        in data:
            try:   ev.date = date.fromisoformat(data['date'])
            except ValueError: return jsonify({'error': 'invalid date'}), 400
        db.session.commit()
        return jsonify(ev.to_dict())

    @app.route('/api/events/<int:event_id>', methods=['DELETE'])
    @login_required
    def api_delete_event(event_id):
        ev = Event.query.get_or_404(event_id)
        db.session.delete(ev)
        db.session.commit()
        return jsonify({'ok': True})

    # ── API: Draft Status ──────────────────────────────────────────────────────

    @app.route('/api/drafts/<int:draft_id>/status', methods=['PUT'])
    @login_required
    def api_update_draft_status(draft_id):
        d    = Draft.query.get_or_404(draft_id)
        data = request.get_json(silent=True) or {}
        new_status = data.get('status')
        valid = ('needs_post', 'draft_ready', 'scheduled', 'posted')
        if new_status not in valid:
            return jsonify({'error': f'status must be one of {valid}'}), 400
        d.status = new_status
        if new_status == 'posted' and not d.copied_at:
            d.copied_at = datetime.utcnow()
        if 'scheduled_for' in data and data['scheduled_for']:
            try:
                d.scheduled_for = datetime.fromisoformat(data['scheduled_for'])
            except ValueError:
                pass
        db.session.commit()
        return jsonify(d.to_dict())

    # ── API: File Import ────────────────────────────────────────────────────────

    @app.route('/api/import', methods=['POST'])
    @login_required
    def api_import():
        if 'file' not in request.files:
            return jsonify({'error': 'no file uploaded'}), 400
        f        = request.files['file']
        filename = (f.filename or '').lower()
        text     = ''

        try:
            if filename.endswith('.pdf'):
                import pdfplumber
                with pdfplumber.open(io.BytesIO(f.read())) as pdf:
                    text = '\n'.join(p.extract_text() or '' for p in pdf.pages)
            elif filename.endswith('.docx'):
                from docx import Document
                doc  = Document(io.BytesIO(f.read()))
                text = '\n'.join(p.text for p in doc.paragraphs)
            elif filename.endswith(('.csv', '.txt')):
                text = f.read().decode('utf-8', errors='ignore')
            else:
                return jsonify({'error': 'Unsupported file. Use PDF, DOCX, CSV, or TXT.'}), 400
        except Exception as exc:
            return jsonify({'error': f'Could not read file: {exc}'}), 400

        if not text.strip():
            return jsonify({'error': 'No readable text found in this file.'}), 400

        try:
            from google import genai as _genai
            client = _genai.Client(api_key=app.config['GEMINI_API_KEY'])
            prompt = (
                f"Extract all school events, important dates, and activities from the text below.\n"
                f"Return ONLY a JSON array — no markdown, no explanation.\n"
                f"Each item: {{\"title\": \"event name\", \"date\": \"YYYY-MM-DD\", "
                f"\"description\": \"brief description\", "
                f"\"category\": \"one of: holiday|admissions|academic|community|achievement\"}}\n"
                f"Omit items with no determinable date. Today is {date.today().isoformat()}.\n\n"
                f"Text:\n{text[:4000]}"
            )
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[{'role': 'user', 'parts': [{'text': prompt}]}]
            )
            raw = resp.text.strip()
            if raw.startswith('```'):
                raw = '\n'.join(raw.split('\n')[1:])
                if raw.endswith('```'): raw = raw[:-3]
            extracted = json.loads(raw.strip())
        except Exception as exc:
            return jsonify({'error': f'AI extraction failed: {exc}'}), 500

        return jsonify({'events': extracted})

    @app.route('/api/import/confirm', methods=['POST'])
    @login_required
    def api_import_confirm():
        items = (request.get_json(silent=True) or {}).get('events', [])
        added = 0
        for item in items:
            try:
                ev = Event(
                    title=item['title'][:200],
                    description=item.get('description', '')[:500],
                    date=date.fromisoformat(item['date']),
                    category=item.get('category', 'community'),
                    source='imported',
                    created_by=current_user.id,
                )
                db.session.add(ev)
                added += 1
            except Exception:
                continue
        db.session.commit()
        return jsonify({'ok': True, 'added': added})

    # ── API: Draft Generation ──────────────────────────────────────────────────

    @app.route('/api/generate', methods=['POST'])
    @login_required
    def api_generate():
        data          = request.get_json(silent=True) or {}
        event_id      = data.get('event_id')
        tone_override = data.get('tone_override', '').strip()
        platforms     = data.get('platforms', list(PLATFORM_CONFIG.keys()))

        ev = Event.query.get(event_id) if event_id else None
        event_text   = data.get('event_text', '') or (
            f'{ev.title}. {ev.description}'.strip() if ev else ''
        )
        content_type = data.get('content_type', 'photo')  # text | photo | video
        if not event_text:
            return jsonify({'error': 'event_text is required'}), 400

        tov = _build_tov_prompt(app)

        # Single batched API call for all platforms + photo brief
        try:
            results, photo_brief = _generate_all(platforms, event_text, tone_override, tov, content_type, app)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 500

        if ev:
            for platform, content in results.items():
                if not content.startswith('[Generation error'):
                    # Replace latest draft for this platform if it exists
                    existing = Draft.query.filter_by(
                        event_id=ev.id, platform=platform
                    ).order_by(Draft.generated_at.desc()).first()
                    if existing and existing.status in ('draft_ready', 'needs_post'):
                        existing.content       = content
                        existing.photo_brief   = photo_brief
                        existing.tone_override = tone_override
                        existing.generated_at  = datetime.utcnow()
                        existing.status        = 'draft_ready'
                    else:
                        db.session.add(Draft(
                            event_id=ev.id,
                            platform=platform,
                            content=content,
                            photo_brief=photo_brief,
                            tone_override=tone_override,
                            status='draft_ready',
                        ))
            db.session.commit()

        return jsonify({
            'drafts':      results,
            'photo_brief': photo_brief,
            'best_times':  BEST_TIMES,
            'event':       ev.to_dict() if ev else None,
        })

    @app.route('/api/drafts/<int:event_id>', methods=['GET'])
    @login_required
    def api_get_drafts(event_id):
        drafts = Draft.query.filter_by(event_id=event_id).order_by(Draft.generated_at.desc()).all()
        return jsonify([d.to_dict() for d in drafts])

    # ── Insights ───────────────────────────────────────────────────────────

    @app.route('/insights')
    @login_required
    def insights():
        latest  = InsightRun.query.filter_by(status='done').order_by(
            InsightRun.started_at.desc()).first()
        running = InsightRun.query.filter_by(status='running').first()
        return render_template('insights.html', latest=latest, running=running)

    @app.route('/api/insights/run', methods=['POST'])
    @login_required
    def api_insights_run():
        if InsightRun.query.filter_by(status='running').first():
            return jsonify({'error': 'A scrape is already running'}), 409

        run = InsightRun(status='running', platform='facebook')
        db.session.add(run)
        db.session.commit()
        run_id = run.id

        import threading
        def _scrape():
            with app.app_context():
                r = InsightRun.query.get(run_id)
                try:
                    from scraper import scrape_facebook, analyse_facebook, ai_narrative
                    cookies = os.path.join(app.root_path, 'data', 'fb_cookies.txt')
                    posts   = scrape_facebook('beltonprep', max_posts=200,
                                              cookies_txt=cookies if os.path.exists(cookies) else None)
                    metrics = analyse_facebook(posts)
                    narr    = ai_narrative(metrics, 'Belton Preparatory Academy',
                                          app.config['GEMINI_API_KEY']) if metrics else None
                    r.status     = 'done'
                    r.post_count = len(posts)
                    r.results    = json.dumps(metrics)
                    r.narrative  = narr
                    r.finished_at = datetime.utcnow()
                except Exception as exc:
                    r.status = 'failed'
                    r.error  = str(exc)
                    r.finished_at = datetime.utcnow()
                db.session.commit()

        threading.Thread(target=_scrape, daemon=True).start()
        return jsonify({'ok': True, 'run_id': run_id})

    @app.route('/api/insights/status', methods=['GET'])
    @login_required
    def api_insights_status():
        running = InsightRun.query.filter_by(status='running').first()
        latest  = InsightRun.query.filter_by(status='done').order_by(
            InsightRun.started_at.desc()).first()
        return jsonify({
            'running':      running is not None,
            'latest_id':    latest.id if latest else None,
            'latest_date':  latest.started_at.strftime('%b %d, %Y %H:%M') if latest else None,
            'post_count':   latest.post_count if latest else 0,
        })

    @app.route('/api/insights/upload', methods=['POST'])
    @login_required
    def api_insights_upload():
        """Accept manually exported JSON post data as fallback if scraping is blocked."""
        if 'file' not in request.files:
            return jsonify({'error': 'no file'}), 400
        f    = request.files['file']
        try:
            posts = json.loads(f.read().decode('utf-8'))
            if not isinstance(posts, list):
                return jsonify({'error': 'expected a JSON array of posts'}), 400
        except Exception as exc:
            return jsonify({'error': f'could not parse file: {exc}'}), 400

        from scraper import analyse_facebook, ai_narrative
        # Normalise common export formats
        normalised = []
        for p in posts:
            normalised.append({
                'text':      p.get('text') or p.get('message') or '',
                'time':      p.get('time') or p.get('created_time') or p.get('timestamp') or '',
                'likes':     p.get('likes') or p.get('like_count') or 0,
                'comments':  p.get('comments') or p.get('comment_count') or 0,
                'shares':    p.get('shares') or p.get('share_count') or 0,
                'has_image': bool(p.get('image') or p.get('attachments') or p.get('media')),
                'has_video': bool(p.get('video') or p.get('is_video')),
            })

        metrics = analyse_facebook(normalised)
        narr    = ai_narrative(metrics, 'Belton Preparatory Academy', app.config['GEMINI_API_KEY']) if metrics else None

        run = InsightRun(
            status='done', platform='facebook',
            post_count=len(normalised),
            results=json.dumps(metrics),
            narrative=narr,
            finished_at=datetime.utcnow(),
        )
        db.session.add(run)
        db.session.commit()
        return jsonify({'ok': True, 'post_count': len(normalised)})

    # ── Settings ───────────────────────────────────────────────────────────

    @app.route('/settings')
    @login_required
    def settings():
        categories = Category.query.order_by(Category.sort_order, Category.name).all()
        tov_path   = os.path.join(app.root_path, 'data', 'tov_bpa.json')
        tov        = {}
        try:
            with open(tov_path) as f:
                tov = json.load(f)
        except Exception:
            pass

        # Brand assets
        brand_dir = os.path.join(app.root_path, 'data', 'uploads', 'brand')
        os.makedirs(brand_dir, exist_ok=True)

        # Pre-populate with BPA logo on first run
        bpa_logo_src = os.path.join(app.root_path, 'static', 'bpa-logo.png')
        bpa_logo_dst = os.path.join(brand_dir, 'bpa-logo.png')
        if os.path.exists(bpa_logo_src) and not os.path.exists(bpa_logo_dst):
            shutil.copy2(bpa_logo_src, bpa_logo_dst)

        brand_assets = [
            {'filename': f, 'url': url_for('serve_upload', filename=f'brand/{f}')}
            for f in sorted(os.listdir(brand_dir))
            if not f.startswith('.')
        ]

        return render_template('settings.html', categories=categories, tov=tov,
                               brand_assets=brand_assets)

    # ── API: Categories CRUD ───────────────────────────────────────────────

    @app.route('/api/categories', methods=['GET'])
    @login_required
    def api_categories_list():
        cats = Category.query.order_by(Category.sort_order, Category.name).all()
        return jsonify([c.to_dict() for c in cats])

    @app.route('/api/categories', methods=['POST'])
    @login_required
    def api_create_category():
        data = request.get_json(silent=True) or {}
        name  = data.get('name', '').strip()
        color = data.get('color', '#64748b').strip()
        if not name:
            return jsonify({'error': 'name is required'}), 400
        slug = name.lower().replace(' ', '_').replace('&', 'and')
        slug = ''.join(c for c in slug if c.isalnum() or c == '_')[:30]
        if Category.query.filter_by(slug=slug).first():
            slug = f"{slug}_{Category.query.count()}"
        cat = Category(name=name, slug=slug, color=color, is_preset=False)
        db.session.add(cat)
        db.session.commit()
        return jsonify(cat.to_dict()), 201

    @app.route('/api/categories/<int:cat_id>', methods=['PUT'])
    @login_required
    def api_update_category(cat_id):
        cat  = Category.query.get_or_404(cat_id)
        data = request.get_json(silent=True) or {}
        if 'name'  in data: cat.name  = data['name'].strip()
        if 'color' in data: cat.color = data['color'].strip()
        db.session.commit()
        return jsonify(cat.to_dict())

    @app.route('/api/categories/<int:cat_id>', methods=['DELETE'])
    @login_required
    def api_delete_category(cat_id):
        cat = Category.query.get_or_404(cat_id)
        if cat.is_preset:
            return jsonify({'error': 'Cannot delete a preset category'}), 400
        db.session.delete(cat)
        db.session.commit()
        return jsonify({'ok': True})

    # ── Context processor — inject categories into all pages

    @app.context_processor
    def inject_globals():
        try:
            cats = Category.query.order_by(Category.sort_order).all()
        except Exception:
            cats = []
        return {
            'categories': cats,
            'cat_colors': {c.slug: c.color for c in cats},
        }

    # ── File uploads ───────────────────────────────────────────────────────

    UPLOAD_DIR = os.path.join(app.root_path, 'data', 'uploads')

    @app.route('/uploads/<path:filename>')
    @login_required
    def serve_upload(filename):
        return send_from_directory(UPLOAD_DIR, filename)

    @app.route('/api/photos', methods=['POST'])
    @login_required
    def api_upload_photo():
        if 'file' not in request.files:
            return jsonify({'error': 'no file'}), 400
        f = request.files['file']
        ext = (f.filename or '').rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'):
            return jsonify({'error': 'image files only (jpg, png, gif, webp)'}), 400
        event_id = request.form.get('event_id', 'freeform')
        filename = f'{event_id}_{uuid.uuid4().hex[:8]}.{ext}'
        photos_dir = os.path.join(UPLOAD_DIR, 'photos')
        os.makedirs(photos_dir, exist_ok=True)
        f.save(os.path.join(photos_dir, filename))
        return jsonify({'ok': True, 'filename': filename,
                        'url': url_for('serve_upload', filename=f'photos/{filename}')})

    @app.route('/api/photos/<filename>', methods=['DELETE'])
    @login_required
    def api_delete_photo(filename):
        path = os.path.join(UPLOAD_DIR, 'photos', secure_filename(filename))
        if os.path.exists(path): os.remove(path)
        return jsonify({'ok': True})

    @app.route('/api/brand/assets', methods=['POST'])
    @login_required
    def api_upload_brand_asset():
        if 'file' not in request.files:
            return jsonify({'error': 'no file'}), 400
        f = request.files['file']
        ext = (f.filename or '').rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'pdf'):
            return jsonify({'error': 'unsupported file type'}), 400
        brand_dir = os.path.join(UPLOAD_DIR, 'brand')
        os.makedirs(brand_dir, exist_ok=True)
        filename = secure_filename(f.filename)
        f.save(os.path.join(brand_dir, filename))
        return jsonify({'ok': True, 'filename': filename,
                        'url': url_for('serve_upload', filename=f'brand/{filename}')})

    @app.route('/api/brand/assets/<filename>', methods=['DELETE'])
    @login_required
    def api_delete_brand_asset(filename):
        path = os.path.join(UPLOAD_DIR, 'brand', secure_filename(filename))
        if os.path.exists(path): os.remove(path)
        return jsonify({'ok': True})

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'app': 'Forte by Automatey'})

    # ── Init DB + Seed ─────────────────────────────────────────────────────────

    with app.app_context():
        db.create_all()   # creates categories table automatically
        _migrate_db(db)
        _seed_defaults()

    return app


# ── Helpers ────────────────────────────────────────────────────────────────────

def _migrate_db(db):
    """Add new columns to existing SQLite DB if they don't exist yet."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    existing  = {c['name'] for c in inspector.get_columns('drafts')}
    with db.engine.connect() as conn:
        if 'status' not in existing:
            conn.execute(text("ALTER TABLE drafts ADD COLUMN status TEXT DEFAULT 'draft_ready'"))
        if 'scheduled_for' not in existing:
            conn.execute(text("ALTER TABLE drafts ADD COLUMN scheduled_for DATETIME"))
        if 'photo_brief' not in existing:
            conn.execute(text("ALTER TABLE drafts ADD COLUMN photo_brief TEXT DEFAULT ''"))
        conn.commit()


def _build_tov_prompt(app):
    tov_path = os.path.join(app.root_path, 'data', 'tov_bpa.json')
    try:
        with open(tov_path) as f:
            t = json.load(f)
        bp      = ', '.join(t.get('brand_personality', []))
        pillars = ', '.join(t.get('content_pillars', []))
        do      = ' '.join(t.get('what_to_always_do', []))
        dont    = ' '.join(t.get('what_to_never_do', []))
        pref    = ', '.join(t.get('vocabulary', {}).get('preferred_words', []))
        phrases = ', '.join(t.get('vocabulary', {}).get('signature_phrases', []))
        emoji   = t.get('emoji_use', 'moderate')
        htag    = t.get('hashtag_style', '#BeltonPrepAcademy first, then topic hashtags')
        return (
            f"You are a social media content writer for Belton Preparatory Academy (BPA), "
            f"a free public classical charter school in Belton, South Carolina, serving grades K–8. "
            f"Brand personality: {bp}. Content pillars: {pillars}. "
            f"Always: {do}. Never: {dont}. "
            f"Preferred words: {pref}. Signature phrases: {phrases}. "
            f"Emoji use: {emoji}. Hashtag style: {htag}."
        )
    except Exception:
        return (
            "You are a social media writer for Belton Preparatory Academy, "
            "a free public classical charter school in Belton, SC serving K–8."
        )


def _gemini_call(app, prompt, retries=3):
    """Single Gemini call with automatic retry on 429 rate-limit errors."""
    import time
    from google import genai as _genai
    client = _genai.Client(api_key=app.config['GEMINI_API_KEY'])
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[{'role': 'user', 'parts': [{'text': prompt}]}]
            )
            return resp.text.strip()
        except Exception as exc:
            msg = str(exc)
            if '429' in msg and attempt < retries - 1:
                wait = int(attempt * 10 + 8)   # 8s, 18s, 28s
                time.sleep(wait)
            else:
                raise


def _generate_all(platforms, event_text, tone_override, tov, content_type, app):
    """
    Single API call that produces all platform drafts + photo brief at once.
    Reduces N calls down to 1, staying well within the free-tier 5 RPM limit.
    """
    tone_extra = f'\nTONE OVERRIDE for all posts: {tone_override}.' if tone_override else ''

    media_context = {
        'photo': 'This post WILL be accompanied by a photo. Write captions that reference/complement the image. The photo brief should describe exactly what to shoot.',
        'video': 'This post WILL include a short video clip. Write captions that hook viewers in the first line and encourage them to watch. The photo brief should describe exactly what video to record (length, what to capture, any text overlay suggestions).',
        'text':  'This post will be TEXT ONLY — no photo or video. The content must stand on its own without any image. Skip the photo brief or note it is not applicable.',
    }.get(content_type, '')

    platform_specs = '\n'.join(
        f'- {p.upper()}: {PLATFORM_CONFIG[p]}'
        for p in platforms if p in PLATFORM_CONFIG
    )

    brief_instruction = (
        'Also write a PHOTO_BRIEF (2-3 sentences: shot type, who is in frame, mood, any text overlay if video).'
        if content_type in ('photo', 'video')
        else 'Set photo_brief to an empty string.'
    )

    prompt = (
        f"{tov}{tone_extra}\n\n"
        f"MEDIA CONTEXT: {media_context}\n\n"
        f"Write social media posts for the following school moment:\n\n{event_text}\n\n"
        f"Generate one post per platform below. {brief_instruction}\n\n"
        f"Platform requirements:\n{platform_specs}\n\n"
        f"Reply with ONLY a JSON object — no markdown, no code fences — in this exact format:\n"
        f'{{"photo_brief": "...", '
        + ', '.join(f'"{p}": "..."' for p in platforms if p in PLATFORM_CONFIG)
        + '}'
    )

    raw = _gemini_call(app, prompt)

    # Strip markdown fences if present
    if raw.startswith('```'):
        lines = raw.split('\n')
        raw = '\n'.join(lines[1:])
        if raw.rstrip().endswith('```'):
            raw = raw.rstrip()[:-3]

    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        # Fallback: extract JSON object from response
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
        else:
            raise RuntimeError('Could not parse JSON from Gemini response')

    photo_brief = parsed.pop('photo_brief', '')
    results = {p: parsed.get(p, '') for p in platforms if p in PLATFORM_CONFIG}
    return results, photo_brief


def _seed_categories():
    if Category.query.count() > 0:
        return
    presets = [
        ('Community',          'community',  '#d97706', True,  1),
        ('Academic',           'academic',   '#2563eb', True,  2),
        ('Admissions',         'admissions', '#16a34a', True,  3),
        ('Achievement',        'achievement','#7c3aed', True,  4),
        ('Holiday',            'holiday',    '#ef4444', True,  5),
        ('Sports & Activities','sports',     '#0891b2', True,  6),
        ('Staff & Faculty',    'staff',      '#9333ea', True,  7),
    ]
    for name, slug, color, is_preset, sort_order in presets:
        db.session.add(Category(name=name, slug=slug, color=color,
                                is_preset=is_preset, sort_order=sort_order))
    db.session.commit()


def _seed_defaults():
    if not User.query.filter_by(email='admin@beltonprep.us').first():
        u = User(name='BPA Admin', email='admin@beltonprep.us', role='admin')
        u.set_password('BPA2025admin!')
        db.session.add(u)

    if not User.query.filter_by(email='staff@beltonprep.us').first():
        u = User(name='BPA Staff', email='staff@beltonprep.us', role='staff')
        u.set_password('BPAstaff2025!')
        db.session.add(u)

    if Event.query.count() == 0:
        _seed_events()

    _seed_categories()
    db.session.commit()


def _seed_events():
    rows = [
        # Aug 2025
        ('Uniform Reminder — Back to School', date(2025, 8, 11),
         'Back to school uniform reminder — navy and khaki, BPA-approved items from Palmetto Screen Print & Embroidery in Anderson.',
         'community'),
        ('Meet the Teacher Night', date(2025, 8, 14),
         "Meet your child's teacher and tour the classroom before the school year begins.", 'community'),
        ('First Day of School', date(2025, 8, 18),
         'Welcome back, Knights! K–8 students return for the 2025–26 school year.', 'community'),
        # Sep 2025
        ('Labor Day — School Closed', date(2025, 9, 1),
         'School is closed in observance of Labor Day. Enjoy the long weekend, BPA families!', 'holiday'),
        ('Constitution Day', date(2025, 9, 17),
         'Celebrating Constitution Day — a special civics opportunity in our classical curriculum.', 'academic'),
        ('Open Enrollment Teaser', date(2025, 9, 22),
         'Mark your calendars — BPA open enrollment for 2026–27 opens November 1!', 'admissions'),
        # Oct 2025
        ('FBLA / Beta Club Kickoff', date(2025, 10, 7),
         'Middle school clubs are starting up — FBLA, Beta Club, Knights Society, and more!', 'academic'),
        ('Fall Picture Day', date(2025, 10, 9),
         'Smile, Knights! Fall picture day for all K–8 students.', 'community'),
        ('Open Enrollment Countdown', date(2025, 10, 27),
         'Just 5 days until BPA open enrollment opens! Apply for 2026–27 starting November 1.', 'admissions'),
        ('Halloween / Fall Festival', date(2025, 10, 31),
         'BPA Fall Festival — costumes, fun, and community spirit for our Knights!', 'community'),
        # Nov 2025
        ('Open Enrollment Opens', date(2025, 11, 1),
         'Enrollment for 2026–27 is now OPEN! Apply at beltonprep.us — tuition-free, open to all South Carolina families.', 'admissions'),
        ('Veterans Day', date(2025, 11, 11),
         'Thank you to all who serve and have served. BPA honours our veterans today.', 'community'),
        ('Open Enrollment — Week 3 Reminder', date(2025, 11, 17),
         'Enrollment for 2026–27 is open! Share with any SC family looking for a free classical education.', 'admissions'),
        ('Thanksgiving Feast', date(2025, 11, 20),
         'Our annual Thanksgiving Feast — students and staff celebrate together.', 'community'),
        ('Thanksgiving Break Begins', date(2025, 11, 26),
         'Happy Thanksgiving from all of us at BPA! Enjoy time with your families.', 'holiday'),
        # Dec 2025
        ('Open Enrollment Mid-Season Reminder', date(2025, 12, 1),
         'Remember: BPA open enrollment for 2026–27 closes February 1. Apply today at beltonprep.us!', 'admissions'),
        ('Winter Concert / Holiday Performance', date(2025, 12, 11),
         'Our BPA students take the stage for the annual winter performance. Family and friends welcome!', 'community'),
        ('Winter Break Begins', date(2025, 12, 22),
         'Happy holidays from Belton Preparatory Academy! See our Knights in January.', 'holiday'),
        # Jan 2026
        ('Students Return — Second Semester', date(2026, 1, 5),
         "Welcome back, Knights! Second semester begins — let's finish the year strong.", 'community'),
        ('MLK Day — School Closed', date(2026, 1, 19),
         '"Intelligence plus character — that is the goal of true education." — Dr. Martin Luther King Jr.', 'holiday'),
        ('Open Enrollment Final Push', date(2026, 1, 26),
         "Only 6 days left! BPA enrollment for 2026–27 closes February 1. Don't miss your chance — beltonprep.us", 'admissions'),
        # Feb 2026
        ('Open Enrollment Closes — Last Day', date(2026, 2, 1),
         'Today is the last day to apply for 2026–27! Submit your application at beltonprep.us.', 'admissions'),
        ('Black History Month', date(2026, 2, 2),
         'February is Black History Month. BPA celebrates the contributions and achievements of Black Americans throughout the month.', 'community'),
        ("Valentine's Day", date(2026, 2, 14),
         "Happy Valentine's Day from BPA — celebrating the community that makes our school so special.", 'community'),
        ('FBLA Regional Competition', date(2026, 2, 20),
         'BPA middle school FBLA members compete at the regional level — go Knights!', 'achievement'),
        # Mar 2026
        ('Read Across America / Dr. Seuss Week', date(2026, 3, 2),
         'Celebrating Read Across America and the love of reading with activities for all grade levels.', 'academic'),
        ('Pi Day', date(2026, 3, 14),
         'Happy Pi Day! Our Eureka Math knights celebrate 3.14159… in style.', 'academic'),
        ('Spring Picture Day', date(2026, 3, 19),
         'Spring picture day — looking sharp, BPA Knights!', 'community'),
        ('Spring Break Begins', date(2026, 3, 23),
         'Spring break is here! Enjoy the time with your families.', 'holiday'),
        # Apr 2026
        ('SC Ready State Testing Begins', date(2026, 4, 6),
         "SC Ready state testing begins. We believe in you, BPA students — you've worked hard all year!", 'academic'),
        ('Earth Day', date(2026, 4, 22),
         'Happy Earth Day! BPA students learn to be good stewards of our world.', 'community'),
        ('Spring STEM Showcase', date(2026, 4, 23),
         "BPA's spring STEM showcase — robotics, science projects, and innovation from our young Knights.", 'achievement'),
        # May 2026
        ('Teacher Appreciation Week', date(2026, 5, 4),
         'This week we celebrate the incredible teachers who shape our students every single day. Thank you, BPA faculty!', 'community'),
        ('Beta Club / FBLA Awards', date(2026, 5, 21),
         'Congratulations to our Beta Club and FBLA members on a fantastic year of achievement!', 'achievement'),
        ('Memorial Day — School Closed', date(2026, 5, 25),
         'School is closed in observance of Memorial Day. We honour all who gave the ultimate sacrifice.', 'holiday'),
        # Jun 2026
        ('8th Grade Promotion Ceremony', date(2026, 6, 4),
         "Congratulations to our 8th grade Knights — you've earned this! Join us to celebrate.", 'achievement'),
        ('Last Day of School', date(2026, 6, 11),
         'What a year! Thank you to every student, family, and staff member who made 2025–26 so special.', 'community'),
        ('Summer Reading Encouragement', date(2026, 6, 15),
         "Keep the learning going this summer! Check out BPA's summer reading recommendations for all grade levels.", 'academic'),
        ('Enrollment Preview 2027–28', date(2026, 6, 18),
         'Save the date: BPA enrollment for 2027–28 opens November 1, 2026. Spread the word!', 'admissions'),
    ]
    for title, ev_date, desc, cat in rows:
        db.session.add(Event(
            title=title, description=desc, date=ev_date,
            category=cat, source='preloaded',
        ))


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=True, host='0.0.0.0', port=port)
