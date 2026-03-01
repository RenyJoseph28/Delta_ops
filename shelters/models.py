from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
# KERALA DISTRICT DEFAULT COORDINATES
# ─────────────────────────────────────────────
KERALA_DISTRICT_COORDS = {
    "Alappuzha":         (9.4981,  76.3388),
    "Ernakulam":         (9.9816,  76.2999),
    "Idukki":            (9.9189,  77.1025),
    "Kannur":            (11.8745, 75.3704),
    "Kasaragod":         (12.4996, 74.9869),
    "Kollam":            (8.8932,  76.6141),
    "Kottayam":          (9.5916,  76.5222),
    "Kozhikode":         (11.2588, 75.7804),
    "Malappuram":        (11.0510, 76.0711),
    "Palakkad":          (10.7867, 76.6548),
    "Pathanamthitta":    (9.2648,  76.7870),
    "Thiruvananthapuram":(8.5241,  76.9366),
    "Thrissur":          (10.5276, 76.2144),
    "Wayanad":           (11.6854, 76.1320),
}

DISTRICT_CHOICES = [(d, d) for d in KERALA_DISTRICT_COORDS.keys()]


# ─────────────────────────────────────────────
# SHELTER MANAGER (new user role)
# ─────────────────────────────────────────────
class ShelterManager(models.Model):
    full_name       = models.CharField(max_length=200)
    username        = models.CharField(max_length=100, unique=True)
    password        = models.CharField(max_length=255)
    email           = models.EmailField(unique=True)
    phone           = models.CharField(max_length=20, null=True, blank=True)
    district        = models.CharField(max_length=50, choices=DISTRICT_CHOICES, null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    last_login      = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shelter_managers"

    def __str__(self):
        return f"{self.full_name} ({self.district})"


# ─────────────────────────────────────────────
# SHELTER
# ─────────────────────────────────────────────
class Shelter(models.Model):
    STATUS_CHOICES = [
        ("active",   "Active"),
        ("inactive", "Inactive"),
        ("full",     "Full"),
        ("closed",   "Closed"),
    ]

    name            = models.CharField(max_length=255)
    district        = models.CharField(max_length=50, choices=DISTRICT_CHOICES)
    address         = models.TextField()
    latitude        = models.FloatField()
    longitude       = models.FloatField()
    max_capacity    = models.IntegerField()
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    has_medical     = models.BooleanField(default=False)
    is_accessible   = models.BooleanField(default=True, help_text="Wheelchair / differently-abled accessible")
    contact_phone   = models.CharField(max_length=20, null=True, blank=True)
    manager         = models.ForeignKey(ShelterManager, null=True, blank=True, on_delete=models.SET_NULL, related_name="shelters")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shelters"

    def __str__(self):
        return f"{self.name} - {self.district}"

    @property
    def latest_status(self):
        return self.status_updates.order_by("-updated_at").first()

    @property
    def current_occupancy(self):
        s = self.latest_status
        return s.current_occupancy if s else 0

    @property
    def occupancy_pct(self):
        if self.max_capacity == 0:
            return 0
        return round((self.current_occupancy / self.max_capacity) * 100, 1)


# ─────────────────────────────────────────────
# SHELTER STATUS UPDATE (live updates by volunteers / managers)
# ─────────────────────────────────────────────
class ShelterStatusUpdate(models.Model):
    FOOD_CHOICES  = [("ok", "OK"), ("low", "Low"), ("critical", "Critical"), ("out", "Out")]
    WATER_CHOICES = [("ok", "OK"), ("low", "Low"), ("critical", "Critical"), ("out", "Out")]

    shelter             = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="status_updates")
    current_occupancy   = models.IntegerField()
    food_status         = models.CharField(max_length=20, choices=FOOD_CHOICES, default="ok")
    water_status        = models.CharField(max_length=20, choices=WATER_CHOICES, default="ok")
    medical_support     = models.BooleanField(default=False)
    notes               = models.TextField(null=True, blank=True)
    updated_by          = models.CharField(max_length=200, help_text="Volunteer name or manager username")
    updated_at          = models.DateTimeField(default=timezone.now)
    is_synced           = models.BooleanField(default=True, help_text="False if submitted offline and pending sync")

    class Meta:
        db_table = "shelter_status_updates"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.shelter.name} @ {self.updated_at:%Y-%m-%d %H:%M}"


# ─────────────────────────────────────────────
# VOLUNTEER
# ─────────────────────────────────────────────
class Volunteer(models.Model):
    TASK_CHOICES = [
        ("cooking",      "Cooking"),
        ("registration", "Registration"),
        ("cleaning",     "Cleaning"),
        ("medical",      "Medical Assistance"),
        ("logistics",    "Logistics"),
        ("security",     "Security"),
        ("general",      "General Help"),
    ]
    STATUS_CHOICES = [("active", "Active"), ("resting", "Resting"), ("off_duty", "Off Duty")]

    shelter     = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="volunteers")
    name        = models.CharField(max_length=200)
    phone       = models.CharField(max_length=20, null=True, blank=True)
    pin         = models.CharField(max_length=6, help_text="6-digit PIN for mobile login")
    task        = models.CharField(max_length=30, choices=TASK_CHOICES, default="general")
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    shift_start = models.TimeField(null=True, blank=True)
    shift_end   = models.TimeField(null=True, blank=True)
    joined_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "volunteers"

    def __str__(self):
        return f"{self.name} - {self.shelter.name} [{self.task}]"


# ─────────────────────────────────────────────
# SUPPLY LOG  (food & water tracking)
# ─────────────────────────────────────────────
class SupplyLog(models.Model):
    SUPPLY_TYPE = [("food", "Food"), ("water", "Water")]

    shelter             = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="supply_logs")
    supply_type         = models.CharField(max_length=10, choices=SUPPLY_TYPE)
    quantity_available  = models.FloatField(help_text="kg for food, litres for water")
    consumption_rate    = models.FloatField(help_text="per person per day estimate", default=0)
    logged_at           = models.DateTimeField(default=timezone.now)
    logged_by           = models.CharField(max_length=200)

    class Meta:
        db_table = "supply_logs"
        ordering = ["-logged_at"]

    def __str__(self):
        return f"{self.shelter.name} - {self.supply_type} @ {self.logged_at:%Y-%m-%d}"

    @property
    def days_remaining(self):
        """Estimated days supply will last based on current occupancy."""
        occupancy = self.shelter.current_occupancy or 1
        if self.consumption_rate == 0 or occupancy == 0:
            return None
        daily_usage = self.consumption_rate * occupancy
        if daily_usage == 0:
            return None
        return round(self.quantity_available / daily_usage, 1)


# ─────────────────────────────────────────────
# ML OVERFLOW PREDICTION LOG
# ─────────────────────────────────────────────
class OverflowPredictionLog(models.Model):
    RISK_LEVELS = [("low", "Low"), ("medium", "Medium"), ("high", "High")]

    shelter         = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="overflow_predictions")
    risk_level      = models.CharField(max_length=10, choices=RISK_LEVELS)
    probability     = models.FloatField(help_text="0.0 to 1.0")
    occupancy_at    = models.IntegerField()
    predicted_at    = models.DateTimeField(default=timezone.now)
    features_used   = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "overflow_prediction_logs"
        ordering = ["-predicted_at"]

    def __str__(self):
        return f"{self.shelter.name} - {self.risk_level} ({self.probability:.0%})"


# ─────────────────────────────────────────────
# SHELTER ALERT LOG
# ─────────────────────────────────────────────
class ShelterAlert(models.Model):
    ALERT_TYPES = [
        ("overflow_high",  "Overflow Risk HIGH"),
        ("food_low",       "Food Running Low"),
        ("water_low",      "Water Running Low"),
        ("understaffed",   "Shelter Understaffed"),
    ]

    shelter     = models.ForeignKey(Shelter, on_delete=models.CASCADE, related_name="alerts")
    alert_type  = models.CharField(max_length=30, choices=ALERT_TYPES)
    message     = models.TextField()
    is_resolved = models.BooleanField(default=False)
    email_sent  = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shelter_alerts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.alert_type}] {self.shelter.name}"
