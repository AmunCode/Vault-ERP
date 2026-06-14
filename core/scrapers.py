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
    with _driver_lock:
        try:
            driver = _get_driver()
            return _scrape(driver, item_number)
        except WebDriverException:
            # Browser may have crashed; clear singleton so next call restarts it
            global _driver
            _driver = None
            return None


def _scrape(driver: webdriver.Chrome, item_number: str) -> dict | None:
    wait = WebDriverWait(driver, 15)

    # Navigate to HSN and use the search box
    driver.get("https://www.hsn.com")
    time.sleep(2)

    # Find and fill the search input
    try:
        search_box = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'input[type="search"], input[name="query"], input[placeholder*="Search"], #search-input'
        )))
        search_box.clear()
        search_box.send_keys(item_number)
        search_box.submit()
    except TimeoutException:
        return None

    # Wait for search results to render
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/products/"]')))
    except TimeoutException:
        return None

    time.sleep(1)

    # Click the first product result
    links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/products/"]')
    product_links = [
        l for l in links
        if l.get_attribute('href') and '/products/' in l.get_attribute('href')
        and l.get_attribute('href') not in ('#', driver.current_url)
    ]
    if not product_links:
        return None

    product_url = product_links[0].get_attribute('href')
    driver.get(product_url)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
    except TimeoutException:
        pass
    time.sleep(1)

    result = _extract_from_driver(driver, product_url)
    if result and not _validate_match(result, item_number, product_url):
        return None
    return result


def _validate_match(result: dict, searched_code: str, product_url: str) -> bool:
    """
    Confirm the scraped product actually corresponds to the code that was searched.

    HSN search returns the first result even when the code doesn't exist, so we
    verify by checking the item number in the URL, JSON-LD sku, or model number.
    """
    # 7-digit item numbers appear as the trailing segment of HSN product URLs
    url_tail = product_url.rstrip('/').split('/')[-1]
    if url_tail == searched_code:
        return True

    # JSON-LD sku (HSN item number) or mpn (model/style number)
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
