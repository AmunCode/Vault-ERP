"""
HSN product lookup using Selenium with a visible Chrome window.
A real browser session bypasses Cloudflare bot detection.

A single Chrome instance is reused for the lifetime of the Django process
so repeated scans don't each open a new window.
"""
import re
import json
import time
import threading
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

_IMAGE_PREFER = re.compile(r'/prodfull/|/rocs1200/|/pd154/')
_IMAGE_EXCLUDE = re.compile(r'match|/orig/|~\d+x\d+')

# HSN posts short per-item demo clips to YouTube alongside hour-long live-
# broadcast recordings that also match a plain item-number search. Duration
# is the only reliable way to tell them apart -- both kinds of video title
# look like generic "HSN | ..." text.
_YOUTUBE_MAX_DURATION_SECONDS = 15 * 60

# Module-level singleton — one browser per Django process
_driver: webdriver.Chrome | None = None
_driver_lock = threading.Lock()


def _make_driver() -> webdriver.Chrome:
    options = Options()
    # Visible browser — not headless, bypasses bot detection
    options.add_argument('--start-minimized')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--disable-notifications')
    options.add_argument('--no-sandbox')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    return driver


def _get_driver() -> webdriver.Chrome:
    """Return the shared browser, creating it if needed or if it crashed."""
    global _driver
    try:
        if _driver is not None:
            _driver.title  # ping — raises if window is dead
            return _driver
    except Exception:
        _driver = None

    _driver = _make_driver()
    return _driver


def scrape_hsn(item_number: str) -> dict | None:
    """
    Look up an HSN product by item number or 6-digit model code.

    Reuses a persistent Chrome window across calls. Thread-safe: only one
    scrape runs at a time via a module-level lock.
    """
    item_number = item_number.strip()
    print(f"[scrape_hsn] looking up item number: {item_number}")
    with _driver_lock:
        try:
            driver = _get_driver()
            result = _scrape(driver, item_number)
            if result:
                return result
            print(f"[scrape_hsn] not on hsn.com, trying YouTube fallback")
            return _scrape_youtube_title(driver, item_number)
        except WebDriverException:
            # Browser may have crashed; clear singleton so next call restarts it
            global _driver
            _driver = None
            return None


def _parse_duration_seconds(aria_label: str) -> int | None:
    """
    YouTube's video-title aria-label ends with the duration, e.g.
    "...Blouse 4 minutes, 54 seconds" or "...At Home 01.26.16 1 hour".
    Anchor to the trailing phrase so a number embedded earlier in the
    title itself (e.g. "5 Minute Beauty Routine") isn't misread as the
    duration.
    """
    trailing = re.search(r'((?:\d+\s*(?:hour|minute|second)s?[,\s]*)+)$', aria_label, re.IGNORECASE)
    if not trailing:
        return None
    unit_seconds = {'hour': 3600, 'minute': 60, 'second': 1}
    total = 0
    for value, unit in re.findall(r'(\d+)\s*(hour|minute|second)s?', trailing.group(1), re.IGNORECASE):
        total += int(value) * unit_seconds[unit.lower()]
    return total


def _scrape_youtube_title(driver: webdriver.Chrome, item_number: str) -> dict | None:
    """
    Fallback when HSN's own site doesn't have the product page. Searches
    YouTube for "HSN <item_number>" and returns the title of the first
    *short* result (a per-item demo clip), skipping hour-long live-broadcast
    recordings that also match the search. This is a best-effort title only
    -- no images/brand/price -- and isn't cross-checked against the item
    number the way the HSN scrape's _validate_match is, so the worker still
    needs to review it before confirming.
    """
    query = f"HSN {item_number}"
    driver.get(f"https://www.youtube.com/results?search_query={quote(query)}")
    wait = WebDriverWait(driver, 15)
    try:
        wait.until(EC.presence_of_element_located((By.ID, "video-title")))
    except TimeoutException:
        return None
    time.sleep(1)

    for el in driver.find_elements(By.ID, "video-title")[:10]:
        aria_label = el.get_attribute('aria-label') or ''
        duration = _parse_duration_seconds(aria_label)
        if duration is None or duration > _YOUTUBE_MAX_DURATION_SECONDS:
            continue
        title = el.text.strip()
        if not title:
            continue
        title = re.sub(r'\s*\|\s*HSN\s*$', '', title).strip()
        return {
            'title': title,
            'description': '',
            'brand': '',
            'images': [],
            'retail_price': '',
            'url': el.get_attribute('href') or '',
            'needs_title': False,
            'from_youtube': True,
        }
    return None


def _dismiss_popups(driver: webdriver.Chrome) -> None:
    """
    Remove marketing overlays (e.g. the Attentive SMS-signup iframe) that HSN
    shows a couple seconds after load. These render full-viewport and steal
    focus, which silently swallows send_keys() into the search box -- no
    exception is raised, the input just never receives the typed text.
    """
    driver.execute_script("""
        document.querySelectorAll(
            '#attentive_creative, [id^="attentive"], iframe[title*="Sign Up" i]'
        ).forEach(el => el.remove());
    """)


def _scrape(driver: webdriver.Chrome, item_number: str) -> dict | None:
    wait = WebDriverWait(driver, 15)

    # Navigate to HSN and use the search box
    driver.get("https://www.hsn.com")
    time.sleep(2)
    _dismiss_popups(driver)

    # Find and fill the search input
    try:
        search_box = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'input[type="search"], input[name="query"], input[placeholder*="Search"], #search-input'
        )))
        search_box.click()
        search_box.clear()
        search_box.send_keys(item_number)
        search_box.submit()
    except TimeoutException:
        return None

    # An exact item-number search lands directly on the product page --
    # no results-list page to click through.
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
    except TimeoutException:
        pass
    time.sleep(1)

    product_url = driver.current_url
    result = _extract_from_driver(driver, product_url)
    if result and not _validate_match(result, item_number):
        return None
    return result


def _validate_match(result: dict, searched_code: str) -> bool:
    """
    Confirm the scraped product actually corresponds to the code that was searched.

    HSN tags every image asset for a product with its item number (e.g.
    ".../nina-leonard-crop-pant...~924538_7YJ.jpg"), which is a far more
    reliable signal than the URL path -- the trailing URL segment is an
    unrelated internal catalog id, not the item number, despite what it looks
    like -- or JSON-LD sku/mpn, which are only populated when a product page
    has JSON-LD at all (the DOM-scrape fallback never sets those fields).
    """
    for image_url in result.get('images', []):
        if searched_code in image_url:
            return True

    for field in ('sku', 'mpn', 'model'):
        val = result.get(field, '')
        if val and searched_code in val:
            return True

    return False


def _extract_from_driver(driver: webdriver.Chrome, page_url: str) -> dict | None:
    # Try JSON-LD first
    scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
    for script in scripts:
        try:
            data = json.loads(script.get_attribute('innerHTML') or '')
        except (json.JSONDecodeError, Exception):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get('@type') == 'Product':
                result = _extract_from_ld(item, page_url)
                if result.get('title'):
                    if not result['images']:
                        result['images'] = _extract_images(driver.page_source)
                    if not result['retail_price']:
                        result['retail_price'] = _extract_price(driver)
                    return result

    # Fallback: scrape DOM directly
    title = ''
    try:
        h1 = driver.find_element(By.TAG_NAME, 'h1')
        title = h1.text.strip()
    except Exception:
        pass
    if not title:
        try:
            el = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:title"]')
            title = el.get_attribute('content') or ''
        except Exception:
            pass
    title = re.sub(r'\s*\|\s*HSN\s*$', '', title).strip()

    if not title:
        return None

    return {
        'title': title,
        'description': _extract_description(driver),
        'brand': _extract_brand(driver),
        'images': _extract_images(driver.page_source),
        'retail_price': _extract_price(driver),
        'url': page_url,
        'needs_title': False,
    }


def _extract_from_ld(item: dict, page_url: str) -> dict:
    images = item.get('image', [])
    if isinstance(images, str):
        images = [images]
    elif isinstance(images, dict):
        images = [images.get('url', '')]

    price = None
    offers = item.get('offers', {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if offers:
        price = offers.get('price') or offers.get('lowPrice')

    brand = item.get('brand', '')
    if isinstance(brand, dict):
        brand = brand.get('name', '')

    title = re.sub(r'\s*\|\s*HSN\s*$', '', item.get('name', '')).strip()

    return {
        'title': title,
        'description': item.get('description', ''),
        'brand': brand,
        'images': [i for i in images if i],
        'retail_price': str(price) if price else '',
        'url': page_url,
        'sku': item.get('sku', ''),
        'mpn': item.get('mpn', ''),
        'needs_title': False,
    }


def _extract_images(page_source: str) -> list[str]:
    all_urls = re.findall(r'https://i\d+\.hsncdn\.com/is/image/[^\s\"\'\&\\]+\.jpg', page_source)
    seen, result = set(), []
    for url in all_urls:
        if _IMAGE_EXCLUDE.search(url):
            continue
        stem = re.split(r'[~?]', url)[-1]
        if stem not in seen and _IMAGE_PREFER.search(url):
            seen.add(stem)
            result.append(url)
    return result[:8]


def _extract_price(driver: webdriver.Chrome) -> str:
    prices = []
    try:
        els = driver.find_elements(By.CSS_SELECTOR, '[class*=Price],[class*=price]')
        for el in els:
            for m in re.findall(r'\$([\d,]+\.\d{2})', el.text):
                try:
                    prices.append(float(m.replace(',', '')))
                except ValueError:
                    continue
    except Exception:
        pass
    return f"{max(prices):.2f}" if prices else ''


def _extract_description(driver: webdriver.Chrome) -> str:
    selectors = ['[class*="description"]', '[class*="Description"]', '[data-testid*="description"]']
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if len(txt) > 30:
                return txt
        except Exception:
            continue
    return ''


def _extract_brand(driver: webdriver.Chrome) -> str:
    try:
        el = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:brand"]')
        val = el.get_attribute('content') or ''
        if val:
            return val
    except Exception:
        pass
    for sel in ['[itemprop="brand"]', '[class*="brandName"]', '[class*="brand-name"]']:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            # Ignore nav links like "Shop all X"
            if txt and len(txt) < 60 and not txt.lower().startswith('shop'):
                return txt
        except Exception:
            continue
    return ''
