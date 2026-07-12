from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count
from .models import Residence


def get_flagged_users():
    """
    Cheap database-only scan across recently active users. Returns only the
    users whose numbers cross a suspicious threshold — nothing here calls AI yet,
    that only happens for the (usually small) list this returns.
    """
    from chat.models import Message

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    candidates = {}

    # Users who posted multiple listings recently
    listing_counts = (
        Residence.objects.filter(created_at__gte=last_7d, owner__isnull=False)
        .values('owner')
        .annotate(count_24h=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(created_at__gte=last_24h)))
    )

    for row in Residence.objects.filter(created_at__gte=last_7d, owner__isnull=False).values_list('owner', flat=True).distinct():
        user_id = row
        listings_24h = Residence.objects.filter(owner_id=user_id, created_at__gte=last_24h).count()
        listings_7d = Residence.objects.filter(owner_id=user_id, created_at__gte=last_7d).count()
        distinct_phones = Residence.objects.filter(owner_id=user_id).values('phone_number').distinct().count()

        if listings_24h >= 3 or distinct_phones >= 3:
            candidates[user_id] = candidates.get(user_id, {})
            candidates[user_id]['listings_24h'] = listings_24h
            candidates[user_id]['listings_7d'] = listings_7d
            candidates[user_id]['distinct_phones'] = distinct_phones

    # Users messaging many different people in a short window
    recent_messages = Message.objects.filter(timestamp__gte=last_24h)
    sender_ids = recent_messages.values_list('sender_id', flat=True).distinct()

    for user_id in sender_ids:
        user_msgs = recent_messages.filter(sender_id=user_id)
        distinct_recipients = set()
        for msg in user_msgs.select_related('conversation'):
            others = msg.conversation.participants.exclude(id=user_id).values_list('id', flat=True)
            distinct_recipients.update(others)

        if len(distinct_recipients) >= 5:
            candidates.setdefault(user_id, {})
            candidates[user_id]['distinct_recipients_24h'] = len(distinct_recipients)
            candidates[user_id]['messages_24h'] = user_msgs.count()

    results = []
    for user_id, stats in candidates.items():
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            continue
        results.append({'user': user, 'stats': stats})

    return results


def ai_explain_pattern(user, stats):
    """Only called for users that already crossed a cheap threshold above — asks
    the AI to phrase a human-readable explanation, not to decide suspicion itself."""
    from .views import _get_nvidia_client
    import json

    summary_lines = []
    if 'listings_24h' in stats:
        summary_lines.append(f"Posted {stats['listings_24h']} listings in the last 24 hours ({stats['listings_7d']} in 7 days).")
    if 'distinct_phones' in stats:
        summary_lines.append(f"Used {stats['distinct_phones']} different phone numbers across their listings.")
    if 'distinct_recipients_24h' in stats:
        summary_lines.append(f"Sent {stats.get('messages_24h', '?')} messages to {stats['distinct_recipients_24h']} different people in 24 hours.")

    prompt = (
        "You are helping a Kenyan rental platform admin review account activity. "
        "Given these behavior stats for one user, write one short, plain-English sentence "
        "explaining why this might be worth a manual look (or say it's likely fine if the "
        "numbers look like normal heavy usage, not abuse). Be balanced, not alarmist.\n\n"
        + "\n".join(summary_lines)
    )

    try:
        client = _get_nvidia_client()
        response = client.chat.completions.create(
            model="z-ai/glm-5.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("USER BEHAVIOR AI ERROR:", e)
        return "AI explanation unavailable — raw stats above still apply."