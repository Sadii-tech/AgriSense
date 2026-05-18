# management/commands/fix_urdu_disease_names.py
from django.core.management.base import BaseCommand
from agrisense.models import PlantScan

class Command(BaseCommand):
    help = 'Fix Urdu disease names to English in the database'
    
    def handle(self, *args, **options):
        # Urdu to English mapping for disease names
        urdu_to_english = {
            'شمالی مکئی کی پتی کی جھلسن': 'Northern Corn Leaf Blight',
            'مکئی کی بال کی سڑاند': 'Corn Ear Rot',
            'چاول کی گردن کی جھلسن': 'Rice Neck Blast',
            'چاول کا بھورا دھبہ': 'Rice Brown Spot',
            'سیب کی سڑاند': 'Apple Rot',
            'صحت مند سیب': 'Healthy Apple',
            'امرود کی سڑاند': 'Guava Rot',
            'صحت مند امرود': 'Healthy Guava',
            'انار کی سڑاند': 'Pomegranate Rot',
            'صحت مند انار': 'Healthy Pomegranate',
            'کیلے کی سڑاند': 'Banana Rot',
            'صحت مند کیلا': 'Healthy Banana',
            'نارنجی کی سڑاند': 'Orange Rot',
            'صحت مند نارنجی': 'Healthy Orange',
            'آم کے پتے کی گال': 'Mango Leaf Gall',
            'لیموں کی سڑاند': 'Lemon Rot',
            'صحت مند لیموں': 'Healthy Lemon',
        }
        
        # Urdu to English crop mapping
        urdu_to_english_crop = {
            'مکئی': 'Corn',
            'چاول': 'Rice',
            'سیب': 'Apple',
            'امرود': 'Guava',
            'انار': 'Pomegranate',
            'کیلا': 'Banana',
            'نارنجی': 'Orange',
            'آم': 'Mango',
            'لیموں': 'Lemon',
        }
        
        scans = PlantScan.objects.all()
        updated_count = 0
        crop_updated_count = 0
        
        for scan in scans:
            updated = False
            
            # Fix disease name
            if scan.disease_name in urdu_to_english:
                old_name = scan.disease_name
                scan.disease_name = urdu_to_english[old_name]
                updated = True
                updated_count += 1
                self.stdout.write(f'Fixed disease: "{old_name}" → "{scan.disease_name}"')
            
            # Fix crop type
            if scan.crop_type and scan.crop_type in urdu_to_english_crop:
                old_crop = scan.crop_type
                scan.crop_type = urdu_to_english_crop[old_crop]
                crop_updated_count += 1
                self.stdout.write(f'Fixed crop: "{old_crop}" → "{scan.crop_type}"')
                updated = True
            
            if updated:
                scan.save()
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully updated {updated_count} disease names and {crop_updated_count} crop types'
        ))