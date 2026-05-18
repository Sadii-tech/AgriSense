from django.contrib import admin

from agrisense.models import PlantScan, SiteBranding, UserProfile, TeamApplication, TutorialVideo, CropCategory, StaticContent


# Register your models here.
@admin.register(StaticContent)
class StaticContentAdmin(admin.ModelAdmin):
    list_display = ('page', 'key', 'text_en', 'text_ur_preview')
    list_filter = ('page',)
    search_fields = ('key', 'text_en', 'text_ur')
    
    def text_ur_preview(self, obj):
        return obj.text_ur[:50] + "..." if len(obj.text_ur) > 50 else obj.text_ur
    text_ur_preview.short_description = 'Urdu Text'

admin.site.register(PlantScan)
admin.site.register(SiteBranding)
admin.site.register(UserProfile)
admin.site.register(TeamApplication)
admin.site.register(TutorialVideo)
admin.site.register(CropCategory)