import React, { useState, useEffect } from 'react';
import firebase from './firebase';
import axios from 'axios';
import Auth from './Auth'; // Make sure this import is present

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [user, setUser] = useState(null);

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
      })
      .catch((error) => {
        console.error("Error pushing user message to Firebase:", error.message);
      });

    // Send message to backend for AI processing
    axios.post('/api/message', { text: input, userId: user.uid })
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
    return <Auth />;
  }

  // If a user is logged in, show the chat interface
  return (
    <div className="App">
      <div className="header">
        <h1>Chatbot</h1>
        <button onClick={signOut} className="sign-out-button">Sign Out</button>
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
      </div>
      <form onSubmit={handleSubmit} className="message-input-form">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          className="message-input"
        />
        <button type="submit" className="send-button">Send</button>
      </form>
    </div>
  );
}

export default App;