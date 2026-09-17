"""Download each product's hotlinked image into MEDIA_ROOT/raw_images/<slug>.<ext>.

Only rows whose product_image starts with http are fetched. Rows holding a
relative path have no source and are listed at the end. Re-running skips files
that already exist unless --force is given.
"""
import io
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from products.models import Product

UA = 'Mozilla/5.0 (X11; Linux x86_64) MaisonRoast/1.0'


class Command(BaseCommand):
    help = 'Fetch hotlinked product images into media/raw_images/.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='fetch but write nothing')
        parser.add_argument('--force', action='store_true', help='overwrite existing files')

    def handle(self, *args, **opts):
        out = Path(settings.MEDIA_ROOT) / 'raw_images'
        if not opts['dry_run']:
            out.mkdir(parents=True, exist_ok=True)

        ok, skipped, failed, no_source = [], [], [], []
        for p in Product.objects.order_by('slug'):
            url = p.product_image or ''
            if not url.startswith('http'):
                no_source.append(p.slug)
                continue
            existing = list(out.glob(f'{p.slug}.*'))
            if existing and not opts['force']:
                skipped.append(p.slug)
                continue
            try:
                req = Request(url, headers={'User-Agent': UA, 'Accept': 'image/*,*/*'})
                with urlopen(req, timeout=20) as r:
                    data = r.read()
                img = Image.open(io.BytesIO(data))
                img.verify()
                ext = (img.format or 'jpeg').lower().replace('jpeg', 'jpg')
            except Exception as e:
                failed.append((p.slug, url, str(e)[:80]))
                continue
            if not opts['dry_run']:
                (out / f'{p.slug}.{ext}').write_bytes(data)
            ok.append(f'{p.slug}.{ext}')

        self.stdout.write(f'downloaded {len(ok)}, skipped {len(skipped)}, failed {len(failed)}, no source {len(no_source)}')
        for slug, url, err in failed:
            self.stdout.write(self.style.WARNING(f'  FAIL {slug}: {err}\n       {url}'))
        if no_source:
            self.stdout.write(f'no source (need a local file): {", ".join(no_source)}')
