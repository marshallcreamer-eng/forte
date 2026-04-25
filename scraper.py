"""
scraper.py — Facebook scraping + analysis for Forte
Adapted from Pulse's scrape_free.py + generate_analysis.py
"""
import json, os
from collections import defaultdict
from datetime import datetime, timezone


# ── Facebook Scraping ─────────────────────────────────────────────────────

def scrape_facebook(handle, max_posts=150, cookies_txt=None):
    """
    Scrape public Facebook page. Returns list of post dicts.
    handle: Facebook page slug e.g. 'beltonprep'
    cookies_txt: optional path to cookies.txt file (needed if FB blocks unauthenticated)
    """
    try:
        from facebook_scraper import get_posts
    except ImportError:
        raise RuntimeError("facebook-scraper not installed — run: pip install facebook-scraper")

    kwargs = {
        'pages': 15,
        'options': {
            'posts_per_page': 10,
            'allow_extra_requests': False,
            'progress': False,
        },
    }
    if cookies_txt and os.path.exists(cookies_txt):
        kwargs['cookies'] = cookies_txt

    posts = []
    try:
        for post in get_posts(handle, **kwargs):
            posts.append({
                'id':       post.get('post_id') or post.get('postId', ''),
                'text':     (post.get('text') or post.get('text_en') or '').strip(),
                'time':     str(post.get('time') or ''),
                'likes':    _safe_int(post.get('likes')),
                'comments': _safe_int(post.get('comments')),
                'shares':   _safe_int(post.get('shares')),
                'url':      post.get('post_url') or post.get('url', ''),
                'has_image': bool(post.get('image') or post.get('media')),
                'has_video': bool(post.get('video') or post.get('is_video')),
            })
            if len(posts) >= max_posts:
                break
    except Exception as exc:
        raise RuntimeError(f"Facebook scrape failed: {exc}")

    return posts


# ── Analysis ──────────────────────────────────────────────────────────────

def analyse_facebook(posts):
    """Compute engagement metrics from a list of Facebook post dicts."""
    if not posts:
        return None

    total = len(posts)
    engagements = [
        _safe_int(p.get('likes')) + _safe_int(p.get('comments')) + _safe_int(p.get('shares'))
        for p in posts
    ]
    avg_eng    = sum(engagements) / total
    avg_likes  = sum(_safe_int(p.get('likes'))    for p in posts) / total
    avg_comm   = sum(_safe_int(p.get('comments')) for p in posts) / total
    avg_shares = sum(_safe_int(p.get('shares'))   for p in posts) / total

    # Day-of-week breakdown
    day_eng = defaultdict(list)
    hour_eng = defaultdict(list)
    monthly = defaultdict(lambda: {'posts': 0, 'total_eng': 0})

    for p, eng in zip(posts, engagements):
        ts = p.get('time', '')
        dt = _parse_ts(ts)
        if dt:
            day_eng[dt.strftime('%A')].append(eng)
            hour_eng[dt.hour].append(eng)
            monthly[dt.strftime('%Y-%m')]['posts']     += 1
            monthly[dt.strftime('%Y-%m')]['total_eng'] += eng

    best_day  = _argmax(day_eng)
    best_hour = _argmax(hour_eng)
    best_hour_label = f"{best_hour}:00–{best_hour+1}:00" if best_hour is not None else None

    # Day breakdown sorted Mon→Sun
    day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    day_avgs  = {
        d: round(sum(day_eng[d]) / len(day_eng[d]), 1)
        for d in day_order if d in day_eng
    }

    # Content mix
    photos  = sum(1 for p in posts if p.get('has_image') and not p.get('has_video'))
    videos  = sum(1 for p in posts if p.get('has_video'))
    texts   = total - photos - videos
    content_mix = {
        'Photo': round(photos / total * 100),
        'Video': round(videos / total * 100),
        'Text only': round(texts / total * 100),
    }

    # Top 5 posts
    top5 = sorted(
        [{'text': p.get('text','')[:220], 'date': str(p.get('time',''))[:10],
          'likes': _safe_int(p.get('likes')), 'comments': _safe_int(p.get('comments')),
          'shares': _safe_int(p.get('shares')), 'total': e}
         for p, e in zip(posts, engagements)],
        key=lambda x: x['total'], reverse=True
    )[:5]

    # Date range
    dates = [_parse_ts(p.get('time','')) for p in posts]
    dates = [d for d in dates if d]
    date_from = min(dates).strftime('%b %Y') if dates else '—'
    date_to   = max(dates).strftime('%b %Y') if dates else '—'

    return {
        'total_posts':   total,
        'date_from':     date_from,
        'date_to':       date_to,
        'avg_engagement': round(avg_eng, 1),
        'avg_likes':      round(avg_likes, 1),
        'avg_comments':   round(avg_comm, 1),
        'avg_shares':     round(avg_shares, 1),
        'best_day':       best_day or '—',
        'best_hour':      best_hour_label or '—',
        'day_breakdown':  day_avgs,
        'content_mix':    content_mix,
        'top_posts':      top5,
        'monthly_trend':  {k: v for k, v in sorted(monthly.items())},
    }


def ai_narrative(metrics, school_name, gemini_key):
    """Ask Gemini to summarise the insights in 3 bullet points."""
    try:
        from google import genai as _genai
        client = _genai.Client(api_key=gemini_key)
        prompt = (
            f"You are analysing social media data for {school_name}, a K-8 charter school in SC.\n"
            f"Facebook metrics: {json.dumps(metrics, indent=2)}\n\n"
            f"Write exactly 3 concise bullet points (one sentence each) summarising:\n"
            f"1. Overall posting activity and engagement level\n"
            f"2. Best performing content type or day pattern\n"
            f"3. One specific, actionable recommendation\n"
            f"Be specific with numbers. Start each bullet with '•'."
        )
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[{'role': 'user', 'parts': [{'text': prompt}]}]
        )
        return resp.text.strip()
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────

def _safe_int(v):
    try: return int(v or 0)
    except: return 0

def _parse_ts(ts):
    if not ts: return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return datetime.fromisoformat(str(ts)[:19].replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _argmax(d):
    """Return key with highest average value."""
    if not d: return None
    return max(d, key=lambda k: sum(d[k]) / len(d[k]))
