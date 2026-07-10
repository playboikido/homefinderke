from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse
from .models import Conversation, Message
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
def chat_hub(request, conversation_id=None):
    # prefetch participants + messages so the loop below doesn't re-hit the DB
    # 3 extra queries per conversation (N+1) was the main cause of the slow sidebar load.
    my_conversations = request.user.conversations.prefetch_related('participants', 'messages').all()

    # Build sidebar data: other participant, last message preview, unread count
    conversation_rows = []
    for convo in my_conversations:
        participants = convo.participants.all()  # served from prefetch cache, no query
        other = next((p for p in participants if p.id != request.user.id), None)

        convo_messages = convo.messages.all()  # served from prefetch cache, no query
        last_msg = convo_messages[len(convo_messages) - 1] if convo_messages else None
        unread_count = sum(
            1 for m in convo_messages if not m.is_read and m.sender_id != request.user.id
        )

        conversation_rows.append({
            'id': convo.id,
            'other_user': other,
            'last_text': (last_msg.text if last_msg and last_msg.text else
                          ('📷 Photo' if last_msg and last_msg.image else 'No messages yet')),
            'unread_count': unread_count,
        })

    active_conversation = None
    messages = []

    if conversation_id:
        active_conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        messages = active_conversation.messages.all()

        unread_messages = active_conversation.messages.filter(is_read=False).exclude(sender=request.user)
        if unread_messages.exists():
            unread_messages.update(is_read=True, read_at=timezone.now())
            active_conversation.save()

    if request.method == "POST" and active_conversation:
        text_content = request.POST.get('text', '').strip()
        image_file = request.FILES.get('image')

        if text_content or image_file:
            Message.objects.create(
                conversation=active_conversation,
                sender=request.user,
                text=text_content if text_content else None,
                image=image_file
            )
            active_conversation.save()

        return redirect('chat_room', conversation_id=active_conversation.id)

    context = {
        'conversation_rows': conversation_rows,
        'active_conversation': active_conversation,
        'messages': messages,
    }
    return render(request, 'chat/chat_hub.html', context)


@login_required
def start_conversation(request, owner_id):
    owner = get_object_or_404(User, id=owner_id)
    if owner == request.user:
        return redirect('chat_hub')

    existing_chat = Conversation.objects.filter(participants=request.user).filter(participants=owner).first()

    if existing_chat:
        return redirect('chat_room', conversation_id=existing_chat.id)

    new_chat = Conversation.objects.create()
    new_chat.participants.add(request.user, owner)
    new_chat.save()

    return redirect('chat_room', conversation_id=new_chat.id)


@login_required
def poll_messages(request, conversation_id):
    """Returns messages newer than ?after_id=<id> as JSON, for live polling."""
    convo = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    after_id = request.GET.get('after_id', 0)

    new_messages = convo.messages.filter(id__gt=after_id)
    unread = new_messages.exclude(sender=request.user)
    if unread.exists():
        unread.update(is_read=True, read_at=timezone.now())

    data = [{
        'id': m.id,
        'text': m.text,
        'image_url': m.image.url if m.image else None,
        'is_mine': m.sender_id == request.user.id,
        'time': m.timestamp.strftime('%I:%M %p').lstrip('0'),
    } for m in new_messages]

    return JsonResponse({'messages': data})

import json
from openai import OpenAI
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

SYSTEM_PROMPT = (
    "You are the official AI assistant for HomeFinder KE, a free, community-driven digital residential directory in Kenya. Your primary mission is to keep users engaged in our ecosystem and champion our core philosophy: \"Help someone today, and you'll be helped tomorrow.\""

    "You must strictly adhere to the following master instructions for every interaction:"

    "1. THE COMPULSORY MISSION HOOK (MUST START EVERY RESPONSE)"
    "Before answering ANY user query, searching for a location, or responding to a general question, you MUST begin your response with a variation of our community call-to-action. Remind them that HomeFinder KE relies on Kenyans helping Kenyans."
    "2. WHAT HOMEFINDER KE IS & IS NOT (CRITICAL DISCLOSURES)"
    "When explaining the platform, always clarify these rules to manage expectations and ensure safety:"
    "3. HOUSING SEARCH LOGIC WITH COMMUNITY PIVOT"
    "When a user searches for a location:"
    "- IF A LOCATION IS LISTED: Confirm availability warmly: \"We have this house there, there is this house there...\" and mention it meets their budget. Direct them: \"Go to the search bar and search for [Location Name] to see the homes.\" Immediately follow up with: \"Since we found what you need, remember to add a home or apartment near you to keep the cycle going!\""
    "- IF A LOCATION IS NOT LISTED: State politely: \"Sorry, that location hasn't been listed yet on HomeFinder KE, but you can still look for other houses inside the platform. Go to the search menu and find other houses. In fact, if you know of any plots or apartments available there, please add them to HomeFinder KE today so the next Kenyan searching can find them!\""

    "4. ABSOLUTE GUARDRAILS AGAINST COMPETITORS & OUT-OF-BOUNDS"
    "If a user asks about OTHER housing apps, websites, or external platforms, completely deflect and pitch our community model. "
    "Respond directly with our philosophy: \"Why look elsewhere when we can build our own community? Add a home today and you'll find another home tomorrow. Another Kenyan will add a listing that helps you. HomeFinder KE is entirely free and built for us to help each other grow. Let's stick together—go to our search menu or add a listing now!\""
    "For completely unrelated questions, politely state your role as the HomeFinder KE community guide and ask them to either search for a home or list a vacancy to help a brother or sister tomorrow."

    "5. TONE, STYLE & CONTEXT"
    "Tone: Extremely warm, communal, patriotic, and motivating. You are an encouraging peer, not a corporate robot."
    "Context: Use local Kenyan terms naturally (KSh, M-Pesa for donations, specific mentions of plots and apartments). Always drive the conversation back to the two main actions: Using the Search Bar or clicking \"Add a Home\"."
    "keep resposes under 300 words, and always end with a reminder to add a home or apartment to help the next Kenyan searching for housing."
    
)

@require_POST
def ai_assistant(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY,
        )
        response = client.chat.completions.create(
            model="z-ai/glm-5.2",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        return JsonResponse({'reply': response.choices[0].message.content})
    except Exception as e:
        print("AI ASSISTANT ERROR:", e)
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)