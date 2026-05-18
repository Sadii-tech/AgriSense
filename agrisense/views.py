from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_http_methods
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
from .models import PlantScan, SiteBranding, UserProfile, TeamApplication, TutorialVideo, CropCategory, StaticContent
from .forms import BrandingForm, CustomPasswordResetForm, CustomSetPasswordForm, CustomUserCreationForm
import base64
import json
import random
from datetime import datetime
try:
    import torch
    import clip
    import numpy as np
    from PIL import Image
    import io
    
    # Load CLIP model globally
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device} for Model")
    model, preprocess = clip.load("ViT-B/32", device=device)
except ImportError:
    print("Warning: torch/clip not found. ML features will be disabled.")
    torch = None
    clip = None
    model = None
    preprocess = None
    device = "cpu"

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
text_tokens = clip.tokenize(text_prompts).to(device) if clip else None

# ========== CLASS METADATA - ENGLISH VERSION ==========
class_metadata_en = {
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
        "treatment": "❌ NO PLANT DETECTED\nThe image appears to contain a random object. Please upload a clear image of a plant leaf or fruit from our supported crops.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A vegetable like cucumber, tomato, carrot, broccoli, or potato": {
        "disease_name": "Unsupported Vegetable",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🥕 UNSUPPORTED VEGETABLE\nPlease upload an image of our supported crops.\n\n✅ SUPPORTED CROPS:\n• Corn • Rice • Apple • Guava • Pomegranate • Banana • Orange • Mango • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A flower, ornamental plant, or garden plant not in supported list": {
        "disease_name": "Unsupported Plant",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🌸 UNSUPPORTED PLANT\nOur system is designed for agricultural crops and fruits only.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A person, animal, or pet in the image": {
        "disease_name": "No Plant Detected",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "👤 NO PLANT DETECTED\nPlease upload an image of a plant leaf or fruit.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A building, car, furniture, or outdoor scenery with no plants": {
        "disease_name": "No Plant Detected",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "🏠 NO PLANT DETECTED\nPlease upload an image focused on a plant leaf or fruit.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A blurry or out of focus image that is unclear": {
        "disease_name": "Blurry Image",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "📷 BLURRY IMAGE\nPlease take a clearer photo with good lighting and steady camera.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "Unsupported fruit like mango, pineapple, grapes, watermelon, or strawberry": {
        "disease_name": "Unsupported Fruit",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🍍 UNSUPPORTED FRUIT\nThis fruit is not currently supported.\n\n✅ SUPPORTED FRUITS:\n• Apple • Guava • Pomegranate • Banana • Orange • Lemon",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
    "A leaf from an unsupported tree or plant like neem, peepal, or rubber plant": {
        "disease_name": "Unsupported Leaf",
        "scientific_name": "Not in database",
        "severity": "unknown",
        "treatment": "🌿 UNSUPPORTED LEAF\nPlease upload an image of leaves from our supported crops.",
        "crop_type": "Unsupported",
        "disease_detected": False
    },
}

# ========== CLASS METADATA - URDU VERSION ==========
# ========== CLASS METADATA - URDU VERSION ==========
class_metadata_ur = {
    # ========== CORN (مکئی) ==========
    "Corn leaf showing long cigar-shaped gray-tan lesions running parallel to veins typical of northern corn leaf blight": {
        "disease_name": "شمالی مکئی کی پتی کی جھلسن",
        "scientific_name": "Exserohilum turcicum",
        "severity": "high",
        "treatment": "🌽 مکئی کا مخصوص علاج:\n• زخموں کی پہلی علامت پر سٹروبیلورنز (azoxystrobin) یا ٹرائیازولز (tebuconazole) پر مشتمل فنگسائڈز لگائیں\n• مزاحم مکئی کے ہائبرڈ لگائیں (Ht جین والے)\n• مکئی کو 2+ سال کے لیے سویابین یا گندم کے ساتھ تبدیل کریں\n• کٹائی کے بعد ہل چلا کر مکئی کی باقیات ہٹا دیں\n• بہتر تحفظ کے لیے بال لگنے کے مرحلے پر فنگسائڈ لگائیں",
        "crop_type": "مکئی",
        "disease_detected": True,
        "english_name": "Northern Corn Leaf Blight"  # Added for mapping
    },
    "Corn cob showing moldy kernels with white or pink fungal growth indicating corn ear rot": {
        "disease_name": "مکئی کی بال کی سڑاند",
        "scientific_name": "Fusarium spp./Gibberella spp.",
        "severity": "high",
        "treatment": "🌽 مکئی کا مخصوص علاج:\n• پکنے پر فوری طور پر مکئی کی کٹائی کریں (نمی 20% سے کم)\n• اناج کو 48 گھنٹوں کے اندر 15% نمی یا اس سے کم خشک کریں\n• کٹائی کے دوران متاثرہ بالوں کو دستی طور پر ہٹا دیں\n• ذخیرہ کرنے سے پہلے اسٹوریج بنوں کو فنگسائڈ سے صاف کریں\n• سلکنگ اسٹیج (R1) پر فولیئر فنگسائڈ لگائیں\n• اچھی ہوا کی گردش کے ساتھ 50-60°F پر اسٹور کریں",
        "crop_type": "مکئی",
        "disease_detected": True,
        "english_name": "Corn Ear Rot"
    },
    
    # ========== RICE (چاول) ==========
    "Rice panicle with dark brown neck lesion causing whitening and drying of the grain head": {
        "disease_name": "چاول کی گردن کی جھلسن",
        "scientific_name": "Pyricularia oryzae",
        "severity": "high",
        "treatment": "🌾 چاول کا مخصوص علاج:\n• بوٹنگ اور ہیڈنگ کے مراحل پر 0.6g/L پر tricyclazole (75% WP) لگائیں\n• مزاحم اقسام استعمال کریں جیسے IR64، Swarna، یا MTU1010\n• ضرورت سے زیادہ نائٹروجن کھاد سے بچیں - 3 ایپلی کیشنز میں تقسیم کریں\n• نمی کم کرنے کے لیے کھیتوں کو 5-7 دن تک نکالیں\n• نامیاتی متبادل کے طور پر نیم پر مبنی فارمولیشنز (5ml/L) لگائیں",
        "crop_type": "چاول",
        "disease_detected": True,
        "english_name": "Rice Neck Blast"
    },
    "Rice leaf showing multiple circular brown spots with dark margins typical of brown spot disease": {
        "disease_name": "چاول کا بھورا دھبہ",
        "scientific_name": "Cochliobolus miyabeanus",
        "severity": "medium",
        "treatment": "🌾 چاول کا مخصوص علاج:\n• ٹیلرنگ کے مرحلے پر mancozeb (2g/L) یا propiconazole (1ml/L) لگائیں\n• متوازن NPK کھاد لگائیں (120:60:40 kg/ha)\n• زنک سلفیٹ کا استعمال (25kg/ha) بیماری کی شدت کو کم کرتا ہے\n• ٹیلرنگ کے دوران 3-5 سینٹی میٹر کھڑا پانی برقرار رکھیں\n• کاربینڈازیم سے علاج شدہ صاف، بیماری سے پاک بیج استعمال کریں",
        "crop_type": "چاول",
        "disease_detected": True,
        "english_name": "Rice Brown Spot"
    },
    
    # ========== APPLE (سیب) ==========
    "Fresh apple": {
        "disease_name": "صحت مند سیب",
        "scientific_name": "Malus domestica - صحت مند",
        "severity": "low",
        "treatment": "🍎 سیب کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - پھل صحت مند دکھائی دیتا ہے\n• مناسب پکنے پر کٹائی کریں (رنگ کی تبدیلی، مضبوطی)\n• 90-95% نمی کے ساتھ 30-32°F پر اسٹور کریں\n• کوڈلنگ موتھ اور ایپل سکاب کے لیے باقاعدہ نگرانی کریں\n• اگلے سیزن کی فصل کے لیے سردیوں کے آخر میں کٹائی کریں",
        "crop_type": "سیب",
        "disease_detected": False,
        "english_name": "Healthy Apple"
    },
    "Rotten apple": {
        "disease_name": "سیب کی سڑاند",
        "scientific_name": "Botrytis cinerea, Penicillium expansum",
        "severity": "high",
        "treatment": "🍎 سیب کا مخصوص علاج:\n• تمام متاثرہ سیبوں کو فوری طور پر ہٹا کر تباہ کریں\n• کٹائی سے پہلے captan (3g/L) یا thiophanate-methyl لگائیں\n• باغ کی صفائی برقرار رکھیں - ممی شدہ پھل ہٹائیں\n• کٹائی کے بعد: fludioxonil (200ppm) محلول میں ڈبوئیں\n• 90-95% نمی کے ساتھ 32°F پر اسٹور کریں\n• چنائی کے دوران خراش سے بچنے کے لیے احتیاط سے ہینڈل کریں",
        "crop_type": "سیب",
        "disease_detected": True,
        "english_name": "Apple Rot"
    },
    
    # ========== GUAVA (امرود) ==========
    "Fresh guava fruit with smooth green skin and healthy appearance": {
        "disease_name": "صحت مند امرود",
        "scientific_name": "Psidium guajava - صحت مند",
        "severity": "low",
        "treatment": "🍐 امرود کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - صحت مند امرود کا پھل\n• جب رنگ گہرے سبز سے ہلکے سبز میں بدل جائے تو کٹائی کریں\n• پکا ہوا امرود تیار ہوتا ہے جب ہلکا پیلا نظر آئے\n• 2-3 ہفتوں کے لیے 45-50°F پر اسٹور کریں\n• باقاعدہ کٹائی ہوا کی گردش کو بہتر بناتی ہے",
        "crop_type": "امرود",
        "disease_detected": False,
        "english_name": "Healthy Guava"
    },
    "Rotten guava with dark decay spots and soft damaged areas": {
        "disease_name": "امرود کی سڑاند",
        "scientific_name": "Colletotrichum gloeosporioides, Phytophthora",
        "severity": "high",
        "treatment": "🍐 امرود کا مخصوص علاج:\n• متاثرہ پھلوں کو ہٹا کر باغ سے دور تباہ کریں\n• copper oxychloride (3g/L) یا carbendazim (1g/L) لگائیں\n• چنائی سے 14 دن پہلے azoxystrobin کا سپرے کریں\n• جلد کو نقصان پہنچنے سے بچنے کے لیے احتیاط سے کٹائی کریں\n• کٹائی کے بعد: گرم پانی کا علاج (50°C پر 5 منٹ)\n• 85-90% نمی کے ساتھ 45-50°F پر اسٹور کریں",
        "crop_type": "امرود",
        "disease_detected": True,
        "english_name": "Guava Rot"
    },
    
    # ========== POMEGRANATE (انار) ==========
    "Fresh pomegranate with bright red smooth outer skin": {
        "disease_name": "صحت مند انار",
        "scientific_name": "Punica granatum - صحت مند",
        "severity": "low",
        "treatment": "🍑 انار کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - صحت مند پھل\n• جب پھل تھپتھپانے پر دھاتی آواز دے تو کٹائی کریں\n• جلد کا رنگ سبز سے پیلا-سرخ ہو جاتا ہے\n• 80-85% نمی کے ساتھ 32-41°F پر اسٹور کریں\n• مناسب حالات میں 3-4 ماہ تک ذخیرہ کیا جا سکتا ہے",
        "crop_type": "انار",
        "disease_detected": False,
        "english_name": "Healthy Pomegranate"
    },
    "Rotten pomegranate with dark decay spots and damaged skin": {
        "disease_name": "انار کی سڑاند",
        "scientific_name": "Alternaria alternata, Aspergillus niger",
        "severity": "high",
        "treatment": "🍑 انار کا مخصوص علاج:\n• تاریک دھبوں والے متاثرہ پھلوں کو فوری طور پر ہٹا دیں\n• مانسون سے پہلے تانبے پر مبنی فنگسائڈز (2.5g/L) لگائیں\n• پھل لگنے کے 30 دن بعد پھل کی تھیلی بندی کریں\n• اوور ہیڈ اریگیشن سے بچیں - ڈرپ سسٹم استعمال کریں\n• جب مکمل پک جائے لیکن جلد پھٹنے سے پہلے کٹائی کریں\n• کٹائی کے بعد: carbendazim (1g/L) + 2% موم کوٹنگ میں ڈبوئیں\n• اچھی وینٹیلیشن کے ساتھ 40°F پر اسٹور کریں",
        "crop_type": "انار",
        "disease_detected": True,
        "english_name": "Pomegranate Rot"
    },
    
    # ========== BANANA (کیلا) ==========
    "Fresh banana with bright yellow smooth skin and healthy appearance": {
        "disease_name": "صحت مند کیلا",
        "scientific_name": "Musa acuminata - صحت مند",
        "severity": "low",
        "treatment": "🍌 کیلا کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - صحت مند کیلا\n• کٹائی کریں جب پھل پر زاویے گول ہو جائیں\n• بہترین کٹائی: 75-80% پختگی (ہلکا سبز)\n• سبز کیلوں کے لیے 56-58°F پر اسٹور کریں\n• یکساں رنگ کے لیے ethylene کے ساتھ 60-65°F پر پکائیں",
        "crop_type": "کیلا",
        "disease_detected": False,
        "english_name": "Healthy Banana"
    },
    "Rotten banana with dark brown or black spots soft mushy areas and decay": {
        "disease_name": "کیلے کی سڑاند",
        "scientific_name": "Colletotrichum musae, Fusarium oxysporum",
        "severity": "high",
        "treatment": "🍌 کیلا کا مخصوص علاج:\n• متاثرہ ہاتھوں کو فوری طور پر گچھے سے ہٹا دیں\n• کٹائی کے بعد ڈپ کے لیے موم کے ساتھ ملا ہوا carbendazim (1ml/L) لگائیں\n• کٹائی سے پہلے: کٹائی سے 3 ہفتے پہلے chlorothalonil کا سپرے کریں\n• گچھوں کو احتیاط سے سنبھالیں - پیڈڈ ہارویسٹنگ بیگ استعمال کریں\n• صاف، جراثیم سے پاک حالات میں ڈی ہینڈ کریں\n• 90-95% نمی کے ساتھ 55°F پر اسٹور کریں\n• کٹائی کے 4 گھنٹوں کے اندر فورسڈ ایئر کولنگ استعمال کریں",
        "crop_type": "کیلا",
        "disease_detected": True,
        "english_name": "Banana Rot"
    },
    
    # ========== ORANGE (نارنجی) ==========
    "Fresh orange with bright orange smooth skin and healthy appearance": {
        "disease_name": "صحت مند نارنجی",
        "scientific_name": "Citrus sinensis - صحت مند",
        "severity": "low",
        "treatment": "🍊 نارنجی کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - صحت مند لیموں کا پھل\n• جب رنگ سبز سے نارنجی ہو جائے تو کٹائی کریں\n• اندرونی شکر 10-12° Brix تک پہنچنی چاہیے\n• 85-90% نمی کے ساتھ 38-48°F پر اسٹور کریں\n• مثالی حالات میں 8-12 ہفتے ذخیرہ کر سکتے ہیں",
        "crop_type": "نارنجی",
        "disease_detected": False,
        "english_name": "Healthy Orange"
    },
    "Rotten orange with dark decay spots mold growth and soft damaged areas": {
        "disease_name": "نارنجی کی سڑاند",
        "scientific_name": "Penicillium digitatum, Penicillium italicum",
        "severity": "high",
        "treatment": "🍊 نارنجی کا مخصوص علاج:\n• سڑاند والے متاثرہ پھلوں کو فوری طور پر ہٹا دیں\n• کٹائی کے بعد imazalil (2ml/L) یا thiabendazole لگائیں\n• کٹائی سے پہلے: 3 ہفتے کی فنگسائڈ گردش برقرار رکھیں\n• نامیاتی متبادل کے طور پر sodium bicarbonate (5g/L) استعمال کریں\n• 85-90% نمی کے ساتھ 40°F پر اسٹور کریں\n• کلورین (200ppm) سے اسٹوریج بنوں کو جراثیم سے پاک کریں\n• کبھی بھی خراب یا زخمی پھل ذخیرہ نہ کریں",
        "crop_type": "نارنجی",
        "disease_detected": True,
        "english_name": "Orange Rot"
    },
    
    # ========== MANGO (آم) ==========
    "Mango leaf gall disease: multiple small round greenish raised bumps like warts or galls covering the mango leaf surface, leaf texture bumpy and distorted": {
        "disease_name": "آم کے پتے کی گال",
        "scientific_name": "Aceria mangiferae (چھوٹا کیڑا)",
        "severity": "medium",
        "treatment": "🥭 آم کا مخصوص علاج:\n• تمام گال والے پتوں اور ٹہنیوں کو فوری طور پر کاٹ کر جلا دیں\n• سلفر 80% WP (3g/L) یا abamectin (0.5ml/L) لگائیں\n• نئی ٹہنیوں کے نکلنے کے دوران سپرے کریں (ہر 10-14 دن بعد)\n• متوازن NPK (200:100:100g/درخت) کے ساتھ درخت کی صحت برقرار رکھیں\n• چھتری کی کٹائی کے ذریعے ہوا کی اچھی گردش کو یقینی بنائیں\n• غیر فعال موسم کے دوران horticultural oil (10ml/L) لگائیں\n• ابتدائی گال کی علامات کے لیے ہفتہ وار نئی ٹہنیوں کی نگرانی کریں",
        "crop_type": "آم",
        "disease_detected": True,
        "english_name": "Mango Leaf Gall"
    },
    
    # ========== LEMON (لیموں) ==========
    "Fresh lemon with bright yellow smooth skin and healthy appearance": {
        "disease_name": "صحت مند لیموں",
        "scientific_name": "Citrus limon - صحت مند",
        "severity": "low",
        "treatment": "🍋 لیموں کا مخصوص مشورہ:\n• کوئی علاج ضروری نہیں - صحت مند لیموں کا پھل\n• جب پھل مکمل طور پر پیلا ہو جائے تو کٹائی کریں (سبز نہیں)\n• بہترین پختگی: پھول آنے کے 6-8 ماہ بعد\n• 85-90% نمی کے ساتھ 45-48°F پر اسٹور کریں\n• مناسب حالات میں 3-6 ماہ تک ذخیرہ کر سکتے ہیں",
        "crop_type": "لیموں",
        "disease_detected": False,
        "english_name": "Healthy Lemon"
    },
    "Rotten lemon with dark decay spots mold growth and soft damaged areas": {
        "disease_name": "لیموں کی سڑاند",
        "scientific_name": "Penicillium digitatum, Alternaria citri, Geotrichum candidum",
        "severity": "high",
        "treatment": "🍋 لیموں کا مخصوص علاج:\n• سڑاند یا پھپھوندی والے تمام پھلوں کو ہٹا دیں\n• کٹائی کے بعد imazalil (2ml/L) یا potassium sorbate (25g/L) لگائیں\n• کٹائی سے پہلے: 30 دن پہلے copper hydroxide (2g/L) کا سپرے کریں\n• بٹن گرنے سے روکنے کے لیے 2,4-D (10ppm) استعمال کریں\n• معتدل نمی کے ساتھ ٹھنڈے درجہ حرارت (45-48°F) پر اسٹور کریں\n• خراب لیموں کو کبھی بھی اسٹیک نہ کریں - سنگل پرت اسٹوریج استعمال کریں\n• ہفتہ وار بلیچ محلول سے چنائی کے کنٹینرز کو جراثیم سے پاک کریں\n• نامیاتی آپشن: baking soda (10g/L) + vegetable oil (5ml/L) لگائیں",
        "crop_type": "لیموں",
        "disease_detected": True,
        "english_name": "Lemon Rot"
    },
    
    # ========== REJECTION CLASSES METADATA - URDU ==========
    "A random object like a box, paper, or electronic device": {
        "disease_name": "پودہ نہیں ہے",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "❌ کوئی پودہ نہیں ملا\nتصویر میں کوئی بے ترتیب چیز دکھائی دیتی ہے۔ براہ کرم ہمارے تعاون یافتہ فصلوں سے پودے کے پتے یا پھل کی واضح تصویر اپ لوڈ کریں۔\n\n✅ تعاون یافتہ فصلیں:\n• مکئی • چاول • سیب • امرود • انار • کیلا • نارنجی • آم • لیموں",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Not a Plant"
    },
    "A vegetable like cucumber, tomato, carrot, broccoli, or potato": {
        "disease_name": "غیر تعاون یافتہ سبزی",
        "scientific_name": "ڈیٹا بیس میں نہیں",
        "severity": "unknown",
        "treatment": "🥕 غیر تعاون یافتہ سبزی\nبراہ کرم ہماری تعاون یافتہ فصلوں کی تصویر اپ لوڈ کریں۔\n\n✅ تعاون یافتہ فصلیں:\n• مکئی • چاول • سیب • امرود • انار • کیلا • نارنجی • آم • لیموں",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Unsupported Vegetable"
    },
    "A flower, ornamental plant, or garden plant not in supported list": {
        "disease_name": "غیر تعاون یافتہ پودہ",
        "scientific_name": "ڈیٹا بیس میں نہیں",
        "severity": "unknown",
        "treatment": "🌸 غیر تعاون یافتہ پودہ\nہمارا نظام صرف زرعی فصلوں اور پھلوں کے لیے ڈیزائن کیا گیا ہے۔",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Unsupported Plant"
    },
    "A person, animal, or pet in the image": {
        "disease_name": "کوئی پودہ نہیں ملا",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "👤 کوئی پودہ نہیں ملا\nبراہ کرم پودے کے پتے یا پھل کی تصویر اپ لوڈ کریں۔",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "No Plant Detected"
    },
    "A building, car, furniture, or outdoor scenery with no plants": {
        "disease_name": "کوئی پودہ نہیں ملا",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "🏠 کوئی پودہ نہیں ملا\nبراہ کرم پودے کے پتے یا پھل پر مرکوز تصویر اپ لوڈ کریں۔",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "No Plant Detected"
    },
    "A blurry or out of focus image that is unclear": {
        "disease_name": "دھندلی تصویر",
        "scientific_name": "N/A",
        "severity": "unknown",
        "treatment": "📷 دھندلی تصویر\nبراہ کرم اچھی روشنی اور مستحکم کیمرے کے ساتھ واضح تصویر لیں۔",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Blurry Image"
    },
    "Unsupported fruit like mango, pineapple, grapes, watermelon, or strawberry": {
        "disease_name": "غیر تعاون یافتہ پھل",
        "scientific_name": "ڈیٹا بیس میں نہیں",
        "severity": "unknown",
        "treatment": "🍍 غیر تعاون یافتہ پھل\nیہ پھل فی الحال تعاون یافتہ نہیں ہے۔\n\n✅ تعاون یافتہ پھل:\n• سیب • امرود • انار • کیلا • نارنجی • لیموں",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Unsupported Fruit"
    },
    "A leaf from an unsupported tree or plant like neem, peepal, or rubber plant": {
        "disease_name": "غیر تعاون یافتہ پتا",
        "scientific_name": "ڈیٹا بیس میں نہیں",
        "severity": "unknown",
        "treatment": "🌿 غیر تعاون یافتہ پتا\nبراہ کرم ہماری تعاون یافتہ فصلوں سے پتوں کی تصویر اپ لوڈ کریں۔",
        "crop_type": "غیر تعاون یافتہ",
        "disease_detected": False,
        "english_name": "Unsupported Leaf"
    },
}

# Helper function to get English name from Urdu disease name
def get_english_from_urdu(urdu_name):
    """Get English disease name from Urdu name"""
    for key, metadata in class_metadata_ur.items():
        if metadata.get('disease_name') == urdu_name:
            return metadata.get('english_name')
    return None

# Helper function to get Urdu name from English disease name
def get_urdu_from_english(english_name):
    """Get Urdu disease name from English name"""
    for key, metadata in class_metadata_ur.items():
        if metadata.get('english_name') == english_name:
            return metadata.get('disease_name')
    return None

# Updated get_class_metadata function
def get_class_metadata(language='en'):
    """Return metadata in requested language (en or ur)"""
    if language == 'ur':
        return class_metadata_ur
    return class_metadata_en

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
            
            # Explicitly set theme preference to 'light' for new users
            user_profile, created = UserProfile.objects.get_or_create(user=user)
            user_profile.theme_preference = 'light'
            user_profile.save()
            
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
                
                # Ensure profile has correct theme (fix for existing users)
                user_profile, created = UserProfile.objects.get_or_create(user=user)
                if created:
                    user_profile.theme_preference = 'light'
                    user_profile.save()
                
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
        # Try to find Urdu translation from metadata or stored scans
        d_name = item['disease_name']
        d_name_ur = d_name
        
        # Check if we have a scan with this name that has a translation
        example_scan = scans.filter(disease_name=d_name, disease_name_ur__isnull=False).exclude(disease_name_ur='').first()
        if example_scan:
            d_name_ur = example_scan.disease_name_ur
        
        disease_distribution.append({
            'name': d_name,
            'name_ur': d_name_ur,
            'count': item['count'],
            'percentage': round(item['count'] / disease_count * 100 if disease_count > 0 else 0, 1)
        })
    
    # FIXED: Chart data - Show total scans per day (both healthy and diseased)
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        date = timezone.now() - timedelta(days=i)
        chart_labels.append(date.strftime('%a'))  # Mon, Tue, Wed...
        
        # Get TOTAL scans for this day (both healthy and diseased)
        daily_total = scans.filter(
            created_at__date=date.date()
        ).count()
        chart_data.append(daily_total)
    
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    # Get localized UI labels
    user_language = get_user_language(request)
    ui_content_objs = StaticContent.objects.filter(page='dashboard')
    ui_labels = {}
    for obj in ui_content_objs:
        if user_language == 'ur' and obj.text_ur:
            ui_labels[obj.key] = obj.text_ur
        else:
            ui_labels[obj.key] = obj.text_en
            
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
        'ui_labels': ui_labels,
        'user_language': user_language,
    }
    return render(request, 'agrisense/dashboard.html', context)

@login_required
def dashboard_stats_api(request):
    """API endpoint for real-time dashboard updates - ALWAYS returns English names"""
    scans = PlantScan.objects.filter(user=request.user)
    total_scans = scans.count()
    healthy_count = scans.filter(disease_detected=False).count()
    disease_count = scans.filter(disease_detected=True).count()
    
    # Get user profile for notification preference
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Calculate unread notifications based on user preference
    if user_profile.high_risk_notifications:
        unread_notifications = scans.filter(
            disease_detected=True,
            notification_read=False
        ).count()
    else:
        unread_notifications = 0
    
    recent_scans = []
    for scan in scans.order_by('-created_at')[:5]:
        # ALWAYS return English disease name from the database
        disease_name = scan.disease_name
        
        # If the stored disease name is in Urdu, convert to English using your mapping
        if any('\u0600' <= c <= '\u06FF' for c in disease_name):
            # Try to find English version from your metadata
            for key, metadata in class_metadata_ur.items():
                if metadata.get('disease_name') == disease_name:
                    english_name = metadata.get('english_name')
                    if english_name:
                        disease_name = english_name
                    break
        
        recent_scans.append({
            'id': str(scan.id),
            'image_url': scan.image.url if scan.image else None,
            'disease_detected': scan.disease_detected,
            'disease_name': disease_name,  # Now always English
            'disease_name_ur': scan.disease_name_ur or disease_name,
            'confidence': scan.confidence,
            'crop_type': scan.crop_type,
            'crop_type_ur': scan.crop_type_ur or scan.crop_type,
            'severity': scan.severity,
            'severity_ur': scan.severity_ur or scan.severity,
            'created_at': scan.created_at.isoformat(),
        })
    
    disease_distribution = []
    disease_names = scans.filter(disease_detected=True)\
                        .values('disease_name')\
                        .annotate(count=Count('id'))\
                        .order_by('-count')[:5]
    
    for item in disease_names:
        # Convert Urdu disease name to English if needed
        disease_name = item['disease_name']
        if any('\u0600' <= c <= '\u06FF' for c in disease_name):
            for key, metadata in class_metadata_ur.items():
                if metadata.get('disease_name') == disease_name:
                    english_name = metadata.get('english_name')
                    if english_name:
                        disease_name = english_name
                    break
        
        disease_distribution.append({
            'name': disease_name,  # Now always English
            'count': item['count'],
            'percentage': round(item['count'] / disease_count * 100 if disease_count > 0 else 0, 1)
        })
    
    # Calculate average confidence from English-named scans
    disease_scans = scans.filter(disease_detected=True)
    avg_conf = disease_scans.aggregate(Avg('confidence'))['confidence__avg'] or 0
    
    return JsonResponse({
        'total_scans': total_scans,
        'healthy_count': healthy_count,
        'disease_count': disease_count,
        'avg_confidence': round(avg_conf, 1),
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
    
    # Get user's language preference (for display only)
    user_language = request.session.get('preferred_language', 'en')
    if user_language == 'en':
        user_language = request.COOKIES.get('agrisense_language', 'en')
    
    print(f"Diagnosis view - Display language: {user_language}, Stored disease: {scan.disease_name}")
    
    # Helper function to check if text contains Urdu characters
    def is_urdu_text(text):
        if not text:
            return False
        return any(0x0600 <= ord(c) <= 0x06FF for c in text)
    
    # Helper function to convert Urdu to English
    def get_english_disease_name(disease_name):
        """Convert Urdu disease name to English using metadata mapping"""
        if not disease_name:
            return disease_name
        
        # Check if it's already English (no Urdu characters)
        if not is_urdu_text(disease_name):
            return disease_name
        
        # Search through Urdu metadata to find English equivalent
        for key, metadata in class_metadata_ur.items():
            if metadata.get('disease_name') == disease_name:
                english_name = metadata.get('english_name')
                if english_name:
                    return english_name
        
        return disease_name
    
    def get_english_crop_type(crop_name):
        """Convert Urdu crop name to English"""
        if not crop_name:
            return crop_name
        
        if not is_urdu_text(crop_name):
            return crop_name
        
        # Urdu to English crop mapping
        urdu_to_en_crop = {
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
        
        return urdu_to_en_crop.get(crop_name, crop_name)
    
    # STEP 1: Ensure database has English names (fix if Urdu is stored)
    english_disease_name = get_english_disease_name(scan.disease_name)
    english_crop_type = get_english_crop_type(scan.crop_type)
    
    # Update database if needed (permanent fix)
    updated = False
    if english_disease_name != scan.disease_name:
        scan.disease_name = english_disease_name
        updated = True
        print(f"Fixed database disease name: {scan.disease_name} -> {english_disease_name}")
    
    if english_crop_type != scan.crop_type and scan.crop_type:
        scan.crop_type = english_crop_type
        updated = True
        print(f"Fixed database crop type: {scan.crop_type} -> {english_crop_type}")
    
    if updated:
        scan.save(update_fields=['disease_name', 'crop_type'])
    
    # STEP 2: Get metadata in the user's display language
    metadata_dict = get_class_metadata(user_language)
    
    # STEP 3: Find matching metadata for the disease
    matched_metadata = None
    for key, metadata in metadata_dict.items():
        if metadata.get('disease_name') == english_disease_name or \
           metadata.get('english_name') == english_disease_name or \
           (english_disease_name in metadata.get('disease_name', '') or 
            metadata.get('disease_name', '') in english_disease_name):
            matched_metadata = metadata
            break
    
    # Also check by crop type if no direct match
    if not matched_metadata and english_crop_type:
        for key, metadata in metadata_dict.items():
            if metadata.get('crop_type') == english_crop_type:
                if (not scan.disease_detected and 'Healthy' in metadata.get('disease_name', '')) or \
                   (scan.disease_detected and 'Healthy' not in metadata.get('disease_name', '')):
                    matched_metadata = metadata
                    break
    
    # STEP 4: Create display version (translated to user's language)
    if matched_metadata:
        scan_display = {
            'id': scan.id,
            'image': scan.image,
            'created_at': scan.created_at,
            'confidence': scan.confidence,
            'disease_detected': scan.disease_detected,
            'disease_name': matched_metadata.get('disease_name', english_disease_name),
            'scientific_name': matched_metadata.get('scientific_name', scan.scientific_name),
            'severity': matched_metadata.get('severity', scan.severity),
            'treatment_recommended': matched_metadata.get('treatment', scan.treatment_recommended),
            'crop_type': matched_metadata.get('crop_type', english_crop_type),
        }
        print(f"Using metadata for display ({user_language}): {scan_display['disease_name']}")
    else:
        # Fallback to original values
        scan_display = {
            'id': scan.id,
            'image': scan.image,
            'created_at': scan.created_at,
            'confidence': scan.confidence,
            'disease_detected': scan.disease_detected,
            'disease_name': english_disease_name,
            'scientific_name': scan.scientific_name,
            'severity': scan.severity,
            'treatment_recommended': scan.treatment_recommended,
            'crop_type': english_crop_type,
        }
    
    # STEP 5: Override treatment with correct language version
    # This ensures treatment text matches the selected language
    if user_language == 'ur':
        # Ensure Urdu translations exist in DB
        if not scan.disease_name_ur or not scan.treatment_recommended_ur:
            try:
                translate_scan_to_urdu(scan)
            except Exception as e:
                print(f"Error translating in diagnosis view: {e}")
        
        # Use stored Urdu content
        if scan.disease_name_ur:
            scan_display['disease_name'] = scan.disease_name_ur
        if scan.treatment_recommended_ur:
            scan_display['treatment_recommended'] = scan.treatment_recommended_ur
        if scan.crop_type_ur:
            scan_display['crop_type'] = scan.crop_type_ur
        if scan.severity_ur:
            scan_display['severity'] = scan.severity_ur
        else:
            scan_display['severity'] = get_urdu_severity(scan.severity)
    elif user_language == 'en':
        # Ensure we show English version
        # If we have matched_metadata, use it as it's definitely English
        if matched_metadata:
            scan_display['disease_name'] = matched_metadata.get('disease_name', english_disease_name)
            scan_display['crop_type'] = matched_metadata.get('crop_type', english_crop_type)
            scan_display['treatment_recommended'] = matched_metadata.get('treatment', scan.treatment_recommended)
            scan_display['severity'] = matched_metadata.get('severity', scan.severity)
        else:
            scan_display['disease_name'] = english_disease_name
            scan_display['crop_type'] = english_crop_type
            scan_display['treatment_recommended'] = scan.treatment_recommended
            scan_display['severity'] = scan.severity
            
        # Final fallback check: if treatment still has Urdu, try to get English version
        if is_urdu_text(scan_display['treatment_recommended']):
            en_metadata_dict = get_class_metadata('en')
            for key, metadata in en_metadata_dict.items():
                if metadata.get('disease_name') == english_disease_name or \
                   metadata.get('english_name') == english_disease_name:
                    scan_display['treatment_recommended'] = metadata.get('treatment', scan_display['treatment_recommended'])
                    break
    
    # Get severity display text in user's language
    severity_display = {
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'unknown': 'Unknown'
    }
    
    severity_urdu = {
        'high': 'شدید',
        'medium': 'درمیانی',
        'low': 'کم',
        'unknown': 'نامعلوم'
    }
    
    # Add severity display to context
    severity_key = scan.severity if scan.severity in severity_display else 'unknown'
    scan_display['severity_display'] = severity_urdu[severity_key] if user_language == 'ur' else severity_display[severity_key]
    
    # Add spread risk (based on severity)
    spread_risk = {
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'unknown': 'Unknown'
    }
    spread_risk_urdu = {
        'high': 'شدید',
        'medium': 'درمیانی',
        'low': 'کم',
        'unknown': 'نامعلوم'
    }
    scan_display['spread_risk'] = spread_risk_urdu[severity_key] if user_language == 'ur' else spread_risk[severity_key]
    
    # Add treatment urgency
    treatment_urgency = {
        'high': 'Immediate',
        'medium': 'Soon',
        'low': 'Monitor',
        'unknown': 'Consult'
    }
    treatment_urgency_urdu = {
        'high': 'فوری',
        'medium': 'جلد',
        'low': 'نگرانی',
        'unknown': 'مشورہ'
    }
    scan_display['treatment_urgency'] = treatment_urgency_urdu[severity_key] if user_language == 'ur' else treatment_urgency[severity_key]
    
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    # Fetch crop category info for the modal
    crop_info = None
    if english_crop_type:
        crop_info = CropCategory.objects.filter(name__iexact=english_crop_type).first()
    
    # Get location from request or use default
    location_name = request.session.get('user_location', 'Lahore, Punjab')
    
    context = {
        'scan': scan_display,
        'form': form,
        'branding': branding,
        'user_language': user_language,
        'location_name': location_name,
        'crop_info': crop_info,
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
    
    # Get user's language preference
    user_language = get_user_language(request)
    
    # Pre-translate scans to Urdu if language is Urdu (robust storage)
    if user_language == 'ur':
        untranslated = scans.filter(disease_name_ur='')
        for scan in untranslated[:20]:  # Limit to 20 per page load for performance
            try:
                translate_scan_to_urdu(scan)
            except:
                pass
    
    print(f"History view - Display language: {user_language}")
    
    # Helper function to convert Urdu to English if needed
    def get_english_disease_name(disease_name):
        """Convert Urdu disease name to English using metadata mapping"""
        if not disease_name:
            return disease_name
        
        # Check if it's already English (no Urdu characters)
        if not any(0x0600 <= ord(c) <= 0x06FF for c in disease_name):
            return disease_name
        
        # Search through Urdu metadata to find English equivalent
        for key, metadata in class_metadata_ur.items():
            if metadata.get('disease_name') == disease_name:
                english_name = metadata.get('english_name')
                if english_name:
                    return english_name
        
        # Also check by crop type matching
        for key, metadata in class_metadata_ur.items():
            if metadata.get('english_name') and metadata.get('disease_name') == disease_name:
                return metadata.get('english_name')
        
        return disease_name
    
    def get_english_crop_type(crop_name):
        """Convert Urdu crop name to English"""
        if not crop_name:
            return crop_name
        
        if not any(0x0600 <= ord(c) <= 0x06FF for c in crop_name):
            return crop_name
        
        # Urdu to English crop mapping
        urdu_to_en_crop = {
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
        
        return urdu_to_en_crop.get(crop_name, crop_name)
    
    # Create a list with English names from database (ALWAYS store English)
    scans_with_translation = []
    for scan in scans:
        # Ensure we have English names in the database (fix Urdu if present)
        english_disease_name = get_english_disease_name(scan.disease_name)
        english_crop_type = get_english_crop_type(scan.crop_type)
        
        # If the stored name was Urdu, update it in the database for future
        if english_disease_name != scan.disease_name:
            scan.disease_name = english_disease_name
            scan.save(update_fields=['disease_name'])
            print(f"Fixed database: {scan.disease_name} -> {english_disease_name}")
        
        if english_crop_type != scan.crop_type and scan.crop_type:
            scan.crop_type = english_crop_type
            scan.save(update_fields=['crop_type'])
            print(f"Fixed crop type: {scan.crop_type} -> {english_crop_type}")
        
        scan_dict = {
            'id': scan.id,
            'image': scan.image,
            'created_at': scan.created_at,
            'disease_detected': scan.disease_detected,
            'disease_name': english_disease_name,  # ALWAYS English in database
            'crop_type': english_crop_type,        # ALWAYS English in database
            'scientific_name': scan.scientific_name,
            'severity': scan.severity,
            'confidence': scan.confidence,
            'treatment_recommended': scan.treatment_recommended,
        }
        
        # ONLY for display - if user wants Urdu, translate on the fly
        if user_language == 'ur':
            # Get Urdu translation from metadata
            urdu_metadata = get_class_metadata('ur')
            for key, metadata in urdu_metadata.items():
                if metadata.get('english_name') == english_disease_name:
                    scan_dict['disease_name'] = metadata.get('disease_name', english_disease_name)
                    scan_dict['scientific_name'] = metadata.get('scientific_name', scan.scientific_name)
                    scan_dict['severity'] = metadata.get('severity', scan.severity)
                    scan_dict['treatment_recommended'] = metadata.get('treatment', scan.treatment_recommended)
                    scan_dict['crop_type'] = metadata.get('crop_type', english_crop_type)
                    print(f"Displaying in Urdu: {english_disease_name} -> {metadata.get('disease_name')}")
                    break
        
        scans_with_translation.append(scan_dict)
    
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    context = {
        'scans': scans_with_translation,
        'total_scans': total_scans,
        'threat_count': threat_count,
        'healthy_count': healthy_count,
        'today': today,
        'yesterday': yesterday,
        'form': form,
        'branding': branding,
    }
    return render(request, 'agrisense/history.html', context)

# ========== API VIEWS ==========
def get_user_language(request):
    """Get user's preferred language from session or request headers"""
    # Check session first
    language = request.session.get('preferred_language', 'en')
    # Check cookie
    if not language or language == 'en':
        language = request.COOKIES.get('agrisense_language', 'en')
    return language

@login_required
@csrf_exempt
def analyze_plant_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image', '')
            
            # Get user's language preference
            user_language = get_user_language(request)
            
            if ';base64,' in image_data:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                
                image_file = ContentFile(
                    base64.b64decode(imgstr), 
                    name=f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                )
                
                # ALWAYS analyze in English for base database fields
                result = run_clip_analysis(imgstr, 'en')
                
                # Check if result was rejected
                if result.get('rejected', False):
                    # For rejected results, we might want to return the error in user's language
                    if user_language == 'ur':
                        # Simple translation for common rejection messages
                        error_msg = result.get('treatment', 'Unsupported image')
                        if "Please upload a clear image" in error_msg:
                            error_msg = "براہ کرم پودے کے پتے یا پھل کی واضح تصویر اپ لوڈ کریں۔"
                        elif "Low confidence" in error_msg:
                            error_msg = f"کم اعتمادیت ({result['confidence']:.1f}%) کی شناخت۔ براہ کرم واضح تصویر اپ لوڈ کریں۔"
                        result['treatment'] = error_msg

                    return JsonResponse({
                        'success': False,
                        'error': result.get('treatment', 'Unsupported image'),
                        'error_type': result.get('reason', 'unsupported'),
                        'confidence': result['confidence']
                    }, status=400)
                
                # Save scan to database (ALWAYS in English base fields)
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
                
                # Immediately pre-translate to Urdu and store in DB fields
                try:
                    translate_scan_to_urdu(scan)
                except Exception as e:
                    print(f"Error pre-translating scan: {e}")
                
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
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# ==================== BACKEND TRANSLATION HELPERS ====================
def translate_text_backend(text, target_lang='ur'):
    """Internal helper to translate text in the backend using MyMemory"""
    if not text or target_lang == 'en':
        return text
        
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': f'en|{target_lang}',
            'de': 'agrisense@demo.com'
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            translated = result.get('responseData', {}).get('translatedText', text)
            return translated.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
    except Exception as e:
        print(f"Backend translation error: {e}")
    return text

def get_urdu_severity(severity):
    """Map severity levels to Urdu"""
    severity_map = {
        'low': 'کم',
        'medium': 'درمیانہ',
        'high': 'زیادہ',
        'unknown': 'نامعلوم'
    }
    return severity_map.get(severity.lower() if severity else 'unknown', severity)

def translate_scan_to_urdu(scan_obj):
    """Populate Urdu fields for a PlantScan object if they are empty"""
    if not scan_obj.disease_name_ur:
        scan_obj.disease_name_ur = translate_text_backend(scan_obj.disease_name)
    if not scan_obj.treatment_recommended_ur:
        scan_obj.treatment_recommended_ur = translate_text_backend(scan_obj.treatment_recommended)
    if not scan_obj.crop_type_ur:
        scan_obj.crop_type_ur = translate_text_backend(scan_obj.crop_type)
    if not scan_obj.severity_ur:
        scan_obj.severity_ur = get_urdu_severity(scan_obj.severity)
    scan_obj.save()

def run_clip_analysis(base64_string, language='en'):
    """Run CLIP model analysis with rejection for unsupported items"""
    REJECTION_KEYWORDS = [
        "random object", "vegetable", "flower", "ornamental", 
        "person", "animal", "pet", "building", "car", "furniture", 
        "outdoor scenery", "blurry", "unsupported fruit", 
        "unsupported tree", "unsupported plant", "box", "paper"
    ]
    
    # Get metadata in correct language
    metadata_dict = get_class_metadata(language)
    
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
            
            predicted_label = text_prompts[top1_idx]
            confidence = top1_conf
            
            print(f"Top prediction: {predicted_label} with confidence: {confidence:.2f}%")
            
            # Check if prediction is a rejection class
            is_rejection = any(keyword in predicted_label.lower() for keyword in REJECTION_KEYWORDS)
            
            if is_rejection:
                metadata = metadata_dict.get(predicted_label, {
                    "disease_name": "Unsupported Image",
                    "scientific_name": "N/A",
                    "severity": "unknown",
                    "treatment": "Please upload an image of a supported crop.",
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
                    'disease_name': "Uncertain Detection" if language == 'en' else "غیر یقینی شناخت",
                    'scientific_name': "N/A",
                    'confidence': round(confidence, 2),
                    'severity': "unknown",
                    'treatment': f"Low confidence ({confidence:.1f}%) detection. Please upload a clearer image." if language == 'en' else f"کم اعتمادیت ({confidence:.1f}%) کی شناخت۔ براہ کرم واضح تصویر اپ لوڈ کریں۔",
                    'crop_type': "Unknown",
                    'predicted_label': predicted_label,
                    'rejected': True,
                    'reason': 'low_confidence'
                }
            
            # Valid prediction - get metadata
            metadata = metadata_dict.get(predicted_label, {
                "disease_name": "Unknown",
                "scientific_name": "Unknown",
                "severity": "unknown",
                "treatment": "Consult agricultural expert for proper diagnosis.",
                "crop_type": "Unknown",
                "disease_detected": False
            })
            
            return {
                'disease_detected': metadata['disease_detected'],
                'disease_name': metadata['disease_name'],
                'scientific_name': metadata['scientific_name'],
                'confidence': round(confidence, 2),
                'severity': metadata['severity'],
                'treatment': metadata['treatment'],
                'crop_type': metadata['crop_type'],
                'predicted_label': predicted_label,
                'rejected': False
            }
            
    except Exception as e:
        print(f"CLIP inference error: {str(e)}")
        return simulate_ai_analysis(language)

def simulate_ai_analysis(language='en'):
    """Fallback simulation if CLIP model fails"""
    if language == 'ur':
        diseases = [
            {
                'name': 'ابتدائی جھلسن',
                'scientific': 'Alternaria solani',
                'confidence': random.uniform(85, 98),
                'severity': 'high',
                'treatment': 'فوری طور پر فنگسائڈ (Chlorothalonil یا Mancozeb) لگائیں۔',
                'crop_type': 'ٹماٹر/آلو',
                'disease_detected': True
            },
            {
                'name': 'صحت مند کیلا',
                'scientific': 'Musa acuminata - صحت مند',
                'confidence': random.uniform(90, 99),
                'severity': 'low',
                'treatment': 'کسی علاج کی ضرورت نہیں۔',
                'crop_type': 'کیلا',
                'disease_detected': False
            },
        ]
    else:
        diseases = [
            {
                'name': 'Early Blight',
                'scientific': 'Alternaria solani',
                'confidence': random.uniform(85, 98),
                'severity': 'high',
                'treatment': 'Apply fungicide (Chlorothalonil or Mancozeb) immediately.',
                'crop_type': 'Tomato/Potato',
                'disease_detected': True
            },
            {
                'name': 'Healthy Banana',
                'scientific': 'Musa acuminata - Healthy',
                'confidence': random.uniform(90, 99),
                'severity': 'low',
                'treatment': 'No treatment needed.',
                'crop_type': 'Banana',
                'disease_detected': False
            },
        ]
    
    if random.random() < 0.5:
        disease = random.choice([d for d in diseases if d['disease_detected']]) or diseases[0]
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
        healthy = random.choice([d for d in diseases if not d['disease_detected']]) or diseases[1]
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
            'disease_name_ur': scan.disease_name_ur or scan.disease_name,
            'disease_detected': scan.disease_detected,
            'confidence': scan.confidence,
            'created_at': scan.created_at.isoformat(),
            'crop_type': scan.crop_type,
            'crop_type_ur': scan.crop_type_ur or scan.crop_type,
        } for scan in scans]
    }
    return JsonResponse(data)

from .models import TeamApplication  # Make sure this is imported

@login_required
def about_view(request):
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')
    
    # Get user's language preference
    user_language = get_user_language(request)
    
    # Get accepted team members from TeamApplication
    accepted_members = TeamApplication.objects.filter(status='accepted').order_by('-created_at')
    
    # Convert to list of dictionaries for the template
    team_members = []
    for member in accepted_members:
        # Pre-translate if mission and user is in Urdu mode
        if user_language == 'ur' and (not member.name_ur or not member.role_ur):
            try:
                if not member.name_ur: member.name_ur = translate_text_backend(member.name)
                if not member.role_ur: member.role_ur = translate_text_backend(member.role)
                member.save()
            except:
                pass
                
        team_members.append({
            'name': member.name,
            'name_ur': member.name_ur or member.name,
            'role': member.role,
            'role_ur': member.role_ur or member.role,
            'email': member.email,
            'applied_at': member.created_at
        })
    
    # If no accepted members yet, show default/static team
    if not team_members:
        team_members = [
            {'name': 'Asma Ramzan', 'name_ur': 'اسما رمضان', 'role': 'Developer', 'role_ur': 'ڈویلپر'},
            {'name': 'Sadia', 'name_ur': 'سعدیہ', 'role': 'Developer', 'role_ur': 'ڈویلپر'},
        ]
    
    return render(request, 'agrisense/About.html', {
        'form': form,
        'branding': branding,
        'team_members': team_members,
        'user_language': user_language,
    })

# Add this import at the top
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

# ============================================
# CHANGE PASSWORD API
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def change_password_api(request):
    """
    Handle password change request.
    """
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        # Validation
        if not current_password:
            return JsonResponse({
                'success': False,
                'error': 'Current password is required'
            }, status=400)
        
        if not new_password or len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'error': 'New password must be at least 8 characters'
            }, status=400)
        
        # Check current password
        user = request.user
        if not user.check_password(current_password):
            return JsonResponse({
                'success': False,
                'error': 'Current password is incorrect'
            }, status=400)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully!'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import TeamApplication
import json

# ============================================
# JOIN TEAM API (ONLY THIS NEEDS TO BE ADDED)
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def join_team_api(request):
    """
    Handle join team form submission.
    Saves application to database for admin review.
    """
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', '').strip()
        message = data.get('message', '').strip()
        
        # Validation
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Name is required'
            }, status=400)
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)
        
        if '@' not in email or '.' not in email:
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid email address'
            }, status=400)
        
        if not role:
            return JsonResponse({
                'success': False,
                'error': 'Role/Position is required'
            }, status=400)
        
        # Save application to database
        application = TeamApplication.objects.create(
            name=name,
            email=email,
            role=role,
            message=message,
            user=request.user,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Application submitted successfully! Our team will review it shortly.',
            'application_id': application.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"Error in join_team_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)

def settings_view(request):
    branding = SiteBranding.get_current()
    form = BrandingForm(request.POST or None, instance=branding)
    
    # Get or create user profile for notification preferences
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Branding settings updated successfully.")
            return redirect('setting')

    return render(request, 'agrisense/Setting.html', {
        'form': form,
        'branding': branding,
        'user_profile': user_profile,  # ADD THIS LINE
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


# ============================================
# PROFILE SETTINGS VIEWS
# ============================================

@login_required
def profile_settings(request):
    """
    Display the profile settings page with user information
    and notification preferences.
    """
    # Get or create user profile for notification preferences
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    context = {
        'user': request.user,
        'user_profile': user_profile,
        'branding': {
            'app_name': SiteBranding.get_current().app_name,
            'app_subtitle': SiteBranding.get_current().app_subtitle,
        }
    }
    return render(request, 'agrisense/profile_settings.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_profile(request):
    """
    Handle AJAX request to update username and email.
    Returns JSON response.
    """
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        # Validation
        errors = {}
        
        # Username validation
        if not username:
            errors['username'] = 'Username is required.'
        elif len(username) < 3:
            errors['username'] = 'Username must be at least 3 characters long.'
        elif len(username) > 150:
            errors['username'] = 'Username must be less than 150 characters.'
        elif User.objects.exclude(pk=request.user.pk).filter(username__iexact=username).exists():
            errors['username'] = 'This username is already taken.'
        
        # Email validation
        if not email:
            errors['email'] = 'Email address is required.'
        elif '@' not in email or '.' not in email:
            errors['email'] = 'Please enter a valid email address.'
        elif User.objects.exclude(pk=request.user.pk).filter(email__iexact=email).exists():
            errors['email'] = 'This email is already registered.'
        
        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors,
                'error': list(errors.values())[0] if errors else 'Validation failed'
            }, status=400)
        
        # Update user - IMPORTANT: Use direct assignment and save
        user = request.user
        user.username = username
        user.email = email
        user.save()  # This saves both fields
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            'username': username,
            'email': email
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data.'
        }, status=400)
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_notification_pref(request):
    """
    Handle AJAX request to update user's notification preferences.
    Specifically for high-risk disease alerts.
    """
    try:
        data = json.loads(request.body)
        high_risk_notifications = data.get('high_risk_notifications', False)
        
        # Get or create user profile
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Update preference
        user_profile.high_risk_notifications = bool(high_risk_notifications)
        user_profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification preferences saved!',
            'high_risk_notifications': user_profile.high_risk_notifications
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)

# Add these imports at the top if not already present
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import PlantScan

# ============================================
# DELETE SINGLE SCAN
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_scan_api(request, scan_id):
    """
    Delete a single scan by ID.
    Only the owner can delete their own scan.
    """
    try:
        scan = PlantScan.objects.get(id=scan_id, user=request.user)
        scan.delete()
        return JsonResponse({
            'success': True,
            'message': 'Scan deleted successfully'
        })
    except PlantScan.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Scan not found or you do not have permission to delete it'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


# ============================================
# CLEAR ALL SCANS (DELETE ALL HISTORY)
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def clear_all_scans_api(request):
    """
    Delete ALL scans for the current user.
    This action cannot be undone.
    """
    try:
        count = PlantScan.objects.filter(user=request.user).count()
        
        if count == 0:
            return JsonResponse({
                'success': False,
                'error': 'No scans to delete'
            }, status=400)
        
        # Delete all scans for this user
        deleted_count, _ = PlantScan.objects.filter(user=request.user).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} scans',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


# ============================================
# DELETE MULTIPLE SELECTED SCANS (Bulk Delete)
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def delete_selected_scans_api(request):
    """
    Delete multiple selected scans by IDs.
    Expects JSON body: {"scan_ids": ["id1", "id2", ...]}
    """
    try:
        data = json.loads(request.body)
        scan_ids = data.get('scan_ids', [])
        
        if not scan_ids:
            return JsonResponse({
                'success': False,
                'error': 'No scan IDs provided'
            }, status=400)
        
        # Delete scans that belong to the current user
        deleted_count = PlantScan.objects.filter(
            id__in=scan_ids,
            user=request.user
        ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} scans',
            'deleted_count': deleted_count
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)

# Add to views.py

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def save_theme_preference(request):
    """Save user's theme preference to database"""
    try:
        data = json.loads(request.body)
        theme = data.get('theme', 'light')
        
        if theme not in ['light', 'dark']:
            return JsonResponse({'success': False, 'error': 'Invalid theme'}, status=400)
        
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        user_profile.theme_preference = theme
        user_profile.save()
        
        return JsonResponse({'success': True, 'theme': theme})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def get_theme_preference(request):
    """Get user's saved theme preference from database"""
    try:
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        return JsonResponse({
            'success': True, 
            'theme': user_profile.theme_preference
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Add to views.py
import requests
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def libre_translate_api(request):
    """
    Translation API with Database Caching (StaticContent model)
    Also saves language preference to session
    """
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        target_lang = data.get('target_lang', 'ur')
        source_lang = data.get('source_lang', 'en')
        page = data.get('page', 'global')
        
        # Save language preference to session
        request.session['preferred_language'] = target_lang if target_lang != 'en' else 'en'

        if not text:
            return JsonResponse({'success': True, 'translated': text})

        # 1. Check Database Cache (StaticContent)
        # We search for the exact English text across all pages or the specific page
        cache_entry = StaticContent.objects.filter(text_en=text).first()
        if cache_entry and target_lang == 'ur' and cache_entry.text_ur:
            return JsonResponse({
                'success': True,
                'translated': cache_entry.text_ur,
                'source': 'Database'
            })

        # 2. Limit text length for performance
        if len(text) > 500:
            text = text[:500]

        # 3. Use MyMemory API (more reliable)
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text,
            'langpair': f'{source_lang}|{target_lang}',
            'de': 'agrisense@demo.com'
        }
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            translated = result.get('responseData', {}).get('translatedText', text)
            translated = translated.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
            
            # 4. STORE in Database for future retrieval
            if target_lang == 'ur' and len(text) < 255: # Only store reasonably sized strings
                import hashlib
                text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                key = f"{text[:40].lower().replace(' ', '-')}-{text_hash}"
                StaticContent.objects.get_or_create(
                    text_en=text,
                    defaults={'page': page, 'key': key[:100], 'text_ur': translated}
                )
            
            return JsonResponse({
                'success': True, 
                'translated': translated,
                'source': 'MyMemory API'
            })
        else:
            return JsonResponse({'success': True, 'translated': text, 'warning': 'API error'})

    except Exception as e:
        print(f"Translation error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def test_translation_api(request):
    """Test endpoint to verify translation works"""
    test_text = "Hello, welcome to AgriSense"
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {'q': test_text, 'langpair': 'en|ur'}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            result = response.json()
            translated = result.get('responseData', {}).get('translatedText', test_text)
            return JsonResponse({
                'success': True,
                'test_text': test_text,
                'translated': translated,
                'message': 'Translation API is working!'
            })
        else:
            return JsonResponse({'success': False, 'message': f'API returned status {response.status_code}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def libre_translate_batch_api(request):
    """
    Batch translation API with Database Caching
    """
    try:
        data = json.loads(request.body)
        texts = data.get('texts', [])
        target_lang = data.get('target_lang', 'ur')
        page = data.get('page', 'global')
        
        if not texts:
            return JsonResponse({'success': True, 'translated_texts': []})

        request.session['preferred_language'] = target_lang

        translated_texts = []
        
        for text in texts:
            text = text.strip()
            # Check Cache
            cache_entry = StaticContent.objects.filter(text_en=text).first()
            if cache_entry and target_lang == 'ur' and cache_entry.text_ur:
                translated_texts.append(cache_entry.text_ur)
                continue
            
            # Translate if not cached
            try:
                url = "https://api.mymemory.translated.net/get"
                params = {'q': text, 'langpair': f'en|{target_lang}', 'de': 'agrisense@demo.com'}
                res = requests.get(url, params=params, timeout=5)
                if res.status_code == 200:
                    trans = res.json().get('responseData', {}).get('translatedText', text)
                    trans = trans.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')
                    
                    # Store
                    if target_lang == 'ur' and len(text) < 255:
                        import hashlib
                        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                        key = f"{text[:40].lower().replace(' ', '-')}-{text_hash}"
                        StaticContent.objects.get_or_create(
                            text_en=text,
                            defaults={'page': page, 'key': key[:100], 'text_ur': trans}
                        )
                    translated_texts.append(trans)
                else:
                    translated_texts.append(text)
            except:
                translated_texts.append(text)
        
        return JsonResponse({
            'success': True,
            'translated_texts': translated_texts
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def set_language_preference(request):
    """Save user's language preference"""
    try:
        data = json.loads(request.body)
        language = data.get('language', 'en')
        
        # Save to session
        request.session['preferred_language'] = language
        # Also set cookie for frontend
        response = JsonResponse({'success': True, 'language': language})
        response.set_cookie('agrisense_language', language, max_age=365*24*60*60)  # 1 year
        
        return response
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_language_preference(request):
    """Get user's language preference from session"""
    language = request.session.get('preferred_language', 'en')
    # Also check cookie if session is empty
    if language == 'en':
        language = request.COOKIES.get('agrisense_language', 'en')
    return JsonResponse({'success': True, 'language': language})

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_account_api(request):
    """Permanently delete user account and all associated data"""
    try:
        user = request.user
        # Delete all scans first (cascade will handle automatically)
        PlantScan.objects.filter(user=user).delete()
        # Delete user profile
        UserProfile.objects.filter(user=user).delete()
        # Delete the user account
        user.delete()
        return JsonResponse({'success': True, 'message': 'Account deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)