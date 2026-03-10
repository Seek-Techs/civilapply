# civil_engineering/scraper/job_scraper.py
#
# Lightweight scraper using requests + BeautifulSoup only.
# No browser required. Works on Jobberman and MyJobMag.
#
# Strategy: hit their search URLs with browser-like headers,
# parse the HTML that comes back. If they return JS-only,
# we fall back to their RSS feeds and LinkedIn search.

import re, time, hashlib, logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE = {}
CACHE_TTL = 30  # minutes

def _cache_key(sources):
    return hashlib.md5(','.join(sorted(sources)).encode()).hexdigest()

def _get_cached(key):
    e = _CACHE.get(key)
    if not e: return None
    if datetime.now() - e['at'] > timedelta(minutes=CACHE_TTL):
        del _CACHE[key]; return None
    log.info(f"Cache hit — {len(e['jobs'])} jobs")
    return e['jobs']

def _set_cache(key, jobs):
    _CACHE[key] = {'jobs': jobs, 'at': datetime.now()}

# ── Helpers ───────────────────────────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

def _get(url, timeout=(6, 10)):
    try:
        time.sleep(1.0)
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except requests.exceptions.Timeout:
        log.warning(f"Timeout fetching {url}")
        return None
    except requests.exceptions.ConnectionError as e:
        log.warning(f"Connection error {url}: {e}")
        return None
    except Exception as e:
        log.warning(f"GET failed {url}: {e}")
        return None

def _clean(t): return ' '.join((t or '').split()).strip()

def _company(card_el, fallback=''):
    """Extract company name from a job card element."""
    # Try common company containers
    for sel in [
        ('span', re.compile(r'company|employer|org', re.I)),
        ('a',    re.compile(r'company|employer',     re.I)),
        ('p',    re.compile(r'company|employer',     re.I)),
        ('div',  re.compile(r'company|employer',     re.I)),
        ('h4',   None),
        ('h5',   None),
    ]:
        tag, cls = sel
        el = card_el.find(tag, class_=cls) if cls else card_el.find(tag)
        if el:
            t = _clean(el.get_text())
            # Reject if it looks like a title or location
            if t and len(t) > 1 and len(t) < 80 and not any(x in t.lower() for x in ['engineer','manager','officer','lagos','abuja','apply']):
                return t
    return fallback

def _parse_date(text):
    t = (text or '').lower()
    n = datetime.now()
    if not t or any(x in t for x in ['today','hour','minute','just']): return n.strftime('%Y-%m-%d')
    m = re.search(r'(\d+)\s+day', t)
    if m: return (n - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%d')
    m = re.search(r'(\d+)\s+week', t)
    if m: return (n - timedelta(weeks=int(m.group(1)))).strftime('%Y-%m-%d')
    return n.strftime('%Y-%m-%d')

def _salary(text):
    m = re.search(r'[₦N#][0-9,]+(?:[\s]*[-–][₦N#\s]*[0-9,]+)?(?:\s*(?:monthly|net|per\s+month))?', text or '', re.I)
    return m.group(0).strip() if m else ''

def _location(text):
    m = re.search(r'\b(Lagos|Abuja|Port Harcourt|Ibadan|Kano|Ogun|Rivers|Delta|Enugu|Kaduna)\b', text or '', re.I)
    return (m.group(0) + ', Nigeria') if m else 'Nigeria'

# ── Construction industry filter (all built environment professionals) ─────────
CONSTRUCTION_KW = {
    # Engineering disciplines
    'civil engineer', 'structural engineer', 'site engineer', 'geotechnical engineer',
    'construction engineer', 'project engineer', 'building engineer',
    'mechanical engineer', 'electrical engineer', 'm&e engineer',
    'environmental engineer', 'water engineer', 'sanitation engineer',
    # Surveying & estimation
    'quantity surveyor', 'land surveyor', 'building surveyor', 'estimator',
    'cost engineer', 'cost planner', 'bim',
    # Architecture & design
    'architect', 'architectural', 'urban planner', 'town planner',
    # Management & supervision
    'project manager', 'construction manager', 'site manager', 'site supervisor',
    'contracts manager', 'planning engineer', 'planning manager',
    'project coordinator', 'construction coordinator',
    # Safety & compliance
    'hse officer', 'hse manager', 'safety officer', 'health and safety',
    'coren', 'corbon',
    # Trades & specialist roles
    'foreman', 'works supervisor', 'clerk of works', 'site agent',
    'procurement officer', 'infrastructure', 'roads', 'bridge',
    # Keywords that appear in construction JDs
    'construction', 'building construction', 'road construction',
    'reinforced concrete', 'autocad', 'revit', 'structural design',
    'foundation', 'drainage', 'site supervision',
}
EXCL_KW = {
    'software engineer', 'software developer', 'web developer', 'frontend developer',
    'backend developer', 'full stack', 'mobile developer', 'android developer',
    'data scientist', 'data analyst', 'machine learning',
    'accountant', 'auditor', 'finance manager', 'marketing manager',
    'nurse', 'doctor', 'pharmacist', 'teacher', 'lecturer',
    'sales executive', 'business development', 'customer service',
    'legal officer', 'lawyer', 'hr manager', 'human resources',
}

def _is_construction(job):
    t = (job.get('title', '') + ' ' + job.get('snippet', '')).lower()
    return any(k in t for k in CONSTRUCTION_KW) and not any(k in t for k in EXCL_KW)

# Keep alias for backward compatibility
_is_civil = _is_construction

# ── Jobberman scraper ─────────────────────────────────────────────────────────
# Jobberman is Next.js — it renders server-side for some pages.
# The construction category page and search results are SSR.

JOBBERMAN_SEARCHES = [
    'https://www.jobberman.com/jobs/construction-site-services',
    'https://www.jobberman.com/jobs?q=civil+engineer&l=Nigeria',
    'https://www.jobberman.com/jobs?q=structural+engineer&l=Nigeria',
    'https://www.jobberman.com/jobs?q=site+engineer&l=Nigeria',
    'https://www.jobberman.com/jobs?q=quantity+surveyor&l=Nigeria',
    'https://www.jobberman.com/jobs?q=architect+construction&l=Nigeria',
    'https://www.jobberman.com/jobs?q=project+manager+construction&l=Nigeria',
    'https://www.jobberman.com/jobs?q=hse+officer&l=Nigeria',
]

def scrape_jobberman(max_pages=2):
    jobs, seen = [], set()

    for base_url in JOBBERMAN_SEARCHES:
        for pg in range(1, max_pages + 1):
            # Use ? for first param, & if URL already has query string
            if pg == 1:
                url = base_url
            elif '?' in base_url:
                url = f"{base_url}&page={pg}"
            else:
                url = f"{base_url}?page={pg}" 
            log.info(f"Jobberman: {url}")
            r = _get(url)
            if not r:
                log.warning(f"No response: {url}")
                break

            soup = BeautifulSoup(r.text, 'html.parser')

            # Diagnostic logging — tells us what Jobberman sent back
            has_nextjs = bool(soup.find('script', id='__NEXT_DATA__'))
            has_cards  = bool(soup.find('article'))
            has_links  = bool(soup.find('a', href=re.compile(r'/listings/')))
            log.info(f"  Response: {len(r.text)} chars | Next.js={has_nextjs} | articles={has_cards} | listing-links={has_links}")
            if not has_nextjs and not has_cards and not has_links:
                log.warning(f"  First 300 chars: {r.text[:300]!r}")

            # Strategy 1: Next.js injects __NEXT_DATA__ JSON with all listings
            script = soup.find('script', id='__NEXT_DATA__')
            if script:
                try:
                    import json
                    nd     = json.loads(script.string)
                    props  = nd.get('props', {}).get('pageProps', {})
                    before = len(jobs)

                    # Walk ALL keys recursively to find a list of job objects
                    def _find_listings(obj, depth=0):
                        if depth > 6: return []
                        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                            if any(k in obj[0] for k in ('slug','title','job_title','id')):
                                return obj
                        if isinstance(obj, dict):
                            for v in obj.values():
                                found = _find_listings(v, depth+1)
                                if found: return found
                        return []

                    listings = _find_listings(props)
                    log.info(f"  Next.js listings found: {len(listings)}")
                    for item in listings:
                        job = _parse_jobberman_json(item)
                        if job and job['url'] not in seen:
                            seen.add(job['url'])
                            jobs.append(job)
                    if len(jobs) > before:
                        log.info(f"  Extracted {len(jobs)-before} jobs from Next.js")
                        continue
                    else:
                        # Log top-level keys to help debug structure
                        log.warning(f"  Next.js found but no listings. Top keys: {list(props.keys())[:10]}")
                except Exception as e:
                    log.warning(f"Next.js parse error: {e}")

            # Strategy 2: parse HTML job cards
            new = _parse_jobberman_html(soup, seen, jobs)
            log.info(f"  HTML parse: {new} new jobs")
            if new == 0:
                break

    return jobs


def _parse_jobberman_json(item):
    """Parse a job from Jobberman's Next.js JSON data."""
    try:
        title = _clean(item.get('title') or item.get('job_title') or item.get('name',''))
        if not title: return None
        slug  = item.get('slug') or item.get('id','')
        url   = f"https://www.jobberman.com/listings/{slug}" if slug else ''
        return {
            'title':    title,
            'company':  _clean(item.get('company',{}).get('name','') if isinstance(item.get('company'), dict) else item.get('company','')),
            'location': _clean(item.get('location','') or item.get('city','')) or 'Nigeria',
            'salary':   _clean(item.get('salary','') or ''),
            'url':      url,
            'snippet':  _clean(item.get('summary','') or item.get('description',''))[:280],
            'posted':   _parse_date(item.get('created_at','') or item.get('date','')),
            'source':   'Jobberman',
        }
    except Exception as e:
        log.debug(f"JSON item parse error: {e}")
        return None


def _parse_jobberman_html(soup, seen, jobs):
    """Parse Jobberman HTML cards — fallback when Next.js data not found."""
    new = 0
    # Try multiple card selectors
    cards = (soup.find_all('article') or
             soup.find_all('div', attrs={'data-job-id': True}) or
             soup.find_all('li', class_=re.compile(r'job|listing', re.I)))

    # Last resort: all links to /listings/
    if not cards:
        links = soup.find_all('a', href=re.compile(r'/listings/'))
        for a in links:
            href = a.get('href','')
            if not href or href in seen: continue
            url = href if href.startswith('http') else 'https://www.jobberman.com' + href
            title = _clean(a.get_text())
            if not title or len(title) < 5: continue
            seen.add(href)
            container = a.find_parent('div') or a.find_parent('li') or a
            text = _clean(container.get_text())
            company = _company(container)
            jobs.append({'title': title, 'company': company, 'location': _location(text),
                         'salary': _salary(text), 'url': url,
                         'snippet': text[:280], 'posted': datetime.now().strftime('%Y-%m-%d'),
                         'source': 'Jobberman'})
            new += 1
        return new

    for card in cards:
        href_el = card.find('a', href=re.compile(r'/listings/'))
        if not href_el: continue
        href = href_el.get('href','')
        if not href or href in seen: continue
        url = href if href.startswith('http') else 'https://www.jobberman.com' + href
        seen.add(href)
        title_el = card.find(['h2','h3','h4'])
        title    = _clean(title_el.get_text()) if title_el else _clean(href_el.get_text())
        if not title or len(title) < 4: continue
        text      = _clean(card.get_text())
        company   = _company(card)
        date_el   = card.find('time') or card.find(class_=re.compile(r'date|posted|ago', re.I))
        jobs.append({'title': title, 'company': company, 'location': _location(text),
                     'salary': _salary(text), 'url': url,
                     'snippet': text[:280],
                     'posted': _parse_date(date_el.get_text() if date_el else ''),
                     'source': 'Jobberman'})
        new += 1
    return new


# ── MyJobMag scraper ──────────────────────────────────────────────────────────
MYJOBMAG_SEARCHES = [
    'https://www.myjobmag.com/jobs/civil+engineer/nigeria',
    'https://www.myjobmag.com/jobs/structural+engineer/nigeria',
    'https://www.myjobmag.com/jobs/site+engineer/nigeria',
    'https://www.myjobmag.com/jobs/quantity+surveyor/nigeria',
    'https://www.myjobmag.com/jobs/architect/nigeria',
    'https://www.myjobmag.com/jobs/project+manager+construction/nigeria',
    'https://www.myjobmag.com/jobs/hse+officer/nigeria',
    'https://www.myjobmag.com/jobs/land+surveyor/nigeria',
]

def scrape_myjobmag(max_pages=2):
    jobs, seen = [], set()

    for base_url in MYJOBMAG_SEARCHES:
        for pg in range(1, max_pages + 1):
            url = base_url if pg == 1 else f"{base_url}?page={pg}"
            log.info(f"MyJobMag: {url}")
            r = _get(url)
            if not r: break

            soup = BeautifulSoup(r.text, 'html.parser')
            new  = 0

            # MyJobMag is server-rendered WordPress — straightforward HTML
            for a in soup.find_all('a', href=re.compile(r'myjobmag\.com/job/')):
                href = a.get('href','')
                if not href or href in seen: continue
                title = _clean(a.get_text())
                if not title or len(title) < 5: continue
                seen.add(href)
                container = a.find_parent('div', class_=re.compile(r'job|listing|card', re.I)) or a.find_parent('li') or a
                text = _clean(container.get_text()) if container else title
                company = _company(container)
                jobs.append({'title': title, 'company': company, 'location': _location(text),
                             'salary': _salary(text), 'url': href,
                             'snippet': text[:280], 'posted': datetime.now().strftime('%Y-%m-%d'),
                             'source': 'MyJobMag'})
                new += 1

            log.info(f"  pg {pg}: {new} new jobs")
            if new == 0: break

    return jobs




# ── NGCareers scraper ─────────────────────────────────────────────────────────
NGCAREERS_SEARCHES = [
    'https://ngcareers.com/jobs?q=civil+engineer',
    'https://ngcareers.com/jobs?q=structural+engineer',
    'https://ngcareers.com/jobs?q=site+engineer',
    'https://ngcareers.com/jobs?q=quantity+surveyor',
    'https://ngcareers.com/jobs?q=architect+construction',
    'https://ngcareers.com/jobs?q=project+manager+construction',
    'https://ngcareers.com/jobs?q=hse+officer+construction',
]

def scrape_ngcareers(max_pages=2):
    jobs, seen = [], set()

    for base_url in NGCAREERS_SEARCHES:
        for pg in range(1, max_pages + 1):
            url = base_url if pg == 1 else f"{base_url}&page={pg}"
            log.info(f"NGCareers: {url}")
            r = _get(url)
            if not r: break

            soup = BeautifulSoup(r.text, 'html.parser')
            new  = 0

            # NGCareers: job cards with job title links
            for a in soup.find_all('a', href=re.compile(r'/job/|/jobs/')):
                href = a.get('href', '')
                if not href: continue
                if not href.startswith('http'): href = 'https://ngcareers.com' + href
                if href in seen: continue
                title = _clean(a.get_text())
                if not title or len(title) < 5: continue
                seen.add(href)
                container = a.find_parent('div', class_=re.compile(r'job|card|listing', re.I)) or a.find_parent('li') or a
                text = _clean(container.get_text()) if container else title
                company = _company(container)
                jobs.append({
                    'title': title, 'company': company, 'location': _location(text),
                    'salary': _salary(text), 'url': href,
                    'snippet': text[:280], 'posted': datetime.now().strftime('%Y-%m-%d'),
                    'source': 'NGCareers'
                })
                new += 1

            log.info(f"  pg {pg}: {new} new jobs")
            if new == 0: break

    return jobs


# ── HotNigerianJobs scraper ───────────────────────────────────────────────────
HOTNG_SEARCHES = [
    'https://www.hotnigerianobs.com/search/civil+engineer',
    'https://www.hotnigerianobs.com/search/structural+engineer',
    'https://www.hotnigerianobs.com/search/site+engineer',
]

def scrape_hotng(max_pages=1):
    """HotNigerianJobs — server-rendered, straightforward HTML."""
    jobs, seen = [], set()

    for base_url in HOTNG_SEARCHES:
        for pg in range(1, max_pages + 1):
            url = base_url if pg == 1 else f"{base_url}/{pg}"
            log.info(f"HotNigerianJobs: {url}")
            r = _get(url)
            if not r: break

            soup = BeautifulSoup(r.text, 'html.parser')
            new  = 0

            for a in soup.find_all('a', href=re.compile(r'/jobs?/|/job-detail/', re.I)):
                href = a.get('href', '')
                if not href: continue
                if not href.startswith('http'): href = 'https://www.hotnigerianjobs.com' + href
                if href in seen: continue
                title = _clean(a.get_text())
                if not title or len(title) < 5: continue
                seen.add(href)
                container = a.find_parent('div', class_=re.compile(r'job|card|post|entry', re.I)) or a.find_parent('li') or a
                text = _clean(container.get_text()) if container else title
                company = _company(container)
                jobs.append({
                    'title': title, 'company': company, 'location': _location(text),
                    'salary': _salary(text), 'url': href,
                    'snippet': text[:280], 'posted': datetime.now().strftime('%Y-%m-%d'),
                    'source': 'HotNigerianJobs'
                })
                new += 1

            log.info(f"  pg {pg}: {new} new jobs")
            if new == 0: break

    return jobs



# ── LinkedIn scraper (public RSS + HTML fallback) ─────────────────────────────
# LinkedIn serves public job listings without authentication for search results.
# We use their public search pages which embed JSON-LD structured data.
# No login required. No API key. Works on Render.
# Rate limit: 1 request/sec already enforced by _get() sleep.

LINKEDIN_SEARCHES = [
    # Civil & structural
    'https://www.linkedin.com/jobs/civil-engineer-jobs-nigeria',
    'https://www.linkedin.com/jobs/structural-engineer-jobs-nigeria',
    'https://www.linkedin.com/jobs/site-engineer-jobs-nigeria',
    # Broader construction
    'https://www.linkedin.com/jobs/quantity-surveyor-jobs-nigeria',
    'https://www.linkedin.com/jobs/construction-project-manager-jobs-nigeria',
    'https://www.linkedin.com/jobs/architect-jobs-nigeria',
    'https://www.linkedin.com/jobs/hse-officer-jobs-nigeria',
]

def scrape_linkedin(max_pages=1):
    """
    Scrape LinkedIn public job search pages.
    LinkedIn serves server-rendered HTML for these URLs (no JS required).
    Each card has: data-entity-urn, job title in <h3>, company in <h4>,
    location in <span class="job-search-card__location">.
    Falls back to JSON-LD if card structure changes.
    """
    import xml.etree.ElementTree as ET
    jobs, seen = [], set()

    for base_url in LINKEDIN_SEARCHES:
        for pg in range(max_pages):
            url = base_url if pg == 0 else f"{base_url}?start={pg * 25}"
            log.info(f"LinkedIn: {url}")
            r = _get(url)
            if not r:
                break

            soup = BeautifulSoup(r.text, 'html.parser')
            new  = 0

            # Method 1: LinkedIn job cards (class="base-card" or "job-search-card")
            cards = soup.find_all('div', class_=re.compile(r'base-card|job-search-card', re.I))
            if not cards:
                # Method 2: <li> elements with data-entity-urn
                cards = soup.find_all('li', attrs={'data-entity-urn': True})

            for card in cards:
                # Title — in <h3> or <a class="base-card__full-link">
                title_el = card.find('h3') or card.find('a', class_=re.compile(r'base-card__full-link|job.*title', re.I))
                title = _clean(title_el.get_text()) if title_el else ''
                if not title or len(title) < 4:
                    continue

                # URL
                link_el = card.find('a', href=re.compile(r'/jobs/view/'))
                href = link_el.get('href', '').split('?')[0] if link_el else ''
                if not href:
                    href = card.get('data-entity-urn', '')
                if not href or href in seen:
                    continue
                seen.add(href)

                # Company — in <h4> or <a class="hidden-nested-link">
                company_el = card.find('h4') or card.find('a', class_=re.compile(r'hidden-nested-link', re.I))
                company = _clean(company_el.get_text()) if company_el else ''

                # Location
                loc_el = card.find('span', class_=re.compile(r'location|job-search-card__location', re.I))
                location = _clean(loc_el.get_text()) if loc_el else 'Nigeria'

                # Posted date
                time_el = card.find('time')
                posted_raw = time_el.get('datetime', '') if time_el else ''
                posted = posted_raw[:10] if posted_raw else datetime.now().strftime('%Y-%m-%d')

                text = title + ' ' + company + ' ' + location
                jobs.append({
                    'title':    title,
                    'company':  company,
                    'location': location if 'nigeria' in location.lower() else location + ', Nigeria',
                    'salary':   '',
                    'url':      href if href.startswith('http') else 'https://www.linkedin.com' + href,
                    'snippet':  text[:280],
                    'posted':   posted,
                    'source':   'LinkedIn',
                })
                new += 1

            # Method 3: JSON-LD fallback (LinkedIn embeds structured data)
            if new == 0:
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        import json as _json
                        data = _json.loads(script.string or '{}')
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if item.get('@type') != 'JobPosting':
                                continue
                            title   = _clean(item.get('title', ''))
                            company = _clean((item.get('hiringOrganization') or {}).get('name', ''))
                            loc     = (item.get('jobLocation') or {})
                            if isinstance(loc, list): loc = loc[0] if loc else {}
                            location = _clean((loc.get('address') or {}).get('addressLocality', 'Nigeria'))
                            url     = item.get('url', '')
                            if not title or not url or url in seen:
                                continue
                            seen.add(url)
                            posted = (item.get('datePosted') or datetime.now().strftime('%Y-%m-%d'))[:10]
                            text   = title + ' ' + company
                            jobs.append({
                                'title':    title,
                                'company':  company,
                                'location': location,
                                'salary':   '',
                                'url':      url,
                                'snippet':  text[:280],
                                'posted':   posted,
                                'source':   'LinkedIn',
                            })
                            new += 1
                    except Exception:
                        pass

            log.info(f"  pg {pg+1}: {new} new jobs from LinkedIn")
            if new == 0:
                break

    return jobs

# ── Public API ────────────────────────────────────────────────────────────────
def fetch_jobs(sources=None, max_pages=2, force_refresh=False):
    sources = [s.lower() for s in (sources or ['jobberman','myjobmag','ngcareers','hotng','linkedin'])]
    key = _cache_key(sources)
    if not force_refresh:
        cached = _get_cached(key)
        if cached is not None: return cached

    all_jobs = []
    if 'jobberman' in sources:
        try: all_jobs.extend(scrape_jobberman(max_pages))
        except Exception as e: log.error(f"Jobberman failed: {e}")
    if 'myjobmag' in sources:
        try: all_jobs.extend(scrape_myjobmag(max_pages))
        except Exception as e: log.error(f"MyJobMag failed: {e}")
    if 'ngcareers' in sources:
        try: all_jobs.extend(scrape_ngcareers(max_pages))
        except Exception as e: log.error(f"NGCareers failed: {e}")
    if 'hotng' in sources:
        try: all_jobs.extend(scrape_hotng(max_pages))
        except Exception as e: log.error(f"HotNigerianJobs failed: {e}")
    if 'linkedin' in sources:
        try: all_jobs.extend(scrape_linkedin(max_pages))
        except Exception as e: log.error(f"LinkedIn failed: {e}")

    civil = [j for j in all_jobs if _is_construction(j)]
    seen, unique = set(), []
    for j in civil:
        k = j.get('url') or j.get('title','')
        if k not in seen: seen.add(k); unique.append(j)

    unique.sort(key=lambda j: j.get('posted',''), reverse=True)
    _set_cache(key, unique)
    log.info(f"fetch_jobs: {len(unique)} civil / {len(all_jobs)} raw")
    return unique


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    jobs = fetch_jobs(max_pages=1)
    print(f"\n{len(jobs)} jobs\n")
    for j in jobs[:10]:
        print(f"[{j['source']}] {j['title']}")
        print(f"  {j['company']} | {j['location']} | {j['salary'] or 'N/A'}")
        print(f"  {j['url']}\n")
