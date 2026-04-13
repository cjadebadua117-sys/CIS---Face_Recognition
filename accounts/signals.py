from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, AuditLog


@receiver(post_save, sender=CustomUser)
def create_user_audit_log(sender, instance, created, **kwargs):
    """Log user creation"""
    if created:
        AuditLog.objects.create(
            user=instance,
            action='USER_CREATE',
            details={'created_by_system': True}
        )


@receiver(post_save, sender=CustomUser)
def update_user_audit_log(sender, instance, created, **kwargs):
    """Log user updates"""
    if not created:
        # Only log if important fields changed
        # This is a simplified version - in production you might want to track specific field changes
        AuditLog.objects.create(
            user=instance,
            action='USER_UPDATE',
            details={'updated_by_system': True}
        )
