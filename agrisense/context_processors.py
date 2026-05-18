# context_processors.py
from .models import TutorialVideo

def tutorial_video(request):
    """Add tutorial video to all templates"""
    video = TutorialVideo.get_active_video()
    return {
        'tutorial_video': video
    }