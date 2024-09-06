from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ['username', 'password']}),
        ('Personal info', {'fields': ['first_name', 'last_name', 'email']}),
        ('Permissions', {
            'fields': ['is_active', 'is_staff', 'is_artist', 'is_customer', 'is_admin', 'is_superuser', 'groups', 'user_permissions'],
        }),
        ('Important dates', {'fields': ['last_login']}),
    )
    
admin.site.register(User, CustomUserAdmin)
admin.site.register(UserVerificationRequest)
admin.site.register(AdminInvitation)
admin.site.register(AdminProfile)
admin.site.register(ArtistProfile)
admin.site.register(ArtistData)
admin.site.register(CustomerProfile)
admin.site.register(Genre)