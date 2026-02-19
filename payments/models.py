from django.db import models
from django.contrib.auth.models import User

class VendorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.user.username
    

class Product(models.Model):
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100, help_text="Name of the product")
    description = models.TextField(blank=True, null=True, help_text="Description of the product")
    price = models.IntegerField(default=0, help_text="Price of the product in cents")
    
    def __str__(self):
        return self.name
    
    def get_display_price(self):
        return "{0:.2f}".format(self.price / 100)