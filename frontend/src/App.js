import React, { useState, useEffect } from 'react';
import firebase from './firebase';
import axios from 'axios';
import Auth from './Auth'; 
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [user, setUser] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false);

  useEffect(() => {
    // Authentication state observer
    firebase.auth().onAuthStateChanged((currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        fetchMessages(currentUser.uid);
      } else {
        // Clear messages if user logs out
        setMessages([]);
      }
    });

    // Clean up the listener when the component unmounts
    return () => {
      // You might want to detach the 'value' listener from fetchMessages here
      // if it's causing issues after logout, but for simplicity, we'll let it re-attach
      // when a new user logs in.
    };
  }, []); // Empty dependency array means this runs once on mount

  const fetchMessages = (uid) => {
    const messagesRef = firebase.database().ref(`messages/${uid}`);
    // Attach a listener to the messages reference
    messagesRef.on('value', (snapshot) => {
      const msgs = snapshot.val();
      const newState = [];
      for (let msgId in msgs) {
        newState.push({
          id: msgId,
          text: msgs[msgId].text,
          user: msgs[msgId].user,
        });
      }
      setMessages(newState);
    });
  };

  // Sign out function
  const signOut = () => {
    firebase.auth().signOut()
      .then(() => {
        console.log("User signed out successfully.");
        // Firebase's onAuthStateChanged listener will handle setting user to null
        // and clearing messages.
      })
      .catch((error) => {
        console.error("Error signing out:", error.message);
        // Handle sign-out errors (e.g., display a message to the user)
      });
  };

  const toggleChat = () => {
    setIsChatOpen(prev => !prev);
  };

  const handleSubmit = (e) => {
    e.preventDefault(); // Prevent default form submission behavior
    if (input.trim() === '') {
      // Don't send empty messages
      return;
    }

    if (!user) {
      console.error("No user logged in to send message.");
      return;
    }

    // Push user message to Firebase Realtime Database
    const messagesRef = firebase.database().ref(`messages/${user.uid}`);
    const message = {
      text: input,
      user: 'User',
      timestamp: firebase.database.ServerValue.TIMESTAMP // Add server timestamp
    };
    messagesRef.push(message)
      .then(() => {
        console.log("User message pushed to Firebase.");
        setIsBotTyping(false);
      })
      .catch((error) => {
        console.error("Error pushing user message to Firebase:", error.message);
        setIsBotTyping(false);
      });

      setIsBotTyping(true);


    // Send message to backend for AI processing
    axios.post('http://127.0.0.1:5000/api/message', { text: input, userId: user.uid })
      .then(response => {
        console.log("Backend response:", response.data);
        // The bot's reply will be fetched via the fetchMessages listener
        // No need to update messages state directly here for bot replies
      })
      .catch(error => {
        console.error("Error sending message to backend:", error);
        // Handle backend errors (e.g., display an error message in chat)
      });

    // Clear the input field
    setInput('');
  };

  // If no user is logged in, show the Auth component
  if (!user) {
    return (
      <div className="website-container">
        <Auth />
      </div>
    );
  }

  // If a user is logged in, show the chat interface
  return (
    <div className="website-container">
      {/* Main website content */}
      <div className="website-content">
        <h1>Welcome to Our Product Showcase!</h1>
        <p>This is a simulated website where you can learn about our amazing products. Click the chat icon to talk to our AI assistant!</p>
        <p>Our AI can answer questions about product features, pricing, availability, and more (once integrated with your mock product API).</p>
        <p>Feel free to explore and then open the chatbot for a real-time conversation.</p>
        <button onClick={signOut} className="sign-out-button">Sign Out</button>
      </div>

      {/* Chatbot toggle button */}
      <button 
        className="open-chatbot-button" 
        onClick={toggleChat}
        aria-label={isChatOpen ? "Close Chatbot" : "Open Chatbot"}
      >
        {isChatOpen ? '✕' : '💬'} {/* X for close, speech bubble for open */}
      </button>

      {/* Chatbot Container (Modal-like appearance) */}
      <div className={`chatbot-container ${isChatOpen ? 'open' : ''}`}>
        <div className="chatbot-header">
          <h1>AI Assistant</h1>
          <button onClick={toggleChat} className="close-chatbot-button" aria-label="Close Chat">✕</button>
        </div>
        <div className="chat-window">
          {messages.length === 0 ? (
            <div className="no-messages">Start a conversation!</div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.user === 'User' ? 'user-message' : 'bot-message'}`}>
                <p>{msg.text}</p>
              </div>
            ))
          )}

          {isBotTyping && (
            <div className="message bot-message typing-indicator">
              <div className="dot-flashing"></div>
            </div>
          )}
          {/* Scroll to bottom */}
          <div ref={el => { if (el) el.scrollIntoView({ behavior: 'smooth' }); }} />
        </div>
        <form onSubmit={handleSubmit} className="message-input-form">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="message-input"
            disabled={!user} // Disable input if no user for some reason
          />
          <button type="submit" className="send-button" disabled={!user || input.trim() === ''}>Send</button>
        </form>
      </div>
    </div>
  );
}

export default App;