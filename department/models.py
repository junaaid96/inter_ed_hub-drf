from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    # Emoji or short glyph shown on category chips.
    icon = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
