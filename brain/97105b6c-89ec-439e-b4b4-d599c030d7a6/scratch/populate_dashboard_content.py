import sys
import os
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AgriSenseProject.settings')
django.setup()

from agrisense.models import StaticContent

dashboard_labels = [
    # Sidebar
    ('dashboard', 'nav-dashboard', 'Dashboard', 'ڈیش بورڈ'),
    ('dashboard', 'nav-scanner', 'New Scan', 'نیا اسکین'),
    ('dashboard', 'nav-history', 'History', 'تاریخچہ'),
    ('dashboard', 'nav-settings', 'Settings', 'ترتیبات'),
    ('dashboard', 'nav-about', 'About Us', 'ہمارے بارے میں'),
    ('dashboard', 'nav-logout', 'Logout', 'لاگ آؤٹ'),
    
    # Header
    ('dashboard', 'search-placeholder', 'Search insights, diseases, or sectors...', 'بصیرت، بیماریاں، یا شعبے تلاش کریں...'),
    ('dashboard', 'quick-scan', 'Quick Scan', 'فوری اسکین'),
    
    # Stats Cards
    ('dashboard', 'total-scans-label', 'Total Scans', 'کل اسکینز'),
    ('dashboard', 'healthy-scans-label', 'Healthy Scans', 'صحت مند اسکینز'),
    ('dashboard', 'disease-detected-label', 'Disease Detected', 'بیماری کا پتہ چلا'),
    ('dashboard', 'ai-performance-label', 'AI Performance', 'اے آئی کارکردگی'),
    ('dashboard', 'avg-confidence-label', 'Avg. Confidence', 'اوسط اعتماد'),
    
    # Section Titles
    ('dashboard', 'health-overview-title', 'Health Overview', 'صحت کا جائزہ'),
    ('dashboard', 'recent-activity-title', 'Recent Activity', 'حالیہ سرگرمی'),
    ('dashboard', 'disease-dist-title', 'Disease Distribution', 'بیماریوں کی تقسیم'),
    ('dashboard', 'realtime-insights-title', 'Real-time Insights', 'حقیقی وقت کی بصیرت'),
]

for page, key, en, ur in dashboard_labels:
    obj, created = StaticContent.objects.update_or_create(
        page=page, key=key,
        defaults={'text_en': en, 'text_ur': ur}
    )
    print(f"{'Created' if created else 'Updated'}: {key}")

print("\nDashboard static content populated!")
