from django.conf import settings
from django.db import models
from django.utils.text import slugify


CATEGORY_CHOICES = [
    ('movers', 'Movers'),
    ('furniture', 'Furniture Store'),
    ('curtains', 'Curtains & Blinds'),
    ('electronics', 'Electronics & Appliances'),
    ('kitchen', 'Kitchen & Home Fittings'),
    ('mattresses', 'Mattresses & Bedding'),
    ('bathroom', 'Bathroom & Sanitary'),
    ('cleaning', 'Cleaning Services'),
    ('lighting', 'Lighting'),
    ('repairs', 'Repairs & Maintenance'),
    ('garden', 'Garden & Landscaping'),
    ('internet', 'Internet Providers'),
    ('security', 'Security Companies'),
    ('househelp', 'Househelp & Domestic Staff'),
    ('carpets', 'Carpets & Rugs'),
    ('bedding', 'Duvets & Blankets'),
    ('other', 'Other'),
]

PLAN_CHOICES = [
    ('starter', 'Starter (Free)'),
    ('standard', 'Standard'),
    ('premium', 'Premium'),
    ('enterprise', 'Enterprise'),
]

PLAN_LIMITS = {
    'starter':    {'products': 5,   'gallery': 10,   'staff': 1},
    'standard':   {'products': 100, 'gallery': None, 'staff': 1},
    'premium':    {'products': None,'gallery': None, 'staff': 5},
    'enterprise': {'products': None,'gallery': None, 'staff': None},
}

# Boolean/behavioral features layered on top of the numeric limits above.
# This is the single source of truth — dashboard views, resident-facing
# querysets, and templates should all check business.has_feature('x')
# rather than comparing business.plan directly.
PLAN_FEATURES = {
    'starter':    {'analytics', 'reviews_view', 'gallery'},
    'standard':   {'analytics', 'reviews_view', 'reviews_reply', 'click_tracking', 'gallery', 'inquiries'},
    'premium':    {'analytics', 'reviews_view', 'reviews_reply', 'click_tracking', 'gallery', 'inquiries',
                   'priority_placement', 'sponsor_listing', 'homepage_promotion', 'advanced_analytics'},
    'enterprise': {'analytics', 'reviews_view', 'reviews_reply', 'click_tracking', 'gallery', 'inquiries',
                   'priority_placement', 'sponsor_listing', 'homepage_promotion', 'advanced_analytics',
                   'multi_location', 'account_manager'},
}
# Human-readable feature bullets shown on the plans page.
# HEADLINE_COUNT items show by default; the rest appear behind "See more".
PLAN_FEATURE_COPY = {
    'starter': [
        'Up to 5 product listings',
        'Up to 10 gallery photos',
        'Basic dashboard (views & inquiries)',
        '1 staff account',
        'Standard directory listing',
    ],
    'standard': [
        'Up to 100 product listings',
        'Unlimited gallery photos',
        'Full analytics dashboard',
        'Phone & WhatsApp click tracking',
        'Reply to customer reviews',
        '1 staff account',
        'Standard directory listing',
    ],
    'premium': [
        'Unlimited product listings',
        'Unlimited gallery photos',
        'Full analytics + advanced reports',
        'Phone & WhatsApp click tracking',
        'Reply to customer reviews',
        'Priority placement in search & category results',
        'Sponsor badge on directory pages',
        'Eligible for homepage promotion',
        'Up to 5 staff accounts',
    ],
    'enterprise': [
        'Everything in Premium',
        'Unlimited staff accounts',
        'Multiple business locations',
        'Dedicated account manager',
        'Custom contract & billing terms',
    ],
}
PLAN_HEADLINE_COUNT = 3  # bullets visible before "See more"

PLAN_PRICING = {
    'starter': {'monthly': 0, 'yearly': 0},
    'standard': {'monthly': 1500, 'yearly': 15000},
    'premium': {'monthly': 4000, 'yearly': 40000},
    'enterprise': {'monthly': None, 'yearly': None},  # custom / sales-assisted
}

VERIFICATION_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
]


def normalize_ke_whatsapp_number(phone_number):
    if not phone_number:
        return ''
    digits = ''.join(ch for ch in phone_number if ch.isdigit())
    if digits.startswith('0'):
        digits = '254' + digits[1:]
    elif digits.startswith('7') or digits.startswith('1'):
        digits = '254' + digits
    return digits


class Business(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='businesses'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='business/logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='business/covers/', blank=True, null=True)

    # Contact
    phone_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)

    # Location
    county = models.CharField(max_length=100, blank=True)
    town = models.CharField(max_length=100, blank=True)
    estate = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    service_counties = models.CharField(
        max_length=500, blank=True, help_text="Comma-separated counties served"
    )

    # Hours
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    closed_weekdays = models.CharField(
        max_length=20, blank=True, help_text="Comma-separated, 0=Mon..6=Sun"
    )

    # Plan & status
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')
    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUS_CHOICES, default='pending'
    )
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_paused_by_owner = models.BooleanField(default=False, help_text="Owner-controlled: temporarily hide this listing from the public directory without losing approval.")
    notify_new_review = models.BooleanField(default=True)
    notify_new_inquiry = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    onboarding_step = models.PositiveSmallIntegerField(default=1)
    onboarding_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Businesses'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or 'business'
            slug = base
            n = 1
            while Business.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug
        if self.phone_number and not self.whatsapp_number:
            self.whatsapp_number = normalize_ke_whatsapp_number(self.phone_number)
        # Premium/Enterprise auto-qualify for sponsor placement on public pages.
        # A staff member can still manually unfeature a business by editing
        # is_featured directly in the admin — this only auto-*enables* it.
        if self.plan in ('premium', 'enterprise'):
            self.is_featured = True
        elif self.pk:
            old_plan = Business.objects.filter(pk=self.pk).values_list('plan', flat=True).first()
            if old_plan in ('premium', 'enterprise'):
                self.is_featured = False
        super().save(*args, **kwargs)

    @property
    def plan_limits(self):
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS['starter'])

    def has_feature(self, feature):
        """Single check used everywhere: dashboard gating AND resident-facing pages."""
        return feature in PLAN_FEATURES.get(self.plan, PLAN_FEATURES['starter'])

    @property
    def is_open_now(self):
        if not self.opens_at or not self.closes_at:
            return None
        from django.utils import timezone
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
    def product_count(self):
        return self.products.filter(is_available=True).count()


class BusinessStaffMember(models.Model):
    ROLE_CHOICES = [('owner', 'Owner'), ('manager', 'Manager'), ('staff', 'Staff')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='staff_members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('business', 'user')


class BusinessProduct(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='business/products/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['business', 'is_available'])]

    def __str__(self):
        return f'{self.name} ({self.business.name})'


class BusinessGalleryImage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='business/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']


class BusinessVerificationDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('registration_certificate', 'Business Registration Certificate'),
        ('kra_pin', 'KRA PIN Certificate'),
        ('business_permit', 'Business Permit'),
        ('national_id', 'National ID'),
        ('logo', 'Business Logo'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='verification_documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='business/verification/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('business', 'doc_type')


class BusinessInquiry(models.Model):
    STATUS_CHOICES = [('new', 'New'), ('responded', 'Responded')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='inquiries')
    product = models.ForeignKey(
        BusinessProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    reply = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class BusinessReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    reply = models.TextField(blank=True)
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


class BusinessSubscription(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')]

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.business.name} - {self.plan}'


class BusinessPayment(models.Model):
    PURPOSE_CHOICES = [
        ('subscription_monthly', 'Monthly Subscription'),
        ('subscription_yearly', 'Yearly Subscription'),
        ('featured_listing', 'Featured Listing'),
        ('sponsored_category', 'Sponsored Category'),
        ('premium_verification', 'Premium Verification'),
        ('homepage_promotion', 'Homepage Promotion'),
    ]
    METHOD_CHOICES = [('mpesa', 'M-Pesa'), ('card', 'Card'), ('stripe', 'Stripe')]
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payments')
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='mpesa')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=100, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, blank=True, help_text="Plan to activate on successful payment")
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def activate(self):
        """
        Marks this payment completed and activates the associated plan on
        the business. Called by the M-Pesa callback on a real payment, and
        by the admin action below for manual approval (e.g. while waiting
        on live Safaricom credentials, or for bank/cash payments).
        """
        self.status = 'completed'
        self.save(update_fields=['status'])

        business = self.business
        if self.plan:
            business.plan = self.plan
            business.save(update_fields=['plan', 'is_featured'])
            BusinessSubscription.objects.update_or_create(
                business=business, defaults={'plan': self.plan, 'status': 'active'},
            )


class BusinessAnalyticsEvent(models.Model):
    EVENT_CHOICES = [
        ('profile_view', 'Profile View'),
        ('phone_click', 'Phone Click'),
        ('whatsapp_click', 'WhatsApp Click'),
        ('website_click', 'Website Click'),
        ('product_view', 'Product View'),
        ('saved', 'Saved by User'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='analytics_events')
    product = models.ForeignKey(
        BusinessProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='analytics_events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    location_hint = models.CharField(max_length=100, blank=True, help_text="County/town of the visitor, if known")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['business', 'event_type', 'created_at']),
        ]