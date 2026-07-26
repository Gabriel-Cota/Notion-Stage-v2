import os
import json
import requests
from datetime import datetime, timedelta, date
from collections import Counter
import pytz

NOTION_TOKEN = os.environ['NOTION_TOKEN']
DATABASE_ID = 'eb7d566caa5683ddbde88137ddf476c1'
DAILY_GOAL = 10

headers = {
    'Authorization': f'Bearer {NOTION_TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

INTERVIEW_STATUSES = {'Entretien 1', 'Entretien 2', 'Entretien 3'}

def plain_text(prop, key):
    parts = prop.get(key) or []
    return ''.join(t.get('plain_text', '') for t in parts)

def query_database():
    pages = []
    cursor = None
    while True:
        body = {'page_size': 100}
        if cursor:
            body['start_cursor'] = cursor
        r = requests.post(
            f'https://api.notion.com/v1/databases/{DATABASE_ID}/query',
            headers=headers,
            json=body
        )
        data = r.json()
        pages.extend(data.get('results', []))
        if not data.get('has_more'):
            break
        cursor = data.get('next_cursor')
    return pages

pages = query_database()

tz = pytz.timezone('Europe/Paris')
now = datetime.now(tz)
today = now.date()

app_dates = []
statuses = Counter()
next_interview = None
next_interview_dt = None

for page in pages:
    props = page.get('properties', {})

    date_prop = props.get('Date de la candidature', {})
    if date_prop.get('type') == 'date' and date_prop.get('date'):
        try:
            app_dates.append(date.fromisoformat(date_prop['date']['start'][:10]))
        except:
            pass

    status_prop = props.get('Statut de la candidature', {})
    status_name = None
    if status_prop.get('type') == 'status' and status_prop.get('status'):
        status_name = status_prop['status']['name']
        statuses[status_name] += 1

    if status_name in INTERVIEW_STATUSES:
        interview_prop = props.get("Date de l'entretien", {})
        interview_date = interview_prop.get('date') if interview_prop.get('type') == 'date' else None
        raw_start = interview_date.get('start') if interview_date else None
        if raw_start:
            try:
                has_time = 'T' in raw_start
                dt = datetime.fromisoformat(raw_start)
                dt = tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)
                is_upcoming = dt >= now if has_time else dt.date() >= today
            except Exception:
                dt, is_upcoming = None, False

            if is_upcoming and (next_interview_dt is None or dt < next_interview_dt):
                next_interview_dt = dt
                presentiel_prop = props.get('Présentiel?', {})
                presentiel_options = presentiel_prop.get('multi_select') or []
                next_interview = {
                    'company': plain_text(props.get('Société', {}), 'rich_text'),
                    'title': plain_text(props.get('Titre du poste', {}), 'title'),
                    'datetime': dt.isoformat(),
                    'has_time': has_time,
                    'presentiel': presentiel_options[0]['name'] if presentiel_options else None,
                }

date_counter = Counter(app_dates)
today_count = date_counter.get(today, 0)

# Full daily history since the first application, so the UI can show week/month/all ranges
first_date = min(app_dates) if app_dates else today
history = []
d = first_date
while d <= today:
    history.append({'date': d.isoformat(), 'count': date_counter.get(d, 0)})
    d += timedelta(days=1)

output = {
    'total': len(app_dates),
    'today': today_count,
    'goal': DAILY_GOAL,
    'history': history,
    'statuses': {
        'Appliqué': statuses.get('Appliqué', 0),
        'Entretien 1': statuses.get('Entretien 1', 0),
        'Entretien 2': statuses.get('Entretien 2', 0),
        'Entretien 3': statuses.get('Entretien 3', 0),
        'Accepté': statuses.get('Accepté', 0),
        'Refusé': statuses.get('Refusé', 0),
    },
    'next_interview': next_interview,
    'updated_at': datetime.now(tz).strftime('%d/%m/%Y %H:%M')
}

with open('data.json', 'w') as f:
    json.dump(output, f)

print(json.dumps(output, indent=2))
