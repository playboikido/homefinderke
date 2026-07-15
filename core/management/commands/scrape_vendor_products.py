import re
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin
from urllib import robotparser

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags

from core.models import Mover, MoverProduct, FurnitureVendor, FurnitureProduct

logger = logging.getLogger(__name__)

MAX_NAME_LEN = 200
REQUEST_TIMEOUT = 10
USER_AGENT = 'HomeFinderKE-Bot/1.0 (+https://homefinderke.onrender.com)'


def is_scrape_allowed(url):
    try:
        rp = robotparser.RobotFileParser()
        rp.set_url(urljoin(url, '/robots.txt'))
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return False  # fail closed


def clean_price(raw_text):
    if not raw_text:
        return None
    match = re.search(r'[\d,]+(?:\.\d{1,2})?', raw_text)
    if not match:
        return None
    try:
        value = Decimal(match.group().replace(',', ''))
        if value <= 0 or value > Decimal('100000000'):
            return None
        return value
    except InvalidOperation:
        return None


def clean_text(raw_text, max_len=MAX_NAME_LEN):
    if not raw_text:
        return ''
    return strip_tags(raw_text).strip()[:max_len]


class Command(BaseCommand):
    help = 'Scrapes product/price data for Movers and FurnitureVendors with data_source scraped/mixed.'

    def handle(self, *args, **options):
        self.run_for(Mover, MoverProduct, 'mover')
        self.run_for(FurnitureVendor, FurnitureProduct, 'vendor')

    def run_for(self, vendor_model, product_model, fk_name):
        vendors = vendor_model.objects.filter(
            data_source__in=['scraped', 'mixed'],
            is_approved=True,
            scrape_config__isnull=False,
        )
        for vendor in vendors:
            try:
                self.scrape_vendor(vendor, product_model, fk_name)
            except Exception as exc:
                logger.warning(f"Scrape failed for {vendor_model.__name__} {vendor.id} ({vendor.name}): {exc}")
                vendor.scrape_status = 'failed'
                vendor.last_scraped_at = timezone.now()
                vendor.save(update_fields=['scrape_status', 'last_scraped_at'])
                self.stdout.write(self.style.WARNING(f"FAILED: {vendor.name} — {exc}"))

    def scrape_vendor(self, vendor, product_model, fk_name):
        config = vendor.scrape_config
        page_url = config['product_page_url']

        if not is_scrape_allowed(page_url):
            raise ValueError('Disallowed by robots.txt')

        resp = requests.get(page_url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': USER_AGENT})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select(config['item_selector'])[:20]

        found_products = []
        for item in items:
            name_el = item.select_one(config.get('name_selector', ''))
            price_el = item.select_one(config.get('price_selector', ''))
            img_el = item.select_one(config.get('image_selector', ''))

            name = clean_text(name_el.get_text() if name_el else '')
            price = clean_price(price_el.get_text() if price_el else '')
            image_url = ''
            if img_el and img_el.get('src'):
                image_url = urljoin(page_url, img_el['src'])[:500]

            if name:
                found_products.append({'name': name, 'price': price, 'image_url': image_url})

        if not found_products:
            raise ValueError('No products parsed — selectors may be stale')

        product_model.objects.filter(**{fk_name: vendor}, source='scraped').update(is_active=False)
        for p in found_products:
            product_model.objects.update_or_create(
                **{fk_name: vendor}, name=p['name'], source='scraped',
                defaults={'price': p['price'], 'image_url': p['image_url'], 'is_active': True},
            )

        vendor.scrape_status = 'ok'
        vendor.last_scraped_at = timezone.now()
        vendor.save(update_fields=['scrape_status', 'last_scraped_at'])
        self.stdout.write(self.style.SUCCESS(f"OK: {vendor.name} — {len(found_products)} products"))