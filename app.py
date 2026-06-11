from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
import json, os, threading, time, logging, re

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

DATA_DIR = os.environ.get('DATA_DIR', '/data')
CACHE_FILE = os.path.join(DATA_DIR, 'schedule.json')
COUNCIL_ID = os.environ.get('COUNCIL_ID', '')
COUNCIL_URL = f'https://app.ipswich.gov.uk/bin-collection/months/{COUNCIL_ID}'

BINS = {
    'black': {'body': '#1e293b', 'lid': '#0f172a', 'label': 'Black',  'detail': 'General waste',  'pattern': 'solid'},
    'grey':  {'body': '#94a3b8', 'lid': '#64748b', 'label': 'Grey',   'detail': 'Food waste',     'pattern': 'diagonal'},
    'brown': {'body': '#b45309', 'lid': '#78350f', 'label': 'Brown',  'detail': 'Garden waste',   'pattern': 'cross'},
    'blue':  {'body': '#2563eb', 'lid': '#1e40af', 'label': 'Blue',   'detail': 'Plastics',       'pattern': 'dots'},
    'green': {'body': '#16a34a', 'lid': '#14532d', 'label': 'Green',  'detail': 'Paper & card',   'pattern': 'horizontal'},
}

MONTH_NAMES = ['January','February','March','April','May','June',
               'July','August','September','October','November','December']

def classify_bins(text):
    t = text.lower()
    bins = []
    if 'food' in t or 'caddy' in t:
        bins.append('grey')
    if 'refuse' in t or 'black' in t:
        bins.append('black')
    if 'garden' in t or 'brown' in t:
        bins.append('brown')
    if 'blue' in t:
        bins.append('blue')
    if 'green' in t or 'paper' in t:
        bins.append('green')
    return list(dict.fromkeys(bins))

def scrape_schedule():
    if not COUNCIL_ID:
        logger.error('COUNCIL_ID environment variable is not set')
        return None
    try:
        resp = requests.get(COUNCIL_URL, timeout=15,
                            headers={'User-Agent': 'Mozilla/5.0 (compatible; BinDayBot/1.0)'})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        lines = [l.strip() for l in soup.get_text(separator='\n').split('\n') if l.strip()]

        collections = []
        current_month = current_year = None

        for line in lines:
            for i, month in enumerate(MONTH_NAMES):
                if month in line:
                    m = re.search(r'(\d{4})', line)
                    if m:
                        current_month = i + 1
                        current_year = int(m.group(1))
                        break

            if current_month and current_year:
                m = re.match(r'^(\d{1,2})(?:st|nd|rd|th)', line)
                if m:
                    day = int(m.group(1))
                    bins = classify_bins(line)
                    if bins:
                        try:
                            d = date(current_year, current_month, day)
                            iso = d.isoformat()
                            if not any(c['date'] == iso for c in collections):
                                collections.append({'date': iso, 'bins': bins})
                        except ValueError:
                            pass

        collections.sort(key=lambda x: x['date'])
        logger.info(f'Scraped {len(collections)} collections')
        return collections or None
    except Exception as e:
        logger.error(f'Scrape error: {e}')
        return None

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {'collections': [], 'updated': None}

def save_cache(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def refresh():
    cols = scrape_schedule()
    if cols:
        save_cache({'collections': cols, 'updated': datetime.now().isoformat()})
        logger.info('Cache saved')
    else:
        logger.warning('Scrape returned no data; keeping existing cache')

def background_loop():
    while True:
        refresh()
        time.sleep(86400)

def upcoming_collections(n=4):
    cache = load_cache()
    today = date.today()
    future = [c for c in cache['collections'] if date.fromisoformat(c['date']) >= today]
    future.sort(key=lambda x: x['date'])
    return future[:n], cache.get('updated')

def fmt_date(iso_str):
    d = date.fromisoformat(iso_str)
    suffix = {1:'st',2:'nd',3:'rd'}.get(d.day % 10 if d.day not in (11,12,13) else 0, 'th')
    return d.strftime(f'%A {d.day}{suffix} %B %Y')

def fmt_date_short(iso_str):
    return date.fromisoformat(iso_str).strftime('%-d %b')

@app.route('/')
def index():
    if not COUNCIL_ID:
        return render_template('index.html',
            nxt=None, coll_date_fmt=None, urgency='unknown',
            status='Set your COUNCIL_ID environment variable to get started — see README',
            upcoming=[], updated=None,
            theme=request.args.get('theme', 'color'), bins=BINS)
    upcoming, updated = upcoming_collections(4)
    today = date.today()
    nxt = upcoming[0] if upcoming else None

    urgency = status = coll_date_fmt = None

    if nxt:
        coll_date = date.fromisoformat(nxt['date'])
        coll_date_fmt = fmt_date(nxt['date'])
        days_to_collection = (coll_date - today).days
        days_to_wednesday = days_to_collection - 1  # put-out night

        if days_to_collection == 0:
            urgency, status = 'today', 'Collection today — bring the bin back in!'
        elif days_to_wednesday == 0:
            urgency, status = 'tonight', 'Put out tonight!'
        elif days_to_wednesday == 1:
            urgency, status = 'soon', 'Put out tomorrow night'
        elif days_to_wednesday <= 3:
            urgency, status = 'upcoming', f'Put out in {days_to_wednesday} days'
        else:
            urgency, status = 'later', f'Next collection in {days_to_collection} days'
    else:
        urgency, status = 'unknown', 'No schedule data available'

    upcoming_display = []
    for c in upcoming[1:3]:
        labels = ' · '.join(BINS[b]['label'] for b in c['bins'] if b in BINS)
        upcoming_display.append({
            'date_short': fmt_date_short(c['date']),
            'bins': c['bins'],
            'labels': labels,
        })

    updated_str = None
    if updated:
        try:
            updated_str = datetime.fromisoformat(updated).strftime('%-d %b at %H:%M')
        except Exception:
            updated_str = updated

    theme = request.args.get('theme', 'color')

    return render_template('index.html',
        nxt=nxt,
        coll_date_fmt=coll_date_fmt,
        urgency=urgency,
        status=status,
        upcoming=upcoming_display,
        updated=updated_str,
        theme=theme,
        bins=BINS,
    )

@app.route('/debug/raw')
def debug_raw():
    if not COUNCIL_ID:
        return 'COUNCIL_ID not set', 400
    try:
        resp = requests.get(COUNCIL_URL, timeout=15,
                            headers={'User-Agent': 'Mozilla/5.0 (compatible; BinDayBot/1.0)'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        lines = [l.strip() for l in soup.get_text(separator='\n').split('\n') if l.strip()]
        return '<pre>' + '\n'.join(lines[:200]) + '</pre>'
    except Exception as e:
        return str(e), 500

@app.route('/api/schedule')
def api_schedule():
    upcoming, updated = upcoming_collections(20)
    return jsonify({'collections': upcoming, 'updated': updated})

@app.route('/refresh', methods=['POST'])
def manual_refresh():
    refresh()
    return jsonify({'ok': True})

# Start background thread at module load (works with both flask dev and gunicorn)
_thread = threading.Thread(target=background_loop, daemon=True)
_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
