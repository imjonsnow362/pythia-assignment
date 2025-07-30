import firebase_admin
from firebase_admin import credentials, db
import json

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

openai.api_key = os.getenv('OPENAI_API_KEY')

@app.route('/api/message', methods=['POST'])
def handle_message():
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
        'timestamp': firebase_admin.db.SERVER_TIMESTAMP
    })

    # Return the bot's reply to the frontend
    return jsonify({'status': 'success', 'reply': bot_reply})

if __name__ == '__main__':
    app.run(debug=True)