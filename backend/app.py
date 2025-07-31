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

# --- MOCK PRODUCT DATA ---
MOCK_PRODUCTS_DATA = [
    {
        "id": "WM001",
        "name": "SmartWasher 5000 (Top Load)",
        "category": "Washing Machine",
        "brand": "AppliancePro",
        "description": "High-efficiency top-load washing machine with smart fabric care and quick wash cycles. Perfect for medium to large families.",
        "price_per_month": 45.00,
        "availability_status": "Available",
        "stock_count": 15,
        "features": ["10kg Capacity", "AI Smart Wash", "Steam Sanitize", "Low Water Usage"],
        "rating": 4.5
    },
    {
        "id": "WM002",
        "name": "Compact Washer 200 (Front Load)",
        "category": "Washing Machine",
        "brand": "EcoWash",
        "description": "Space-saving front-load washing machine ideal for apartments. Energy-efficient and quiet operation.",
        "price_per_month": 30.00,
        "availability_status": "Available",
        "stock_count": 8,
        "features": ["5kg Capacity", "Eco-Friendly Mode", "Delay Start", "Child Lock"],
        "rating": 4.2
    },
    {
        "id": "FR001",
        "name": "FrostFree Refrigerator (Double Door)",
        "category": "Refrigerator",
        "brand": "CoolTech",
        "description": "Large capacity double-door refrigerator with frost-free technology and advanced cooling system. Includes ice dispenser.",
        "price_per_month": 60.00,
        "availability_status": "Limited Stock",
        "stock_count": 3,
        "features": ["400L Capacity", "Twin Cooling Plus", "Deodorizing Filter", "LED Lighting"],
        "rating": 4.7
    },
    {
        "id": "FR002",
        "name": "Mini Fridge Elite",
        "category": "Refrigerator",
        "brand": "CompactCool",
        "description": "Portable and energy-efficient mini-fridge. Perfect for bedrooms, offices, or dorms. Silent operation.",
        "price_per_month": 20.00,
        "availability_status": "Out of Stock",
        "stock_count": 0,
        "features": ["50L Capacity", "Quiet Operation", "Adjustable Shelf", "Reversible Door"],
        "rating": 3.9
    },
    {
        "id": "OVN001",
        "name": "Smart Oven Chef",
        "category": "Oven",
        "brand": "BakeMaster",
        "description": "Multi-function smart oven with pre-programmed recipes and Wi-Fi connectivity. Perfect for baking, grilling, and roasting.",
        "price_per_month": 35.00,
        "availability_status": "Available",
        "stock_count": 10,
        "features": ["25L Capacity", "Convection Bake", "Touch Control Panel", "Appliance Integration"],
        "rating": 4.6
    }
]
# --- END MOCK PRODUCT DATA ---

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

# --- Mock Product Data API Routes ---
@app.route('/api/products', methods=['GET'])
def get_all_products():
    """Returns a list of all mock products."""
    return jsonify(MOCK_PRODUCTS_DATA)

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product_by_id(product_id):
    """Returns a single product by its ID."""
    product = next((p for p in MOCK_PRODUCTS_DATA if p['id'].lower() == product_id.lower()), None)
    if product:
        return jsonify(product)
    return jsonify({"error": "Product not found"}), 404

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """
    Searches for products based on a query parameter.
    Example: GET /api/products/search?q=washer
    """
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify(MOCK_PRODUCTS_DATA) # Return all if no query

    filtered_products = [
        p for p in MOCK_PRODUCTS_DATA
        if query in p['name'].lower() or \
           query in p['description'].lower() or \
           query in p['category'].lower() or \
           any(query in f.lower() for f in p['features'])
    ]
    return jsonify(filtered_products)

# --- End Mock Product Data API Routes ---

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
    conversation_history = ref.get() or []

    # --- Start of REVISED RAG Logic for Product Data ---
    # This string will hold the product information we want to inject.
    product_context_text = "" 
    
    # Keywords to trigger product search (can be expanded)
    product_query_keywords = [
        "product", "appliance", "washer", "fridge", "oven", "machine",
        "features", "price", "cost", "availability", "stock", "rent",
        "about", "details", "info", "specs"
    ]
    
    # Check if the user message contains any product-related keywords
    is_product_related_query = any(kw in user_message.lower() for kw in product_query_keywords)
    
    # Attempt to find a specific product by name or ID mentioned in the user's query
    identified_product = None
    if is_product_related_query:
        for product in MOCK_PRODUCTS_DATA:
            # Check for full name match or ID match (case-insensitive)
            if product['name'].lower() in user_message.lower() or \
               product['id'].lower() == user_message.lower():
                identified_product = product
                break
    
    if identified_product:
        # If a specific product is found, format its detailed info for the LLM
        product_context_text = (
            f"Here is specific information about the {identified_product['name']} (Product ID: {identified_product['id']}):\n"
            f"Category: {identified_product['category']}\n"
            f"Brand: {identified_product['brand']}\n"
            f"Description: {identified_product['description']}\n"
            f"Price per month: ${identified_product['price_per_month']:.2f}\n"
            f"Availability Status: {identified_product['availability_status']}\n"
            f"Current Stock: {identified_product['stock_count']} units\n"
            f"Key Features: {', '.join(identified_product['features'])}\n"
            f"Customer Rating: {identified_product['rating']} out of 5 stars.\n\n"
            f"Please use this information to answer the user's question. If the user asks about details not covered here, state that you only have the provided information.\n\n"
        )
        print(f"DEBUG: Adding detailed context for product: {identified_product['name']}")
    elif is_product_related_query: # If it's a general product query but no specific product found
        # Provide a general overview or list some available categories/products
        available_products_summary = ", ".join(
            [f"{p['name']} ({p['category']}, ${p['price_per_month']:.2f}/month)" 
             for p in MOCK_PRODUCTS_DATA if p['availability_status'] == "Available"]
        )
        product_context_text = (
            f"You are an assistant for an appliance rental website. Here is a summary of some products we have available:\n"
            f"{available_products_summary}\n\n"
            f"Please answer general product questions based on this or ask for more specifics. If the user asks about products not listed, state that you only have information about the products in your database.\n\n"
        )
        print("DEBUG: Adding general product context.")
    # --- End of REVISED RAG Logic ---


    # Adjust system message based on sentiment
    # This `system_instruction` will be passed directly to the GenerativeModel,
    # affecting its overall persona. It's separate from the RAG context.
    if sentiment_compound < -0.5:
        system_instruction_for_model = "You are a helpful assistant that provides comforting and supportive responses about appliance rentals."
    elif sentiment_compound > 0.5:
        system_instruction_for_model = "You are an enthusiastic assistant that engages positively and offers helpful information about appliance rentals."
    else:
        system_instruction_for_model = "You are a neutral and informative assistant for appliance rentals."

    # Prepare conversation history for Gemini.
    # It must be a list of dicts, each with 'role' ('user' or 'model') and 'parts' (list of dicts with 'text').
    gemini_conversation_history = []
    for msg in conversation_history:
        gemini_conversation_history.append({'role': msg['role'], 'parts': [{'text': msg['content']}]})

    # --- Construct the FINAL message to send to Gemini ---
    # Prepend the product context to the current user's message.
    # This makes the context very prominent for the LLM.
    final_message_content_for_gemini = user_message
    if product_context_text:
        final_message_content_for_gemini = f"{product_context_text} User's question: {user_message}"
    
    print(f"DEBUG: Final content sent to Gemini's send_message: {final_message_content_for_gemini[:200]}...") # Print first 200 chars for debugging

    try:
        # Initialize the model with the overall system instruction (persona)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_instruction_for_model, # Passed here
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        # Start a chat session with the *actual* conversation history (without system instruction or injected product context)
        # The product context is part of the *current* message being sent.
        chat_session = model.start_chat(history=gemini_conversation_history) 

        # Send the combined user message (user's query + RAG context)
        response = chat_session.send_message(final_message_content_for_gemini)
        bot_reply = response.text.strip()

    except GoogleAPIError as e:
        print(f"Gemini API Error: {e}")
        return jsonify({"error": f"Failed to get response from AI: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred while processing your request."}), 500

    # Append current user message and bot reply to the original conversation_history for Firebase persistence
    conversation_history.append({'role': 'user', 'content': user_message}) # Add original user message for history
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

if __name__ == '__main__':
    app.run(debug=True)