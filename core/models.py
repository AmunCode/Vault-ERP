from django.db import models


class SiteSettings(models.Model):
    """Singleton model for runtime-configurable application settings."""

    enable_upc_api_lookup = models.BooleanField(
        default=False,
        help_text="Enable UPCitemdb fallback when HSN scrape finds nothing."
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Site Settings"
