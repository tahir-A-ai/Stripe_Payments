from rest_framework import serializers
from django.contrib.auth import authenticate

class CheckoutSessionSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)