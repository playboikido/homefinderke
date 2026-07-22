from django.db import models
from django.conf import settings
from django.utils import timezone

from core.models import compress_image, normalize_ke_whatsapp_number, COUNTY_CHOICES


CATEGORY_CHOICES = [
    ('movers', 'Movers'),
    ('furniture', 'Furniture'),
    ('curtains', 'Curtains & Blinds'),
    ('cleaning', 'Cleaning Services'),
    ('security', 'Security Services'),
    ('electronics', 'Electronics & Appliances'),
    ('internet', 'Internet Providers'),
    ('kitchen', 'Kitchen & Fittings'),
    ('bathroom', 'Bathroom & Plumbing'),
    ('lighting', 'Lighting'),
    ('repairs', 'Repairs & Maintenance'),
    ('garden', 'Garden & Landscaping'),
    ('interior_design', 'Interior Design'),
    ('other', 'Other'),
]

VERIFICATION_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
]


class Business(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='businesses')

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)

    logo = models.ImageField(upload_to='business/logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='business/covers/', blank=True, null=True)

    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_input = models.CharField(max_length=20, blank=True, help_text="Optional, if different from phone")
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

    county = models.CharField(max_length=50, choices=COUNTY_CHOICES, blank=True)
    town = models.CharField(max_length=100, blank=True)
    estate = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    closed_weekdays = models.CharField(max_length=20, blank=True, help_text="Comma-separated, 0=Mon..6=Sun")

    verification_status = models.CharField(max_length=10, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Homepage / homepage-promotion featured slot")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name)
            slug = base
            i = 1
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        if self.logo and hasattr(self.logo, 'file'):
            compressed = compress_image(self.logo)
            if compressed:
                self.logo = compressed
        if self.cover_image and hasattr(self.cover_image, 'file'):
            compressed = compress_image(self.cover_image, max_size=(1600, 900))
            if compressed:
                self.cover_image = compressed
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def whatsapp_number(self):
        raw = self.whatsapp_input or self.phone_number
        return normalize_ke_whatsapp_number(raw)

    @property
    def is_open_now(self):
        if not self.opens_at or not self.closes_at:
            return None
        now = timezone.localtime()
        if str(now.weekday()) in (self.closed_weekdays or '').split(','):
            return False
        current = now.time()
        if self.opens_at <= self.closes_at:
            return self.opens_at <= current <= self.closes_at
        return current >= self.opens_at or current <= self.closes_at

    @property
    def average_rating(self):
        from django.db.models import Avg
        agg = self.reviews.aggregate(avg=Avg('rating'))
        return round(agg['avg'], 1) if agg['avg'] else None

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def active_subscription(self):
        return getattr(self, 'subscription', None)

    @property
    def plan_slug(self):
        sub = self.active_subscription
        return sub.plan.slug if sub and sub.plan else 'starter'

    def product_limit_reached(self):
        sub = self.active_subscription
        if not sub or not sub.plan or sub.plan.max_products is None:
            return self.products.filter(is_active=True).count() >= 5
        return self.products.filter(is_active=True).count() >= sub.plan.max_products

    def gallery_limit_reached(self):
        sub = self.active_subscription
        if not sub or not sub.plan or sub.plan.max_gallery_images is None:
            return self.gallery_images.count() >= 10
        return self.gallery_images.count() >= sub.plan.max_gallery_images


class BusinessProduct(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='business/products/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image, 'file'):
            compressed = compress_image(self.image)
            if compressed:
                self.image = compressed
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.business.name})"

    class Meta:
        indexes = [models.Index(fields=['business', 'is_active'])]
        ordering = ['-created_at']


class BusinessGalleryImage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='business/gallery/', blank=True, null=True)
    video_url = models.URLField(blank=True, help_text="Premium plan: link to a video instead of an image")
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image, 'file'):
            compressed = compress_image(self.image)
            if compressed:
                self.image = compressed
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-uploaded_at']


class BusinessVerificationDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('certificate', 'Business Registration Certificate'),
        ('kra_pin', 'KRA PIN Certificate'),
        ('permit', 'Business Permit'),
        ('national_id', 'National ID'),
        ('logo', 'Business Logo'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='verification_documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='business/verification/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_doc_type_display()} - {self.business.name}"


class BusinessInquiry(models.Model):
    STATUS_CHOICES = [('new', 'New'), ('responded', 'Responded')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='inquiries')
    product = models.ForeignKey(BusinessProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_inquiries')

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    message = models.TextField()

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    reply_text = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['business', 'status'])]

    def __str__(self):
        return f"Inquiry from {self.customer_name} to {self.business.name}"


class BusinessReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)

    owner_reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('business', 'user')


class BusinessFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_favorites')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'business')


class SubscriptionPlan(models.Model):
    SLUG_CHOICES = [
        ('starter', 'Starter'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
    ]
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=20, choices=SLUG_CHOICES, unique=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_custom_pricing = models.BooleanField(default=False)

    max_products = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    max_gallery_images = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")

    allow_website_button = models.BooleanField(default=False)
    allow_whatsapp_button = models.BooleanField(default=False)
    allow_social_links = models.BooleanField(default=False)
    allow_video_gallery = models.BooleanField(default=False)
    featured_in_category = models.BooleanField(default=False)
    homepage_featured = models.BooleanField(default=False)
    priority_search_ranking = models.BooleanField(default=False)
    verified_badge = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    export_inquiries = models.BooleanField(default=False)
    multiple_staff = models.BooleanField(default=False)
    multiple_branches = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class BusinessSubscription(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')]
    BILLING_CHOICES = [('monthly', 'Monthly'), ('yearly', 'Yearly')]

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default='monthly')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business.name} - {self.plan.name}"

    @property
    def is_expired(self):
        return bool(self.end_date and self.end_date < timezone.now().date())


class BusinessPayment(models.Model):
    METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
        ('stripe', 'Stripe'),
    ]
    TYPE_CHOICES = [
        ('subscription_monthly', 'Monthly Subscription'),
        ('subscription_yearly', 'Yearly Subscription'),
        ('featured_listing', 'Featured Listing'),
        ('sponsored_category', 'Sponsored Category'),
        ('premium_verification', 'Premium Verification'),
        ('homepage_promotion', 'Homepage Promotion'),
    ]
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(BusinessSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    payment_method = models.CharField(max_length=15, choices=METHOD_CHOICES)
    payment_type = models.CharField(max_length=25, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_ref = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.business.name} - {self.get_payment_type_display()} - {self.amount}"


class BusinessAnalyticsEvent(models.Model):
    EVENT_CHOICES = [
        ('profile_view', 'Profile View'),
        ('phone_click', 'Phone Click'),
        ('whatsapp_click', 'WhatsApp Click'),
        ('website_click', 'Website Click'),
        ('product_view', 'Product View'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='analytics_events')
    product = models.ForeignKey(BusinessProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    visitor_county = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['business', 'event_type', 'created_at'])]
        ordering = ['-created_at']


class BusinessStaff(models.Model):
    ROLE_CHOICES = [('owner', 'Owner'), ('manager', 'Manager'), ('staff', 'Staff')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='staff_members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_staff_roles')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('business', 'user')