import firebase_admin
from firebase_admin import credentials, db
import json

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # For safety settings
from google.api_core.exceptions import GoogleAPIError

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Try to load the resource, if not found, download it
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

from dotenv import load_dotenv
import os

load_dotenv()

firebase_credentials_path = os.getenv('FIREBASE_CREDENTIALS')
firebase_db_url = os.getenv('FIREBASE_DATABASE_URL')

cred = credentials.Certificate(firebase_credentials_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': firebase_db_url
})


from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from openai import OpenAIError


app = Flask(__name__)
CORS(app)

# openai.api_key = os.getenv('OPENAI_API_KEY')

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

GEMINI_MODEL = 'gemini-1.5-flash'

@app.route('/api/message', methods=['POST'])
def handle_message():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_message = data.get('text')
    user_id = data.get('userId')

    if not user_message:
        return jsonify({"error": "Missing 'text' in request body"}), 400
    if not user_id:
        user_id = "anonymous_user"

    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(user_message)
    sentiment_compound = sentiment['compound']

    ref = db.reference(f'conversations/{user_id}')
    conversation_history = ref.get() or [] # Renamed to avoid conflict with `conversation` below

    # Gemini's chat history format is a list of dicts with 'role' and 'parts' (list of dicts with 'text')
    # Convert existing conversation to Gemini format for context
    gemini_conversation = []
    for msg in conversation_history:
        # Ensure old messages from Firebase are converted to the correct Gemini format
        # Assumes Firebase stores {'role': 'user/assistant', 'content': 'text'}
        gemini_conversation.append({'role': msg['role'], 'parts': [{'text': msg['content']}]})

    # Add the current user message to the Gemini conversation history format
    gemini_conversation.append({'role': 'user', 'parts': [{'text': user_message}]})

    # Adjust system message based on sentiment
    if sentiment_compound < -0.5:
        system_instruction = "You are a helpful assistant that provides comforting responses."
    elif sentiment_compound > 0.5:
        system_instruction = "You are an enthusiastic assistant that engages positively."
    else:
        system_instruction = "You are a neutral assistant."

    try:
        # Initialize the model with system instructions and safety settings
        # Note: system_instruction is passed directly to GenerativeModel
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_instruction,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        # Start a chat session and provide the history
        chat_session = model.start_chat(history=gemini_conversation[:-1]) # history is all but the last (current user) message

        # Send the current user message
        response = chat_session.send_message(user_message)
        bot_reply = response.text.strip()

    except GoogleAPIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify({"error": f"Failed to get response from AI: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred while processing your request."}), 500

    # Append current user message (again, to match original logic, now to original conversation_history)
    # And bot reply to the original conversation history format for Firebase
    conversation_history.append({'role': 'user', 'content': user_message}) # Add back current user message for consistency
    conversation_history.append({'role': 'assistant', 'content': bot_reply})

    # Save updated conversation to Firebase
    ref.set(conversation_history)

    # Save bot reply to messages for frontend display
    messages_ref = db.reference(f'messages/{user_id}')
    messages_ref.push({
        'text': bot_reply,
        'user': 'Bot',
        'timestamp': {".sv": "timestamp"}
    })

    return jsonify({'status': 'success', 'reply': bot_reply})
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_message = data['text']
    user_id = data.get('userId')

    if not user_message:
        return jsonify({"error": "Missing 'text' in request body"}), 400
    if not user_id:
        # If userId is not provided, generate a simple one or handle as anonymous
        # For a real app, you'd want proper user management
        user_id = "anonymous_user" # Fallback for testing without a specific user ID

    # Sentiment Analysis
    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(user_message)
    sentiment_compound = sentiment['compound']

    # Fetch conversation history
    ref = db.reference(f'conversations/{user_id}')
    conversation = ref.get() or []

    # Append user message to conversation
    conversation.append({'role': 'user', 'content': user_message})

    # Adjust prompt based on sentiment
    if sentiment_compound < -0.5:
        system_message = "You are a helpful assistant that provides comforting responses."
    elif sentiment_compound > 0.5:
        system_message = "You are an enthusiastic assistant that engages positively."
    else:
        system_message = "You are a neutral assistant."

    messages_for_openai = [{'role': 'system', 'content': system_message}] + conversation

    # Generate response from OpenAI with context
    try:
        response = openai.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=messages_for_openai
        )
        bot_reply = response.choices[0].message.content.strip()
    except OpenAIError as e:
        print(f"OpenAI API Error: {e}")
        return jsonify({"error": f"Failed to get response from AI: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred while processing your request."}), 500        

    # Append bot reply to conversation
    conversation.append({'role': 'assistant', 'content': bot_reply})

    # Save updated conversation
    ref.set(conversation)

    # Save bot reply to messages for frontend display
    messages_ref = db.reference(f'messages/{user_id}')
    messages_ref.push({
        'text': bot_reply,
        'user': 'Bot',
        'timestamp': {".sv": "timestamp"}
    })

    # Return the bot's reply to the frontend
    return jsonify({'status': 'success', 'reply': bot_reply})

if __name__ == '__main__':
    app.run(debug=True)