import React, { useState } from 'react';
import firebase from './firebase';

function Auth() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const signUp = (e) => {
    e.preventDefault();
    firebase.auth().createUserWithEmailAndPassword(email, password)
      .catch((error) => {
        console.error('Signup Error:', error);
      });
  };

  const signIn = (e) => {
    e.preventDefault();
    firebase.auth().signInWithEmailAndPassword(email, password)
      .catch((error) => {
        console.error('Signin Error:', error);
      });
  };

  return (
    <div className="auth-container">
      <h2>Welcome to Chatbot App</h2>
      <form>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button onClick={signIn}>Log In</button>
        <button onClick={signUp}>Sign Up</button>
      </form>
    </div>
  );
}

export default Auth;