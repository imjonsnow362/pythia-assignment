import React, { useState } from 'react';
import firebase from './firebase';

function Auth() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const handleAuthError = (err) => {
    console.error('Authentication Error:', err);
    setError(err.message); // Set error message to display to user
  };

  const signUp = (e) => {
    e.preventDefault();
    setError(null);
    firebase.auth().createUserWithEmailAndPassword(email, password)
      .catch(handleAuthError);
  };

  const signIn = (e) => {
    e.preventDefault();
    firebase.auth().signInWithEmailAndPassword(email, password)
      .catch(handleAuthError);
  };

  return (
    <div className="auth-container">
      <h2>Welcome to Chatbot App</h2>
      <p>Log in or sign up to start chatting.</p>
      <form onSubmit={(e) => e.preventDefault()}> {/* Prevent default form submission directly */}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required // Make email required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required // Make password required
        />
        {error && <p className="auth-error-message">{error}</p>} {/* Display error message */}
        <button type="submit" onClick={signIn}>Log In</button>
        <button type="submit" onClick={signUp}>Sign Up</button>
      </form>
    </div>
  );
}

export default Auth;