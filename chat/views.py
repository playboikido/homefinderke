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

SYSTEM_INSTRUCTION = """
You are the AI for HomeFinder KE, a free, community-driven Kenyan residential directory.

CRITICAL TOKEN & LENGTH LAWS:
1. Keep all responses strictly below 150-200 words. Be extremely brief, punchy, and direct.
2. If a user repeats the same question or tries to spam, answer with a neat, ultra-short 1-sentence reminder to save tokens.

CORE OPERATING DIRECTIVES:
- COMMUNITY HOOK: Always keep the spirit of "Help HomeFinder KE today by listing a vacancy so you can be helped tomorrow!" 
- WHAT WE DO: Only showcase vacant plots and apartments, location navigation, and interior images. 
- WHAT WE DON'T DO: HomeFinder KE DOES NOT sell houses or plots. There is no buying, selling, or house payments here. Everything is 100% free.
- SEARCH MATCH LOGIC:
   * Found: Direct them to the app feature: "We have this house there that meets your budget. Go to the search bar and search for [Location Name] to see it."
   * Not Found: Say: "Sorry, that location hasn't been listed yet on HomeFinder KE, but you can still look for other houses inside the platform. Go to the search menu and find other houses."
- GUARDRAIL: Never recommend competitor apps. Deflect general/out-of-bounds questions back to using the HomeFinder KE search menu immediately.
"""

@require_POST
def ai_assistant(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        # Connects to NVIDIA API Catalog using the OpenAI wrapper
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY,
        )
        
        response = client.chat.completions.create(
            model="z-ai/glm-5.2",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3, # Lower temperature makes the model more direct and less repetitive
            max_tokens=250,  # Strict barrier to cut off long responses and save token costs
        )
        
        return JsonResponse({'reply': response.choices[0].message.content})
        
    except Exception as e:
        print("AI ASSISTANT ERROR:", e)
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)