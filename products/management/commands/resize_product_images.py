"""Downscale media/raw_images/* into media/products/<name>.jpg at 320x320.

Each image is centre-cropped to a square, resized with Lanczos and saved as an
optimised progressive JPEG. Alpha is flattened onto white. Filenames are kept,
so a raw file named <slug>.<ext> becomes <slug>.jpg. Re-running overwrites.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

SIZE = 320


class Command(BaseCommand):
    help = 'Resize raw product images to 320x320 JPEGs in media/products/.'

    def add_arguments(self, parser):
        parser.add_argument('--quality', type=int, default=82)
        parser.add_argument('--size', type=int, default=SIZE)

    def handle(self, *args, **opts):
        src = Path(settings.MEDIA_ROOT) / 'raw_images'
        dst = Path(settings.MEDIA_ROOT) / 'products'
        dst.mkdir(parents=True, exist_ok=True)
        size = (opts['size'], opts['size'])

        done, failed, raw_bytes, out_bytes = 0, [], 0, 0
        for f in sorted(p for p in src.iterdir() if p.is_file()):
            try:
                img = Image.open(f)
                img = ImageOps.exif_transpose(img)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGBA')
                    bg = Image.new('RGB', img.size, 'white')
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                else:
                    img = img.convert('RGB')
                img = ImageOps.fit(img, size, Image.LANCZOS)
                out = dst / f'{f.stem}.jpg'
                img.save(out, 'JPEG', quality=opts['quality'], optimize=True, progressive=True)
            except Exception as e:
                failed.append(f'{f.name}: {e}')
                continue
            done += 1
            raw_bytes += f.stat().st_size
            out_bytes += out.stat().st_size

        self.stdout.write(f'resized {done}, failed {len(failed)}: {raw_bytes/1e6:.1f} MB -> {out_bytes/1e6:.2f} MB')
        for line in failed:
            self.stdout.write(self.style.WARNING(f'  FAIL {line}'))
