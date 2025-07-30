import React, { useState, useEffect } from 'react';
import firebase from './firebase';
import axios from 'axios';

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
      }
    });
  }, []);

  const fetchMessages = (uid) => {
    const messagesRef = firebase.database().ref(`messages/${uid}`);
    messagesRef.on('value', (snapshot) => {
      const msgs = snapshot.val();
      const newState = [];
      for (let msg in msgs) {
        newState.push({
          id: msg,
          text: msgs[msg].text,
          user: msgs[msg].user,
        });
      }
      setMessages(newState);
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() === '') return;

    const messagesRef = firebase.database().ref(`messages/${user.uid}`);
    const message = {
      text: input,
      user: 'User',
    };
    messagesRef.push(message);
    setInput('');

    axios.post('/api/message', { text: input, userId: user.uid });
  };

  if (!user) {
    return <Auth />;
  }

  return (
    <div className="App">
      <div className="chat-window">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.user}`}>
            <p>{msg.text}</p>
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
        />
      </form>
    </div>
  );
}

export default App;