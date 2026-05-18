from django.core.management.base import BaseCommand
from agrisense.models import PlantScan

class Command(BaseCommand):
    help = 'Convert Urdu disease names to English in the database'
    
    def handle(self, *args, **options):
        # Your Urdu to English mapping
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
        
        scans = PlantScan.objects.all()
        updated_count = 0
        
        for scan in scans:
            if scan.disease_name in urdu_to_english:
                old_name = scan.disease_name
                scan.disease_name = urdu_to_english[old_name]
                scan.save()
                updated_count += 1
                self.stdout.write(f'Fixed: "{old_name}" → "{scan.disease_name}"')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} scans'))