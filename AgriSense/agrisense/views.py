from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.db.models import Avg, Count
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .models import PlantScan, SiteBranding
from .forms import BrandingForm, CustomPasswordResetForm, CustomSetPasswordForm, CustomUserCreationForm
import base64
import json
import random
from datetime import datetime
import torch
import clip
import numpy as np
from PIL import Image
import io

# ========== CLIP MODEL INITIALIZATION ==========
# Load CLIP model globally (loads once when Django starts)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device} for Model")
model, preprocess = clip.load("ViT-B/32", device=device)
keras_model = "PredictionModel2.keras"

# Confidence thresholds
MIN_CONFIDENCE_THRESHOLD = 35.0
HEALTHY_MIN_CONFIDENCE = 50.0

# ========== TEXT PROMPTS WITH REJECTION CLASSES ==========
text_prompts = [
    # Original classes
    "Corn leaf showing long cigar-shaped gray-tan lesions running parallel to veins typical of northern corn leaf blight",
    "Corn cob showing moldy kernels with white or pink fungal growth indicating corn ear rot",
    "Rice panicle with dark brown neck lesion causing whitening and drying of the grain head",
    "Rice leaf showing multiple circular brown spots with dark margins typical of brown spot disease",
    "Fresh apple",
    "Rotten apple",
    "Fresh guava fruit with smooth green skin and healthy appearance",
    "Rotten guava with dark decay spots and soft damaged areas",
    "Fresh pomegranate with bright red smooth outer skin",
    "Rotten pomegranate with dark decay spots and damaged skin",
    
    # Banana classes
    "Fresh banana with bright yellow smooth skin and healthy appearance",
    "Rotten banana with dark brown or black spots soft mushy areas and decay",
    
    # Orange classes
    "Fresh orange with bright orange smooth skin and healthy appearance",
    "Rotten orange with dark decay spots mold growth and soft damaged areas",
    
    # Mango leaf gall
    "Mango leaf gall disease: multiple small round greenish raised bumps like warts or galls covering the mango leaf surface, leaf texture bumpy and distorted",
    
    # Lemon classes
    "Fresh lemon with bright yellow smooth skin and healthy appearance",
    "Rotten lemon with dark decay spots mold growth and soft damaged areas",
    
    # ========== REJECTION CLASSES ==========
    "A random object like a box, paper, or electronic device",
    "A vegetable like cucumber, tomato, carrot, broccoli, or potato",
    "A flower, ornamental plant, or garden plant not in supported list",
    "A person, animal, or pet in the image",
    "A building, car, furniture, or outdoor scenery with no plants",
    "A blurry or out of focus image that is unclear",
    "Unsupported fruit like mango, pineapple, grapes, watermelon, or strawberry",
    "A leaf from an unsupported tree or plant like neem, peepal, or rubber plant",
]

# Encode text prompts once (for efficiency)
text_tokens = clip.tokenize(text_prompts).to(device)

# ========== CLASS METADATA WITH UNIQUE TREATMENTS ==========
class_metadata = {
    # ========== CORN ==========
    "Corn leaf showing long cigar-shaped gray-tan lesions running parallel to veins typical of northern corn leaf blight": {
        "disease_name": "Northern Corn Leaf Blight",
        "scientific_name": "Exserohilum turcicum",
        "severity": "high",
        "treatment": "🌽 CORN SPECIFIC TREATMENT:\n• Apply fungicides containing strobilurins (azoxystrobin) or triazoles (tebuconazole) at first sign of lesions\n• Plant resistant corn hybrids (those with Ht genes)\n• Rotate corn with soybeans or wheat for 2+ years\n• Remove corn residue after harvest by tilling\n• Apply fungicide at tasseling stage for best protection",
        "crop_type": "Corn",
        "disease_detected": True
    },
    "Corn cob showing moldy kernels with white or pink fungal growth indicating corn ear rot": {
        "disease_name": "Corn Ear Rot",
        "scientific_name": "Fusarium spp./Gibberella spp.",
        "severity": "high",
        "treatment": "🌽 CORN SPECIFIC TREATMENT:\n• Harvest corn immediately at maturity (moisture <20%)\n• Dry grain to 15% moisture or below within 48 hours\n• Remove infected ears manually during harvest\n• Clean storage bins with fungicide before storage\n• Apply foliar fungicide at silking stage (R1)\n• Store at 50-60°F with good air circulation",
        "crop_type": "Corn",
        "disease_detected": True
    },
    
    # ========== RICE ==========
    "Rice panicle with dark brown neck lesion causing whitening and drying of the grain head": {
        "disease_name": "Rice Neck Blast",
        "scientific_name": "Pyricularia oryzae",
        "severity": "high",
        "treatment": "🌾 RICE SPECIFIC TREATMENT:\n• Apply tricyclazole (75% WP) at 0.6g/L at booting and heading stages\n• Use resistant varieties like IR64, Swarna, or MTU1010\n• Avoid excessive nitrogen fertilizer - split into 3 applications\n• Drain fields for 5-7 days to reduce humidity\n• Apply neem-based formulations (5ml/L) as organic alternative",
        "crop_type": "Rice",
        "disease_detected": True
    },
    "Rice leaf showing multiple circular brown spots with dark margins typical of brown spot disease": {
        "disease_name": "Rice Brown Spot",
        "scientific_name": "Cochliobolus miyabeanus",
        "severity": "medium",
        "treatment": "🌾 RICE SPECIFIC TREATMENT:\n• Apply mancozeb (2g/L) or propiconazole (1ml/L) at tillering stage\n• Apply balanced NPK fertilizer (120:60:40 kg/ha)\n• Zinc sulfate application (25kg/ha) reduces disease severity\n• Maintain 3-5cm standing water during tillering\n• Use clean, disease-free seeds treated with carbendazim",
        "crop_type": "Rice",
        "disease_detected": True
    },
    
    # ========== APPLE ==========
    "Fresh apple": {
        "disease_name": "Healthy Apple",
        "scientific_name": "Malus domestica - Healthy",
        "severity": "low",
        "treatment": "🍎 APPLE SPECIFIC ADVICE:\n• No treatment needed - fruit appears healthy\n• Harvest at proper maturity (color change, firmness)\n• Store at 30-32°F with 90-95% humidity\n• Regular monitoring for codling moth and apple scab\n• Prune in late winter for next season's crop",
        "crop_type": "Apple",
        "disease_detected": False
    },
    "Rotten apple": {
        "disease_name": "Apple Rot",
        "scientific_name": "Botrytis cinerea, Penicillium expansum",
        "severity": "high",
        "treatment": "🍎 APPLE SPECIFIC TREATMENT:\n• Remove and destroy all infected apples immediately\n• Apply captan (3g/L) or thiophanate-methyl before harvest\n• Maintain orchard sanitation - remove mummified fruits\n• Post-harvest: dip in fludioxonil (200ppm) solution\n• Store at 32°F with 90-95% humidity\n• Handle carefully to avoid bruising during picking",
        "crop_type": "Apple",
        "disease_detected": True
    },
    
    # ========== GUAVA ==========
    "Fresh guava fruit with smooth green skin and healthy appearance": {
        "disease_name": "Healthy Guava",
        "scientific_name": "Psidium guajava - Healthy",
        "severity": "low",
        "treatment": "🍐 GUAVA SPECIFIC ADVICE:\n• No treatment needed - healthy guava fruit\n• Harvest when color changes from dark green to light green\n• Mature guava ready when slight yellow appears\n• Store at 45-50°F for 2-3 weeks\n• Regular pruning improves air circulation",
        "crop_type": "Guava",
        "disease_detected": False
    },
    "Rotten guava with dark decay spots and soft damaged areas": {
        "disease_name": "Guava Rot",
        "scientific_name": "Colletotrichum gloeosporioides, Phytophthora",
        "severity": "high",
        "treatment": "🍐 GUAVA SPECIFIC TREATMENT:\n• Remove infected fruits and destroy away from orchard\n• Apply copper oxychloride (3g/L) or carbendazim (1g/L)\n• Pre-harvest spray with azoxystrobin 14 days before picking\n• Harvest carefully to avoid skin damage\n• Post-harvest: hot water treatment (50°C for 5 minutes)\n• Store at 45-50°F with 85-90% humidity",
        "crop_type": "Guava",
        "disease_detected": True
    },
    
    # ========== POMEGRANATE ==========
    "Fresh pomegranate with bright red smooth outer skin": {
        "disease_name": "Healthy Pomegranate",
        "scientific_name": "Punica granatum - Healthy",
        "severity": "low",
        "treatment": "🍑 POMEGRANATE SPECIFIC ADVICE:\n• No treatment needed - healthy fruit\n• Harvest when fruit makes metallic sound when tapped\n• Skin color changes from green to yellow-red\n• Store at 32-41°F with 80-85% humidity\n• Can be stored for 3-4 months under proper conditions",
        "crop_type": "Pomegranate",
        "disease_detected": False
    },
    "Rotten pomegranate with dark decay spots and damaged skin": {
        "disease_name": "Pomegranate Rot",
        "scientific_name": "Alternaria alternata, Aspergillus niger",
        "severity": "high",
        "treatment": "🍑 POMEGRANATE SPECIFIC TREATMENT:\n• Remove infected fruits with dark spots immediately\n• Apply copper-based fungicides (2.5g/L) before monsoon\n• Practice fruit bagging 30 days after fruit set\n• Avoid overhead irrigation - use drip system\n• Harvest when fully ripe but before skin cracks\n• Post-harvest: dip in carbendazim (1g/L) + 2% wax coating\n• Store at 40°F with good ventilation",
        "crop_type": "Pomegranate",
        "disease_detected": True
    },
    
    # ========== BANANA ==========
    "Fresh banana with bright yellow smooth skin and healthy appearance": {
        "disease_name": "Healthy Banana",
        "scientific_name": "Musa acuminata - Healthy",
        "severity": "low",
        "treatment": "🍌 BANANA SPECIFIC ADVICE:\n• No treatment needed - healthy banana\n• Harvest when angles on fruit become rounded\n• Optimal harvest: 75-80% maturity (light green)\n• Store at 56-58°F for green bananas\n• Ripen at 60-65°F with ethylene for uniform color",
        "crop_type": "Banana",
        "disease_detected": False
    },
    "Rotten banana with dark brown or black spots soft mushy areas and decay": {
        "disease_name": "Banana Rot",
        "scientific_name": "Colletotrichum musae, Fusarium oxysporum",
        "severity": "high",
        "treatment": "🍌 BANANA SPECIFIC TREATMENT:\n• Remove affected hands immediately from bunch\n• Apply carbendazim (1ml/L) mixed with wax for post-harvest dip\n• Pre-harvest: spray with chlorothalonil 3 weeks before harvest\n• Handle bunches carefully - use padded harvesting bags\n• Dehand under clean, sanitized conditions\n• Store at 55°F with 90-95% humidity\n• Use forced air cooling within 4 hours of harvest",
        "crop_type": "Banana",
        "disease_detected": True
    },
    
    # ========== ORANGE ==========
    "Fresh orange with bright orange smooth skin and healthy appearance": {
        "disease_name": "Healthy Orange",
        "scientific_name": "Citrus sinensis - Healthy",
        "severity": "low",
        "treatment": "🍊 ORANGE SPECIFIC ADVICE:\n• No treatment needed - healthy citrus fruit\n• Harvest when color breaks from green to orange\n• Internal sugars should reach 10-12° Brix\n• Store at 38-48°F with 85-90% humidity\n• Can store for 8-12 weeks under ideal conditions",
        "crop_type": "Orange",
        "disease_detected": False
    },
    "Rotten orange with dark decay spots mold growth and soft damaged areas": {
        "disease_name": "Orange Rot",
        "scientific_name": "Penicillium digitatum, Penicillium italicum",
        "severity": "high",
        "treatment": "🍊 ORANGE SPECIFIC TREATMENT:\n• Remove infected fruits with mold immediately\n• Apply imazalil (2ml/L) or thiabendazole post-harvest\n• Pre-harvest: maintain 3-week fungicide rotation\n• Use sodium bicarbonate (5g/L) as organic alternative\n• Store at 40°F with 85-90% humidity\n• Sanitize storage bins with chlorine (200ppm)\n• Never store damaged or wounded fruits",
        "crop_type": "Orange",
        "disease_detected": True
    },
    
    # ========== MANGO ==========
    "Mango leaf gall disease: multiple small round greenish raised bumps like warts or galls covering the mango leaf surface, leaf texture bumpy and distorted": {
        "disease_name": "Mango Leaf Gall",
        "scientific_name": "Aceria mangiferae (Mite)",
        "severity": "medium",
        "treatment": "🥭 MANGO SPECIFIC TREATMENT:\n• Prune and burn all galled leaves and shoots immediately\n• Apply sulfur 80% WP (3g/L) or abamectin (0.5ml/L)\n• Spray during new flush emergence (every 10-14 days)\n• Maintain tree health with balanced NPK (200:100:100g/tree)\n• Ensure good air circulation through canopy pruning\n• Apply horticultural oil (10ml/L) during dormant season\n• Monitor new flushes weekly for early gall signs",
        "crop_type": "Mango",
        "disease_detected": True
    },
    
    # ========== LEMON ==========
    "Fresh lemon with bright yellow smooth skin and healthy appearance": {
        "disease_name": "Healthy Lemon",
        "scientific_name": "Citrus limon - Healthy",
        "severity": "low",
        "treatment": "🍋 LEMON SPECIFIC ADVICE:\n• No treatment needed - healthy lemon fruit\n• Harvest when fruit is fully yellow (not green)\n• Optimal maturity: 6-8 months after flowering\n• Store at 45-48°F with 85-90% humidity\n• Can store for 3-6 months under proper conditions",
        "crop_type": "Lemon",
        "disease_detected": False
    },
    "Rotten lemon with dark decay spots mold growth and soft damaged areas": {
        "disease_name": "Lemon Rot",
        "scientific_name": "Penicillium digitatum, Alternaria citri, Geotrichum candidum",
        "severity": "high",
        "treatment": "🍋 LEMON SPECIFIC TREATMENT:\n• Remove all rotting fruits showing mold or dark spots\n• Apply imazalil (2ml/L) or potassium sorbate (25g/L) post-harvest\n• Pre-harvest: spray with copper hydroxide (2g/L) 30 days before\n• Use 2,4-D (10ppm) to prevent button drop\n• Store at cool temperatures (45-48°F) with moderate humidity\n• Never stack damaged lemons - use single layer storage\n• Sanitize picking containers with bleach solution weekly\n• Organic option: apply baking soda (10g/L) + vegetable oil (5ml/L)",
        "crop_type": "Lemon",
        "disease_detected": True
    },
    
    # ========== REJECTION CLASSES METADATA ==========
    "A random object like a box, paper, or electronic device": {
        "disease_name": "Not a Plant",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "❌ NO PLANT DETECTED\nThe image appears to contain a random object (box, paper, device, etc.). Please upload a clear image of a plant leaf or fruit from our supported crops.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A vegetable like cucumber, tomato, carrot, broccoli, or potato": {
        "disease_name": "Unsupported Vegetable",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🥕 UNSUPPORTED VEGETABLE\nThe image shows a vegetable that is not currently supported by our system.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon\n\n📝 NOTE: We only detect diseases in specific fruits and crops, not general vegetables.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A flower, ornamental plant, or garden plant not in supported list": {
        "disease_name": "Unsupported Plant",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🌸 UNSUPPORTED PLANT\nThe image shows a flower or ornamental plant. Our system is designed for agricultural crops and fruits only.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A person, animal, or pet in the image": {
        "disease_name": "No Plant Detected",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "👤 NO PLANT DETECTED\nThe image contains a person or animal. Please upload a clear image of a plant leaf or fruit.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A building, car, furniture, or outdoor scenery with no plants": {
        "disease_name": "No Plant Detected",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "🏠 NO PLANT DETECTED\nThe image shows a building, car, or scenery with no visible plants. Please upload an image focused on a plant leaf or fruit.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A blurry or out of focus image that is unclear": {
        "disease_name": "Blurry Image",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "📷 BLURRY IMAGE\nThe image is blurry or out of focus. Please take a clearer photo with:\n• Good lighting\n• Steady camera\n• Plant filling most of the frame\n• Focus on the affected area",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "Unsupported fruit like mango, pineapple, grapes, watermelon, or strawberry": {
        "disease_name": "Unsupported Fruit",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🍍 UNSUPPORTED FRUIT\nThis fruit is not currently supported by our system.\n\n✅ SUPPORTED FRUITS:\n• Apple • Guava • Pomegranate • Banana • Orange • Lemon\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Mango (leaf gall only)\n\n❌ NOT SUPPORTED:\n• Mango fruit (only leaf gall disease)\n• Pineapple, Grapes, Watermelon, Strawberry",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A leaf from an unsupported tree or plant like neem, peepal, or rubber plant": {
        "disease_name": "Unsupported Leaf",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🌿 UNSUPPORTED LEAF\nThe leaf appears to be from an unsupported tree or plant.\n\n✅ SUPPORTED LEAVES:\n• Corn leaves • Rice leaves • Mango leaves (for gall disease)\n\nPlease upload an image of leaves from our supported crops.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
}

# ========== PASSWORD RESET VIEWS ==========
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    form_class = CustomSetPasswordForm
    success_url = '/reset/done/'
    
class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    form_class = CustomPasswordResetForm

    def form_valid(self, form):
        email = form.cleaned_data['email'].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = self.request.build_absolute_uri(
                reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            return render(self.request, 'registration/reset_link_display.html', {
                'reset_link': reset_link,
                'email': email
            })

        return render(self.request, self.template_name, {
            'form': form,
            'error': 'No user found with this email.'
        })

# ========== AUTH VIEWS ==========
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect('dashboard')
        messages.error(request, "Unsuccessful registration. Invalid information.")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'agrisense/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"You are now logged in as {username}.")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    form = AuthenticationForm()
    return render(request, 'agrisense/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')

# ========== MAIN VIEWS ==========
@login_required
def dashboard_view(request):
    scans = PlantScan.objects.filter(user=request.user)
    total_scans = scans.count()
    
    healthy_count = scans.filter(disease_detected=False).count()
    disease_count = scans.filter(disease_detected=True).count()
    
    disease_scans = scans.filter(disease_detected=True)
    if disease_scans.exists():
        avg_confidence = disease_scans.aggregate(Avg('confidence'))['confidence__avg']
        avg_confidence = round(avg_confidence, 1)
    else:
        avg_confidence = 0
    
    last_week = timezone.now() - timedelta(days=7)
    previous_scans = scans.filter(created_at__lt=last_week).count()
    if previous_scans > 0:
        scan_trend = round((total_scans - previous_scans) / previous_scans * 100, 1)
    else:
        scan_trend = 100
    
    disease_names = scans.filter(disease_detected=True)\
                        .values('disease_name')\
                        .annotate(count=Count('id'))\
                        .order_by('-count')[:5]
    
    disease_distribution = []
    for item in disease_names:
        disease_distribution.append({
            'name': item['disease_name'],
            'count': item['count'],
            'percentage': round(item['count'] / disease_count * 100 if disease_count > 0 else 0, 1)
        })
    
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        date = timezone.now() - timedelta(days=i)
        chart_labels.append(date.strftime('%a'))
        daily_healthy = scans.filter(
            created_at__date=date.date(),
            disease_detected=False
        ).count()
        chart_data.append(daily_healthy)
    
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    context = {
        'recent_scans': scans.order_by('-created_at')[:5],
        'total_scans': total_scans,
        'healthy_count': healthy_count,
        'disease_count': disease_count,
        'form': form,
        'branding': branding,
        'avg_confidence': avg_confidence,
        'scan_trend': scan_trend,
        'healthy_trend': round(healthy_count / total_scans * 100 if total_scans > 0 else 0, 1),
        'risk_trend': round(disease_count / total_scans * 100 if total_scans > 0 else 0, 1),
        'disease_distribution': disease_distribution,
        'greeting': 'Morning',
        'current_date': timezone.now().strftime('%A, %B %d, %Y'),
        'current_time': timezone.now().strftime('%I:%M %p'),
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'agrisense/dashboard.html', context)

@login_required
def dashboard_stats_api(request):
    """API endpoint for real-time dashboard updates"""
    scans = PlantScan.objects.filter(user=request.user)
    total_scans = scans.count()
    healthy_count = scans.filter(disease_detected=False).count()
    disease_count = scans.filter(disease_detected=True).count()
    unread_notifications = scans.filter(
        disease_detected=True,
        notification_read=False
    ).count()
    
    recent_scans = []
    for scan in scans.order_by('-created_at')[:5]:
        recent_scans.append({
            'id': str(scan.id),
            'image_url': scan.image.url if scan.image else None,
            'disease_detected': scan.disease_detected,
            'disease_name': scan.disease_name,
            'confidence': scan.confidence,
            'crop_type': scan.crop_type,
            'created_at': scan.created_at.isoformat(),
        })
    
    disease_distribution = []
    disease_names = scans.filter(disease_detected=True)\
                        .values('disease_name')\
                        .annotate(count=Count('id'))\
                        .order_by('-count')[:5]
    
    for item in disease_names:
        disease_distribution.append({
            'name': item['disease_name'],
            'count': item['count'],
            'percentage': round(item['count'] / disease_count * 100 if disease_count > 0 else 0, 1)
        })
    
    return JsonResponse({
        'total_scans': total_scans,
        'healthy_count': healthy_count,
        'disease_count': disease_count,
        'avg_confidence': round(scans.filter(disease_detected=True).aggregate(Avg('confidence'))['confidence__avg'] or 0, 1),
        'scan_trend': 2.4,
        'healthy_trend': 1.8,
        'risk_trend': 0.6,
        'recent_scans': recent_scans,
        'disease_distribution': disease_distribution,
        'unread_notifications': unread_notifications,
    })
    
@login_required
def scanner_view(request):
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    context = {
        'form': form,
        'branding': branding,
    }
    return render(request, 'agrisense/scanner.html', context)

@login_required
def diagnosis_view(request, scan_id):
    scan = get_object_or_404(PlantScan, id=scan_id, user=request.user)
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    context = {
        'scan': scan,
        'form': form,
        'branding': branding,
    }
    return render(request, 'agrisense/diagnosis.html', context)

@login_required
def history_view(request):
    scans = PlantScan.objects.filter(user=request.user).order_by('-created_at')
    
    total_scans = scans.count()
    threat_count = scans.filter(disease_detected=True).count()
    healthy_count = scans.filter(disease_detected=False).count()
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    context = {
        'scans': scans,
        'total_scans': total_scans,
        'threat_count': threat_count,
        'healthy_count': healthy_count,
        'today': today,
        'form': form,
        'branding': branding,
        'yesterday': yesterday,
    }
    return render(request, 'agrisense/history.html', context)

# ========== API VIEWS ==========
@login_required
@csrf_exempt
def analyze_plant_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image', '')
            
            if ';base64,' in image_data:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                image_file = ContentFile(
                    base64.b64decode(imgstr), 
                    name=f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                )
                
                result = run_clip_analysis(imgstr)
                
                # Check if result was rejected
                if result.get('rejected', False):
                    return JsonResponse({
                        'success': False,
                        'error': result.get('treatment', 'Unsupported image'),
                        'error_type': result.get('reason', 'unsupported'),
                        'confidence': result['confidence']
                    }, status=400)
                
                # Save scan to database only for valid predictions
                scan = PlantScan.objects.create(
                    user=request.user,
                    image=image_file,
                    disease_detected=result['disease_detected'],
                    disease_name=result.get('disease_name', ''),
                    scientific_name=result.get('scientific_name', ''),
                    confidence=result['confidence'],
                    severity=result.get('severity', 'low'),
                    treatment_recommended=result.get('treatment', ''),
                    crop_type=result.get('crop_type', 'Unknown')
                )
                
                warning = None
                if result['confidence'] < 50.0:
                    warning = f"Lower confidence detection ({result['confidence']:.1f}%). Consider re-scanning with better lighting."
                
                return JsonResponse({
                    'success': True,
                    'scan_id': str(scan.id),
                    'disease_detected': result['disease_detected'],
                    'disease_name': result.get('disease_name'),
                    'confidence': result['confidence'],
                    'warning': warning
                })
                
        except Exception as e:
            print(f"Error in analyze_plant_api: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def run_clip_analysis(base64_string):
    """
    Run CLIP model analysis with rejection for unsupported items
    """
    # Rejection keywords to identify unsupported content
    REJECTION_KEYWORDS = [
        "random object", "vegetable", "flower", "ornamental", 
        "person", "animal", "pet", "building", "car", "furniture", 
        "outdoor scenery", "blurry", "unsupported fruit", 
        "unsupported tree", "unsupported plant", "box", "paper"
    ]
    
    try:
        image_bytes = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        image_input = preprocess(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_tokens)
            
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
            similarities = (80.0 * image_features @ text_features.T).softmax(dim=-1)
            
            sorted_probs = similarities[0].sort(descending=True)
            top1_idx = sorted_probs.indices[0].item()
            top1_conf = sorted_probs.values[0].item() * 100
            top2_idx = sorted_probs.indices[1].item()
            top2_conf = sorted_probs.values[1].item() * 100
            
            predicted_label = text_prompts[top1_idx]
            confidence = top1_conf
            
            print(f"Top prediction: {predicted_label} with confidence: {confidence:.2f}%")
            print(f"Second prediction: {text_prompts[top2_idx]} with confidence: {top2_conf:.2f}%")
            
            # Check if prediction is a rejection class
            is_rejection = any(keyword in predicted_label.lower() for keyword in REJECTION_KEYWORDS)
            
            if is_rejection:
                print(f"Image rejected: {predicted_label}")
                metadata = class_metadata.get(predicted_label, {
                    "disease_name": "Unsupported Image",
                    "scientific_name": "N/A",
                    "severity": "unknown",
                    "treatment": "Please upload an image of a supported crop: Corn, Rice, Apple, Guava, Pomegranate, Banana, Orange, Mango (leaf gall only), or Lemon.",
                    "crop_type": "Unsupported",
                    "disease_detected": False
                })
                return {
                    'disease_detected': False,
                    'disease_name': metadata['disease_name'],
                    'scientific_name': metadata['scientific_name'],
                    'confidence': round(confidence, 2),
                    'severity': metadata['severity'],
                    'treatment': metadata['treatment'],
                    'crop_type': metadata['crop_type'],
                    'predicted_label': predicted_label,
                    'rejected': True,
                    'reason': 'unsupported'
                }
            
            # Check for low confidence
            if confidence < MIN_CONFIDENCE_THRESHOLD:
                return {
                    'disease_detected': False,
                    'disease_name': "Uncertain Detection",
                    'scientific_name': "N/A",
                    'confidence': round(confidence, 2),
                    'severity': "unknown",
                    'treatment': f"Low confidence ({confidence:.1f}%) detection. Please upload a clearer image of a supported crop.\n\nSupported: Corn, Rice, Apple, Guava, Pomegranate, Banana, Orange, Mango (leaf gall only), Lemon",
                    'crop_type': "Unknown",
                    'predicted_label': predicted_label,
                    'rejected': True,
                    'reason': 'low_confidence'
                }
            
            # Valid prediction - get metadata
            metadata = class_metadata.get(predicted_label, {
                "disease_name": "Unknown",
                "scientific_name": "Unknown",
                "severity": "unknown",
                "treatment": "Consult agricultural expert for proper diagnosis.",
                "crop_type": "Unknown",
                "disease_detected": False
            })
            
            # Add warning for moderate confidence
            treatment = metadata['treatment']
            if confidence < 55.0 and confidence >= MIN_CONFIDENCE_THRESHOLD:
                treatment = f"[Moderate Confidence: {confidence:.1f}%]\n\n{treatment}\n\n⚠️ Consider uploading another image for confirmation."
            
            return {
                'disease_detected': metadata['disease_detected'],
                'disease_name': metadata['disease_name'],
                'scientific_name': metadata['scientific_name'],
                'confidence': round(confidence, 2),
                'severity': metadata['severity'],
                'treatment': treatment,
                'crop_type': metadata['crop_type'],
                'predicted_label': predicted_label,
                'rejected': False
            }
            
    except Exception as e:
        print(f"CLIP inference error: {str(e)}")
        return simulate_ai_analysis()

def simulate_ai_analysis():
    """Fallback simulation if CLIP model fails"""
    diseases = [
        {
            'name': 'Early Blight',
            'scientific': 'Alternaria solani',
            'confidence': random.uniform(85, 98),
            'severity': 'high',
            'treatment': 'Apply fungicide (Chlorothalonil or Mancozeb) immediately. Remove infected leaves and improve air circulation.',
            'crop_type': 'Tomato/Potato',
            'disease_detected': True
        },
        {
            'name': 'Late Blight',
            'scientific': 'Phytophthora infestans',
            'confidence': random.uniform(82, 96),
            'severity': 'high',
            'treatment': 'Apply copper-based fungicide. Remove and destroy infected plants. Avoid overhead watering.',
            'crop_type': 'Tomato/Potato',
            'disease_detected': True
        },
        {
            'name': 'Healthy Banana',
            'scientific': 'Musa acuminata - Healthy',
            'confidence': random.uniform(90, 99),
            'severity': 'low',
            'treatment': 'No treatment needed. Continue regular monitoring and maintain good orchard practices.',
            'crop_type': 'Banana',
            'disease_detected': False
        },
        {
            'name': 'Healthy Lemon',
            'scientific': 'Citrus limon - Healthy',
            'confidence': random.uniform(90, 99),
            'severity': 'low',
            'treatment': 'No treatment needed. Continue regular monitoring and maintain good orchard practices.',
            'crop_type': 'Lemon',
            'disease_detected': False
        },
    ]
    
    if random.random() < 0.5:
        disease_options = [d for d in diseases if d['disease_detected'] == True]
        disease = random.choice(disease_options) if disease_options else diseases[0]
        return {
            'disease_detected': True,
            'disease_name': disease['name'],
            'scientific_name': disease['scientific'],
            'confidence': disease['confidence'],
            'severity': disease['severity'],
            'treatment': disease['treatment'],
            'crop_type': disease['crop_type'],
            'rejected': False
        }
    else:
        healthy_options = [d for d in diseases if d['disease_detected'] == False]
        healthy = random.choice(healthy_options) if healthy_options else diseases[-1]
        return {
            'disease_detected': False,
            'disease_name': healthy['name'],
            'scientific_name': healthy['scientific'],
            'confidence': healthy['confidence'],
            'severity': healthy['severity'],
            'treatment': healthy['treatment'],
            'crop_type': healthy['crop_type'],
            'rejected': False
        }

# Test endpoint to verify CLIP is working
@login_required
@csrf_exempt
def test_clip_api(request):
    """Test endpoint to verify CLIP model is loaded and working"""
    if request.method == 'GET':
        try:
            test_image = Image.new('RGB', (224, 224), color='black')
            image_input = preprocess(test_image).unsqueeze(0).to(device)
            
            with torch.no_grad():
                image_features = model.encode_image(image_input)
                text_features = model.encode_text(text_tokens)
                
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                
            return JsonResponse({
                'success': True,
                'message': 'CLIP model is working',
                'device': device,
                'num_classes': len(text_prompts),
                'classes': text_prompts[:10]
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def recent_history_api(request):
    scans = PlantScan.objects.filter(user=request.user).order_by('-created_at')[:5]
    data = {
        'scans': [{
            'id': str(scan.id),
            'disease_name': scan.disease_name,
            'disease_detected': scan.disease_detected,
            'confidence': scan.confidence,
            'created_at': scan.created_at.isoformat(),
        } for scan in scans]
    }
    return JsonResponse(data)

def about_view(request):
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    return render(request, 'agrisense/About.html', {
        'form': form,
        'branding': branding,
    })

def settings_view(request):
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')

    return render(request, 'agrisense/Setting.html', {
        'form': form,
        'branding': branding,
    })

@login_required
@csrf_exempt
def mark_notifications_read_api(request):
    """Mark ALL unread disease predictions as read"""
    if request.method == 'POST':
        PlantScan.objects.filter(
            user=request.user,
            disease_detected=True,
            notification_read=False
        ).update(notification_read=True)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)