from django.conf import settings
from rest_framework import serializers

ALLOWED_ROLES = ("user", "assistant")


class HistoryMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ALLOWED_ROLES)
    content = serializers.CharField(allow_blank=False, trim_whitespace=False)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("History message content cannot be blank.")
        return value


class ChatRequestSerializer(serializers.Serializer):
    """
    Validates the incoming payload from the frontend:

    {
      "prompt": "Talk like a pirate and use emojis.",
      "message": "What is AI?",
      "history": [{"role": "user", "content": "Hi"}, ...]
    }

    `prompt` is the student's personality prompt (optional, capped in
    length). `message` is the student's current message (required,
    non-blank, capped in length). `history` is optional prior turns;
    only the most recent MAX_HISTORY_MESSAGES are ever forwarded to
    Gemini, enforced again in the view/service layer regardless of
    what's validated here.
    """

    prompt = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        trim_whitespace=False,
    )
    message = serializers.CharField(allow_blank=False, trim_whitespace=False)
    history = HistoryMessageSerializer(many=True, required=False, default=list)

    def validate_prompt(self, value):
        if len(value) > settings.MAX_PROMPT_LENGTH:
            raise serializers.ValidationError(
                f"Prompt must be {settings.MAX_PROMPT_LENGTH} characters or fewer."
            )
        return value

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty or whitespace-only.")
        if len(value) > settings.MAX_MESSAGE_LENGTH:
            raise serializers.ValidationError(
                f"Message must be {settings.MAX_MESSAGE_LENGTH} characters or fewer."
            )
        return value
