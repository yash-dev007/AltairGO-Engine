from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate


class BaseSchema(Schema):
    """
    Base schema for all request payloads.

    unknown = EXCLUDE: unknown fields are silently dropped instead of passed
    through (INCLUDE) or rejected with a 400 (RAISE).  This prevents unknown
    fields from leaking into route handlers while remaining non-breaking for
    existing API clients that send extra fields.
    """
    class Meta:
        unknown = EXCLUDE


class DestinationChoiceSchema(BaseSchema):
    id = fields.Int(required=False, allow_none=True)
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    estimated_cost_per_day = fields.Float(required=False, allow_none=True)


class GenerateItinerarySchema(BaseSchema):
    destination_country = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    start_city = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    selected_destinations = fields.List(
        fields.Nested(DestinationChoiceSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    budget = fields.Float(required=True, validate=validate.Range(min=500))
    duration = fields.Int(required=True, validate=validate.Range(min=1, max=21))
    travelers = fields.Int(load_default=1, validate=validate.Range(min=1, max=20))
    style = fields.Str(load_default="standard")
    traveler_type = fields.Str(load_default="solo")
    date_type = fields.Str(load_default="fixed")
    start_date = fields.Str(required=False, allow_none=True)
    travel_month = fields.Str(required=False, allow_none=True)
    interests = fields.List(fields.Str(), load_default=list)
    children_count = fields.Int(load_default=0, validate=validate.Range(min=0, max=20))
    senior_count = fields.Int(load_default=0, validate=validate.Range(min=0, max=20))
    accessibility = fields.Int(load_default=0, validate=validate.Range(min=0, max=3))
    display_currency = fields.Str(load_default="INR", validate=validate.Length(max=3))
    use_engine = fields.Bool(load_default=True)
    # Dietary restrictions — e.g. ["vegetarian", "vegan", "halal", "jain", "gluten_free"]
    # Food-type attractions that explicitly list other-only options are filtered out.
    dietary_restrictions = fields.List(fields.Str(), load_default=list)
    # Minimum age of youngest child in group — used to filter out attractions with age limits.
    children_min_age = fields.Int(load_default=0, validate=validate.Range(min=0, max=17))
    # Special occasion: "honeymoon", "anniversary", "birthday", "family_reunion", etc.
    # Surfaces personalised insights and hotel special-request flags in booking plan.
    special_occasion = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    # Fitness level of the group: "low", "moderate", "high"
    # Used to surface warnings about strenuous activities even when senior_count is 0.
    fitness_level = fields.Str(
        load_default="moderate",
        validate=validate.OneOf(["low", "moderate", "high"]),
    )
    # from_city_iata: origin city IATA code for outbound flight booking (e.g. "BOM", "DEL")
    from_city_iata = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3))


class SaveTripSchema(BaseSchema):
    destination_country = fields.Str(required=False, allow_none=True, validate=validate.Length(min=2, max=100))
    budget = fields.Float(required=False, allow_none=True)
    duration = fields.Int(required=False, allow_none=True, validate=validate.Range(min=1, max=21))
    travelers = fields.Int(load_default=1, validate=validate.Range(min=1, max=20))
    style = fields.Str(load_default="standard")
    date_type = fields.Str(required=False, allow_none=True)
    start_date = fields.Str(required=False, allow_none=True)
    traveler_type = fields.Str(load_default="solo")
    total_cost = fields.Float(required=False, allow_none=True)
    trip_title = fields.Str(required=False, allow_none=True)
    itinerary_json = fields.Raw(required=True)


class RegisterSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    email = fields.Email(required=True, validate=validate.Length(max=100))
    password = fields.Str(required=True, validate=validate.Length(min=12, max=128))


class LoginSchema(BaseSchema):
    email = fields.Email(required=True, validate=validate.Length(max=100))
    password = fields.Str(required=True, validate=validate.Length(min=1, max=128))


class DestinationRequestSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    cost = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0))
    tag = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))


class CalculateBudgetSchema(BaseSchema):
    selected_destinations = fields.List(
        fields.Nested(DestinationChoiceSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    duration = fields.Int(required=True, validate=validate.Range(min=1, max=21))
    travelers = fields.Int(load_default=1, validate=validate.Range(min=1, max=20))
    style = fields.Str(load_default="standard")


class AttractionSignalSchema(BaseSchema):
    attraction_id = fields.Int(required=True)
    event_type = fields.Str(
        required=True,
        validate=validate.OneOf(["view", "save", "remove", "swap", "book_click"]),
    )
    traveler_type = fields.Str(required=False, allow_none=True)
    trip_style = fields.Str(required=False, allow_none=True)
    style = fields.Str(required=False, allow_none=True)
    budget_tier = fields.Str(required=False, allow_none=True)
    day_position = fields.Int(required=False, allow_none=True)
    trip_duration = fields.Int(required=False, allow_none=True)
    duration = fields.Int(required=False, allow_none=True)
    session_id = fields.Str(required=False, allow_none=True)


class VerifyAdminKeySchema(BaseSchema):
    key = fields.Str(required=True, validate=validate.Length(min=1))


class UpdateDestinationSchema(Schema):
    """Whitelist of allowed fields for updating a destination — prevents mass assignment."""
    class Meta:
        unknown = EXCLUDE  # silently drop any fields not defined here

    name = fields.Str(required=False, validate=validate.Length(min=2, max=200))
    desc = fields.Str(required=False, allow_none=True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=5000))
    image = fields.Str(required=False, allow_none=True)
    location = fields.Str(required=False, allow_none=True)
    rating = fields.Float(required=False, validate=validate.Range(min=0, max=5))
    tag = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    estimated_cost_per_day = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0))
    price_str = fields.Str(required=False, allow_none=True)
    highlights = fields.List(fields.Str(), required=False)
    best_time_months = fields.List(fields.Str(), required=False)
    vibe_tags = fields.List(fields.Str(), required=False)
    status = fields.Str(required=False, validate=validate.OneOf(["active", "inactive", "draft"]))


class TriggerJobSchema(Schema):
    """Schema for triggering background jobs from the dashboard."""
    class Meta:
        unknown = EXCLUDE

    job_name = fields.Str(
        required=True,
        validate=validate.OneOf([
            "ingest_osm", "enrich_destinations", "update_scores",
            "sync_prices", "cache_warm", "quality_score",
            "affiliate_health", "full_pipeline",
        ]),
    )
    params = fields.Dict(keys=fields.Str(), values=fields.Raw(), required=False, load_default=dict)

