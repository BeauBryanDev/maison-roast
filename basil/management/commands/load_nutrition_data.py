
import json
import pathlib
 
from django.conf import settings
from django.core.management.base import BaseCommand
 
from basil.models import NutritionInfo
 
DEFAULT_PATH = pathlib.Path(settings.BASE_DIR) / 'master_food_nutrition.json'
 
# Fields copied straight from each JSON entry onto the model. vision_label is
# handled separately since it's the lookup key, not a plain default.
FIELD_MAP = [
    'basis_g', 'calories_kcal', 'protein_g', 'carbs_g', 'fat_g',
    'description', 'data_type', 'fdc_id', 'source_file',
]
 
# Reads master_food_nutrition.json (expected at the project root, same layout
# Beau generated: {"basis_g": 100, "foods": {vision_label: {...}, ...}}) and
# seeds NutritionInfo via the ORM.
 
class Command(BaseCommand):
    help = 'Seed NutritionInfo from master_food_nutrition.json via the ORM.'
 
    def add_arguments(self, parser):
        parser.add_argument(
            '--path', type=str, default=None,
            help='Path to the JSON file. Defaults to master_food_nutrition.json at the project root.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parse and report only. No database writes.',
        )
 
    def handle(self, *args, **options):
        
        path = pathlib.Path(options['path']) if options['path'] else DEFAULT_PATH
 
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'File not found: {path}'))
            return
 
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            self.stderr.write(self.style.ERROR(f'Invalid JSON in {path}: {exc}'))
            return
 
        foods = data.get('foods')
        
        if not isinstance(foods, dict):
            self.stderr.write(self.style.ERROR(
                "Expected a top-level 'foods' object mapping vision_label -> entry."
            ))
            return
 
        self.stdout.write(f'{len(foods)} entries found in {path.name}')
 
        if options['dry_run']:
            
            for label, entry in foods.items():
                kcal = entry.get('calories_kcal')
                desc = entry.get('description', '')
                self.stdout.write(f'  {label:28s} {kcal!s:>8} kcal   {desc}')
            self.stdout.write(self.style.WARNING('Dry run: nothing written.'))
            return
 
        created, updated, skipped = 0, 0, []
 
        for label, entry in foods.items():
            # entry['vision_label'] should already match the dict key, but the
            # key is what we actually key off of -- trust the structure, not
            # a possibly-diverged inner field.
            defaults = {field: entry.get(field) for field in FIELD_MAP}
 
            if defaults.get('calories_kcal') is None:
                skipped.append(label)
                continue
 
            obj, was_created = NutritionInfo.objects.update_or_create(
                vision_label=label, defaults=defaults,
            )
            created += int(was_created)
            updated += int(not was_created)
 
        self.stdout.write(self.style.SUCCESS(
            f'{created} created, {updated} updated, {NutritionInfo.objects.count()} total rows.'
        ))
        if skipped:
            self.stdout.write(self.style.WARNING(
                f'Skipped {len(skipped)} entries with no calories_kcal: {", ".join(skipped)}'
            ))
 
 
 