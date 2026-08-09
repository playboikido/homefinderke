from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from io import BytesIO
import sys
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile

def validate_image(image):
    # Maximum size: 5 MB
    max_size = 5 * 1024 * 1024

    if image.size > max_size:
        raise ValidationError("Image file too large. Maximum size is 5MB.")

    # Allowed extensions
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']

    import os
    ext = os.path.splitext(image.name)[1].lower()

    if ext not in valid_extensions:
        raise ValidationError(
            "Unsupported file format. Use JPG, JPEG, PNG, or WEBP."
        )
    

def compress_image(image_field, max_size=(1280, 1280), quality=70):
    """Resize + compress an uploaded image in place. Returns a new InMemoryUploadedFile or None."""
    if not image_field:
        return None
    try:
        img = Image.open(image_field)
        img_format = 'JPEG' if img.format != 'PNG' else 'PNG'
        if img.mode in ('RGBA', 'P') and img_format == 'JPEG':
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.LANCZOS)

        buffer = BytesIO()
        save_kwargs = {'quality': quality, 'optimize': True} if img_format == 'JPEG' else {'optimize': True}
        img.save(buffer, format=img_format, **save_kwargs)
        buffer.seek(0)

        return InMemoryUploadedFile(
            buffer, 'ImageField',
            f"{image_field.name.split('.')[0]}.{'jpg' if img_format == 'JPEG' else 'png'}",
            f'image/{img_format.lower()}',
            sys.getsizeof(buffer), None
        )
    except Exception:
        return None
        
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


@receiver(post_save, sender=User)
def notify_admin_new_account(sender, instance, created, **kwargs):
    pass
    # Temporarily disabled — Gmail SMTP was causing worker timeouts/crashes.
    # Re-enable once email is properly configured.
    # if created:
    #     from django.core.mail import send_mail
    #     send_mail(
    #         subject='New HomeFinder KE account created',
    #         message=f'A new account was just created.\n\nUsername: {instance.username}\nEmail: {instance.email}\nJoined: {instance.date_joined}',
    #         from_email=None,
    #         recipient_list=['homefinder.ke.help@gmail.com'],
    #         fail_silently=True,
    #     )


HOUSE_TYPES = [
    ('single', 'Single'),
    ('bedsitter', 'Bedsitter'),
    ('double_room', 'Double Room'),
    ('studio', 'Studio'),
    ('1_bedroom', '1 Bedroom'),
    ('2_bedroom', '2 Bedroom'),
    ('3_bedroom', '3 Bedroom'),
    ('single_bedsitter', 'Single & Bedsitter'),
    ('bedsitter_double', 'Bedsitter & Double Room'),
    ('bedsitter_studio', 'Bedsitter & Studio'),
    ('bedsitter_1bed', 'Bedsitter & 1 Bedroom'),
    ('bedsitter_1bed_2bed', 'Bedsitter, 1 & 2 Bedroom'),
    ('1bed_2bed', '1 & 2 Bedroom'),
    ('2bed_3bed', '2 & 3 Bedroom'),
]

COUNTY_CHOICES = [
    ('Nairobi', 'Nairobi'),
    ('Kiambu', 'Kiambu'),
    ('Machakos', 'Machakos'),
    ('Kajiado', 'Kajiado'),
    ('Muranga', "Murang'a"),
    ('Nakuru', 'Nakuru'),
    ('Mombasa', 'Mombasa'),
    ('Kisumu', 'Kisumu'),
    ('Uasin Gishu', 'Uasin Gishu'),
]


REPORT_CHOICES = [
    ('occupied', 'House Already Occupied'),
    ('wrong_phone', 'Wrong Phone Number'),
    ('wrong_location', 'Wrong Location'),
    ('duplicate', 'Duplicate Residence'),
    ('fake', 'Fake Listing'),
    ('other', 'Other'),
]


RATING_CHOICES = [
    (1, '1 Star'),
    (2, '2 Stars'),
    (3, '3 Stars'),
    (4, '4 Stars'),
    (5, '5 Stars'),
]

def normalize_ke_whatsapp_number(value):
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    if digits.startswith('0') and len(digits) >= 10:
        return f"254{digits[1:]}"
    if digits.startswith('254'):
        return digits
    if len(digits) == 9:
        return f"254{digits}"
    return digits


class Residence(models.Model):

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    name = models.CharField(
        max_length=200,
        unique=True
    )

    description = models.TextField()

    house_type = models.CharField(
        max_length=50,
        choices=HOUSE_TYPES,
        default='bedsitter'
    )

    rent_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
    )

    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
    )

    county = models.CharField(
        max_length=100
    )
    town = models.CharField(
    max_length=100,
    help_text='Example: Kasarani, Ruiru, Kitengela'
    )
    plot_number = models.CharField(max_length=50, blank=True)

    landmark = models.CharField(
        max_length=200,
    )

    nearest_stage = models.CharField(
        max_length=200,
    )

    nearby_school = models.CharField(
        max_length=200,
    )

    nearby_hospital = models.CharField(
        max_length=200,
    )

    phone_number = models.CharField(max_length=20)

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
    )
    submission_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    submission_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    water_available = models.BooleanField(default=False)
    fibre_available = models.BooleanField(default=False)

    gated_community = models.BooleanField(default=False)
    cctv_available = models.BooleanField(default=False)
    security_guard = models.BooleanField(default=False)

    front_image = models.ImageField(
        upload_to='residences/fronts/',
        null=True
    )

    vacancy_poster = models.ImageField(
        upload_to='residences/posters/',
        null=True
    )

    approved = models.BooleanField(default=False)

    views_count = models.PositiveIntegerField(default=0)

    viewers = models.ManyToManyField(
        User,
        related_name='viewed_residences',
        blank=True
    )

    # AI Analysis Fields
    suspected_fraud = models.BooleanField(default=False)
    fraud_reason = models.TextField(blank=True, null=True)
    image_quality_status = models.CharField(
        max_length=20,
        default='unchecked',
        choices=[('unchecked', 'Unchecked'), ('passed', 'Passed'), ('failed', 'Failed')]
    )
    image_quality_feedback = models.TextField(blank=True, null=True)

    # Premium & Visibility Fields
    is_premium = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    is_paused = models.BooleanField(default=False)
    boost_requested = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def average_rating(self):
        reviews = self.reviews.all()

        if reviews.exists():
            total = sum(review.rating for review in reviews)
            return round(total / reviews.count(), 1)

        return 0

    @property
    def whatsapp_number(self):
        return normalize_ke_whatsapp_number(self.phone_number)
    
    def save(self, *args, **kwargs):
        if self.front_image and hasattr(self.front_image, 'file'):
            compressed = compress_image(self.front_image)
            if compressed:
                self.front_image = compressed
        if self.vacancy_poster and hasattr(self.vacancy_poster, 'file'):
            compressed = compress_image(self.vacancy_poster)
            if compressed:
                self.vacancy_poster = compressed
        super().save(*args, **kwargs)    

class ResidenceView(models.Model):
    residence = models.ForeignKey(Residence, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_viewed = models.DateField(auto_now=True)

    class Meta:
        unique_together = ('residence', 'user')

class ResidencePhoto(models.Model):

    residence = models.ForeignKey(
        'residence',
        on_delete=models.CASCADE,
        related_name='photos'
    )
    image = models.ImageField(
        upload_to='residence_photos/',
        validators=[validate_image]
    )

    caption = models.CharField(
        max_length=255,
        blank=True
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):
        if self.image and hasattr(self.image, 'file'):
            compressed = compress_image(self.image)
            if compressed:
                self.image = compressed
        super().save(*args, **kwargs)    



    def __str__(self):
        return f"{self.residence.name} Photo"
    

class Review(models.Model):

    residence = models.ForeignKey(
        Residence,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    rating = models.IntegerField(
        choices=RATING_CHOICES
    )

    comment = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.residence.name}'

class MoverReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    mover = models.ForeignKey('Mover', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('mover', 'user')


class FurnitureVendorReview(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    vendor = models.ForeignKey('FurnitureVendor', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('vendor', 'user')

class Profile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    profile_picture = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    bio = models.TextField(blank=True)
    is_suspended = models.BooleanField(default=False)
    ACCOUNT_TYPE_CHOICES = [('resident', 'Resident'), ('business', 'Business')]
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, default='resident')

    cover_photo = models.ImageField(
        upload_to='profiles/covers/',
        blank=True,
        null=True
    )
    county = models.CharField(max_length=100, choices=COUNTY_CHOICES, blank=True)
    town = models.CharField(max_length=100, blank=True)
    LANGUAGE_CHOICES = [('en', 'English'), ('sw', 'Kiswahili')]
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')

    THEME_CHOICES = [('system', 'System'), ('light', 'Light'), ('dark', 'Dark')]
    theme_preference = models.CharField(max_length=6, choices=THEME_CHOICES, default='system')
    reduce_motion = models.BooleanField(default=False)
    compact_mode = models.BooleanField(default=False)

    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]
    profile_visibility = models.CharField(max_length=7, choices=VISIBILITY_CHOICES, default='public')
    hide_phone = models.BooleanField(default=True)
    hide_email = models.BooleanField(default=True)

    phone_verified = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    RESIDENT_ROLE_CHOICES = [
        ('normal', 'Normal / Renter'),
        ('landlord', 'Landlord'),
        ('agent', 'Agent'),
        ('caretaker', 'Caretaker'),
    ]
    resident_role = models.CharField(
        max_length=10, choices=RESIDENT_ROLE_CHOICES, blank=True,
        help_text='Only meaningful when account_type is resident.',
    )
    onboarding_step = models.PositiveSmallIntegerField(default=1)
    onboarding_complete = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.profile_picture and hasattr(self.profile_picture, 'file'):
            compressed = compress_image(self.profile_picture)
            if compressed:
                self.profile_picture = compressed
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.username


class ResidenceReport(models.Model):

    residence = models.ForeignKey(
        Residence,
        on_delete=models.CASCADE,
        related_name='reports'
    )

    reported_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    reason = models.CharField(
        max_length=50,
        choices=REPORT_CHOICES
    )

    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    reviewed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.residence.name} - {self.reason}"

USER_REPORT_CHOICES = [
    ('harassment', 'Harassment or abusive messages'),
    ('scam', 'Suspected scam or fraud'),
    ('fake_profile', 'Fake profile / impersonation'),
    ('inappropriate', 'Inappropriate content or behavior'),
    ('other', 'Other'),
]

class UserReport(models.Model):
    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reports_received'
    )
    reported_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reports_filed'
    )
    reason = models.CharField(max_length=50, choices=USER_REPORT_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reported_user.username} - {self.reason}"

class Favorite(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites'
    )

    residence = models.ForeignKey(
        Residence,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ('user', 'residence')

    def __str__(self):
        return f"{self.user.username} - {self.residence.name}"
 
class SavedSearch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')

    keyword = models.CharField(max_length=200, blank=True)
    county = models.CharField(max_length=100, blank=True)
    town = models.CharField(max_length=100, blank=True)
    house_type = models.CharField(max_length=50, blank=True)
    min_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def matches(self, residence):
        if self.keyword and self.keyword.lower() not in (residence.name + residence.description).lower():
            return False
        if self.county and self.county.lower() != (residence.county or '').lower():
            return False
        if self.town and self.town.lower() != (residence.town or '').lower():
            return False
        if self.house_type and self.house_type != residence.house_type:
            return False
        if self.min_rent and residence.rent_price and residence.rent_price < self.min_rent:
            return False
        if self.max_rent and residence.rent_price and residence.rent_price > self.max_rent:
            return False
        return True

    def __str__(self):
        return f"{self.user.username}'s search: {self.keyword or 'any'} in {self.town or self.county or 'anywhere'}"

class LeaseAgreement(models.Model):
    residence = models.ForeignKey(Residence, on_delete=models.CASCADE, related_name='leases')
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leases_as_tenant')

    tenant_full_name = models.CharField(max_length=200)
    tenant_id_number = models.CharField(max_length=50)
    tenant_phone = models.CharField(max_length=20)

    landlord_full_name = models.CharField(max_length=200)
    landlord_phone = models.CharField(max_length=20)

    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    lease_start_date = models.DateField()
    lease_duration_months = models.PositiveIntegerField(default=12)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lease: {self.residence.name} - {self.tenant_full_name}"

CURRENT_TERMS_VERSION = 'v1.0'  # bump this any time you change the terms text below

LISTING_TERMS_TEXT = """

By submitting this listing to HomeFinder KE, I confirm that:
1. I am the owner, caretaker, or authorized agent for this property, and have the right to list it.
2. All information provided (rent, location, amenities, availability, and photos) is accurate
   to the best of my knowledge as of the submission date.
3. HomeFinder KE is a listings platform only and is not a party to any tenancy agreement,
   rent collection, or dispute between myself and any tenant.
4. I am solely responsible for the accuracy of this listing and for complying with all
   applicable Kenyan laws regarding rental property advertising and tenancy.
5. HomeFinder KE may remove this listing at its discretion if it is found to be inaccurate,
   fraudulent, or in violation of platform guidelines.
"""

class ListingAgreement(models.Model):
    residence = models.OneToOneField(Residence, on_delete=models.CASCADE, related_name='agreement')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listing_agreements')
    terms_version = models.CharField(max_length=20)
    terms_snapshot = models.TextField(help_text="Full terms text as it existed at the moment of consent")
    agreed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    def __str__(self):
        return f"Agreement — {self.residence.name} — {self.agreed_at.strftime('%d %b %Y')}"

RESIDENT_TERMS_VERSION = 'v1.0'

NORMAL_RESIDENT_TERMS_TEXT = """
By continuing as a Normal resident on HomeFinder KE, I confirm that any property I list is one
I have been given permission to list — by the owner, landlord, or caretaker in charge of it —
and I am borrowing that permission, not claiming ownership. I am solely responsible for making
sure I actually have that permission before posting. HomeFinder KE has no way to verify it on
my behalf and takes no responsibility for, and no blame in, any dispute arising from a listing
I post without proper authorization.
"""

LANDLORD_TERMS_TEXT = """
By continuing as a Landlord on HomeFinder KE, I confirm that I own, or have a legal right to
let out, any property I list, and that the documents I submit for verification are genuine.
I accept that HomeFinder KE may list my properties publicly, and that HomeFinder KE is a
listings platform only — not a party to any tenancy agreement, rent collection, or dispute
between myself and any tenant.
"""

AGENT_TERMS_TEXT = """
By continuing as an Agent on HomeFinder KE, I confirm that I am authorized to represent and
market the properties I list on behalf of their owners or landlords, and that the documents I
submit for verification are genuine and accurately reflect my mandate. HomeFinder KE is a
listings platform only — not a party to any tenancy agreement, rent collection, or dispute
between myself, the property owner, and any tenant.
"""

CARETAKER_TERMS_TEXT = """
By continuing as a Caretaker on HomeFinder KE, I confirm that I have been authorized by the
landlord or property owner to manage and list the properties I post on their behalf, and that
the ID I submit for verification is genuine. HomeFinder KE is a listings platform only — not a
party to any tenancy agreement, rent collection, or dispute connected to a property I manage.
"""

RESIDENT_ROLE_TERMS_TEXT = {
    'normal': NORMAL_RESIDENT_TERMS_TEXT,
    'landlord': LANDLORD_TERMS_TEXT,
    'agent': AGENT_TERMS_TEXT,
    'caretaker': CARETAKER_TERMS_TEXT,
}

class ResidentAgreement(models.Model):
    """
    Signed once during resident onboarding, for the 'normal' (non-landlord,
    non-agent) role: acknowledges up front — before any listing exists — that
    they bear responsibility for having permission to list a property. Deliberately
    a log (FK, not OneToOne) rather than a single row: if CURRENT_TERMS_VERSION is
    ever bumped, the user re-consents and a new row is added rather than the old
    consent being overwritten or lost.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resident_agreements')
    role = models.CharField(max_length=10, choices=Profile.RESIDENT_ROLE_CHOICES, blank=True)
    terms_version = models.CharField(max_length=20)
    terms_snapshot = models.TextField(help_text="Full terms text as it existed at the moment of consent")
    agreed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-agreed_at']

    def __str__(self):
        return f"Resident agreement — {self.user.username} — {self.agreed_at.strftime('%d %b %Y')}"


class Notification(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.user.username} - Notification"


class NotificationPreference(models.Model):
    """Settings > Notifications toggles (Residence Workspace)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preference'
    )

    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    favourite_residence_updates = models.BooleanField(default=True)
    new_inquiry_alerts = models.BooleanField(default=True)
    new_review_alerts = models.BooleanField(default=True)
    newsletter = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)
    notification_sounds = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - Notification Preferences"


class IDVerification(models.Model):
    """Settings > Verification (Residence Workspace).
    Covers the National ID document upload + staff review status.
    Phone verification has no OTP system behind it yet (see Profile.phone_verified);
    email verification reads from allauth's existing EmailAddress model instead
    of duplicating state here.
    """
    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='id_verification'
    )
    document = models.FileField(upload_to='verification/id_documents/', blank=True, null=True)
    kra_pin_document = models.FileField(
        upload_to='verification/kra_pin/', blank=True, null=True,
        help_text='Required for landlords and agents.',
    )
    property_proof_document = models.FileField(
        upload_to='verification/property_proof/', blank=True, null=True,
        help_text='Agents only: proof of the rental properties/homes you manage or represent.',
    )
    status = models.CharField(max_length=13, choices=STATUS_CHOICES, default='not_submitted')
    rejection_reason = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - ID Verification ({self.status})"

@receiver(post_save, sender=Residence)
def create_approval_notification(sender, instance, created, **kwargs):

    if instance.approved:

        already_sent = Notification.objects.filter(
            user=instance.owner,
            message__contains=instance.name
        ).exists()

        if not already_sent:

            Notification.objects.create(
                user=instance.owner,
                message=f'🎉 Your residence "{instance.name}" has been approved and is now live.'
            )    

def validate_image(image):
    file_size = image.file.size

    if file_size > 5 * 1024 * 1024:
        raise ValidationError("Maximum image size is 5MB.")

    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']

    import os
    ext = os.path.splitext(image.name)[1]

    if ext.lower() not in valid_extensions:
        raise ValidationError(
            "Only JPG, JPEG, PNG and WEBP files are allowed."
        )
    
ROOMMATE_MOVE_IN_CHOICES = [
    ('immediately', 'Immediately'),
    ('1_month', 'Within 1 month'),
    ('flexible', 'Flexible'),
]

class RoommateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='roommate_profile')

    budget_min = models.DecimalField(max_digits=10, decimal_places=2)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2)

    preferred_county = models.CharField(max_length=100)
    preferred_town = models.CharField(max_length=100, blank=True, help_text='Example: Kasarani, Ruiru')

    move_in_timeline = models.CharField(max_length=20, choices=ROOMMATE_MOVE_IN_CHOICES, default='flexible')
    bio = models.TextField(help_text='Tell others about yourself, habits, work schedule, etc.')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Roommate profile: {self.user.username}"   


class Donation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"KSh {self.amount} - {self.phone_number} ({self.status})"     
DATA_SOURCE_CHOICES = [
    ('scraped', 'Scraped'),
    ('manual', 'Manual'),
    ('mixed', 'Mixed'),
]
SCRAPE_STATUS_CHOICES = [
    ('ok', 'OK'),
    ('failed', 'Failed'),
    ('never_run', 'Never Run'),
]

class Mover(models.Model):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='movers/', blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    description = models.TextField()
    website = models.URLField(blank=True, null=True)
    is_major_sponsor = models.BooleanField(default=False, help_text="Shows on every listing page, regardless of location")
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    service_counties = models.CharField(max_length=500, blank=True, help_text="Comma-separated counties served, e.g. Nairobi, Kiambu")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    closed_weekdays = models.CharField(max_length=20, blank=True, help_text="Comma-separated, 0=Mon..6=Sun, e.g. '6' for closed Sundays")

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

    # --- NEW: live product data ---
    data_source = models.CharField(max_length=10, choices=DATA_SOURCE_CHOICES, default='manual')
    scrape_config = models.JSONField(blank=True, null=True, help_text=(
        "e.g. {'product_page_url': 'https://vendor.com/shop', "
        "'item_selector': '.product-card', 'name_selector': '.product-title', "
        "'price_selector': '.price', 'image_selector': 'img'}"
    ))
    last_scraped_at = models.DateTimeField(blank=True, null=True)
    scrape_status = models.CharField(max_length=10, choices=SCRAPE_STATUS_CHOICES, default='never_run')
    contract_expires_at = models.DateField(blank=True, null=True, help_text="Sponsorship/listing contract end date")

    def __str__(self):
        return self.name

    @property
    def whatsapp_number(self):
        return normalize_ke_whatsapp_number(self.phone_number)

    @property
    def is_expired(self):
        from django.utils import timezone
        return bool(self.contract_expires_at and self.contract_expires_at < timezone.now().date())



class MoverProduct(models.Model):
    SOURCE_CHOICES = [('scraped', 'Scraped'), ('manual', 'Manual')]

    mover = models.ForeignKey(Mover, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    image_url = models.URLField(blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['mover', 'is_active'])]

class FurnitureVendor(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='furniture/', blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    location = models.CharField(max_length=200)
    CATEGORY_CHOICES = [
    ('furniture', 'Furniture'),
    ('curtains', 'Curtains'),
    ('electronics', 'Electronics'),
    ('kitchen', 'Kitchen'),
    ('mattresses', 'Mattresses'),
    ('bathroom', 'Bathroom'),
    ('cleaning', 'Cleaning'),
    ('lighting', 'Lighting'),
    ('repairs', 'Repairs'),
    ('garden', 'Garden'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='furniture')
    description = models.TextField()
    website = models.URLField(blank=True, null=True)
    is_major_sponsor = models.BooleanField(default=False, help_text="Shows on every listing page, regardless of location")
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    service_counties = models.CharField(max_length=500, blank=True, help_text="Comma-separated counties served, e.g. Nairobi, Kiambu")
    contract_end_date = models.DateField(blank=True, null=True, help_text="When this mover's paid listing/contract expires")

    # --- NEW: live product data ---
    data_source = models.CharField(max_length=10, choices=DATA_SOURCE_CHOICES, default='manual')
    scrape_config = models.JSONField(blank=True, null=True, help_text=(
        "e.g. {'product_page_url': 'https://vendor.com/shop', "
        "'item_selector': '.product-card', 'name_selector': '.product-title', "
        "'price_selector': '.price', 'image_selector': 'img'}"
    ))
    last_scraped_at = models.DateTimeField(blank=True, null=True)
    scrape_status = models.CharField(max_length=10, choices=SCRAPE_STATUS_CHOICES, default='never_run')

    def __str__(self):
        return self.name

    @property
    def whatsapp_number(self):
        return normalize_ke_whatsapp_number(self.phone_number)


class FurnitureProduct(models.Model):
    SOURCE_CHOICES = [('scraped', 'Scraped'), ('manual', 'Manual')]

    vendor = models.ForeignKey(FurnitureVendor, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    image_url = models.URLField(blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['vendor', 'is_active'])]


class MoverGalleryImage(models.Model):
    """Portfolio photos ('what they do, how they do it') — separate from the
    scraped MoverProduct ticker. Shown on the mover's own detail/view page
    for both sponsor and directory tiers."""
    mover = models.ForeignKey(Mover, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='movers/gallery/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class FurnitureGalleryImage(models.Model):
    """Portfolio photos for furniture vendors — same purpose as MoverGalleryImage."""
    vendor = models.ForeignKey(FurnitureVendor, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='furniture/gallery/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class MoverFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mover_favorites')
    mover = models.ForeignKey(Mover, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'mover')


class FurnitureVendorFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='furniture_favorites')
    vendor = models.ForeignKey(FurnitureVendor, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'vendor')    

INCIDENT_CATEGORY_CHOICES = [
    ('emergency', 'Emergency / Safety Concern'),
    ('scam', 'Suspected Scam or Fraud'),
    ('harassment', 'Harassment or Abusive Behavior'),
    ('payment', 'Payment / M-Pesa Issue'),
    ('login', 'Login / Sign-in Problem'),
    ('account_access', 'Account Locked or Suspended'),
    ('verification', 'ID or Business Verification Issue'),
    ('listing_delay', 'Listing Not Approved / Not Going Live'),
    ('listing_edit', "Listing Info Wrong or Won't Update"),
    ('notifications', 'Notifications Not Working'),
    ('messaging', 'Chat / Messaging Problem'),
    ('bug', 'Bug or Technical Issue'),
    ('other', 'Other'),
]

INCIDENT_STATUS_CHOICES = [
    ('open', 'Open'),
    ('in_review', 'In Review'),
    ('resolved', 'Resolved'),
]


class Incident(models.Model):
    """General help-center incident report — not tied to a specific
    residence or user, unlike ResidenceReport/UserReport. Covers
    emergencies, scams, payment issues, bugs, and general safety concerns."""

    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents_filed'
    )
    category = models.CharField(max_length=20, choices=INCIDENT_CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    contact_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=INCIDENT_STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.subject}"

RESIDENCE_SPONSORSHIP_PRICE = 300  # KSh, flat fee to feature one listing for 30 days

class ResidenceSponsorship(models.Model):
    """Payment record for boosting a single residence listing to Premium.
    Mirrors business.models.BusinessPayment's STK-push pattern so both
    flows can go live together once Daraja credentials are registered."""

    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')]

    residence = models.ForeignKey(Residence, on_delete=models.CASCADE, related_name='sponsorships')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='residence_sponsorships')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=RESIDENCE_SPONSORSHIP_PRICE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    checkout_request_id = models.CharField(max_length=100, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def activate(self):
        """Marks payment completed and grants Premium on the residence.
        Called by the M-Pesa callback on a real payment, or manually via
        Django admin while live Daraja credentials are pending."""
        self.status = 'completed'
        self.save(update_fields=['status'])
        self.residence.is_premium = True
        self.residence.boost_requested = False
        self.residence.save(update_fields=['is_premium', 'boost_requested'])    