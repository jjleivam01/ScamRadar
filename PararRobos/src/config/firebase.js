// c:\Tesis_IA\PararRobos\src\config\firebase.js
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyBNsWdHmCvuVycbcLVQjEa9fYam2wt92Tw",
    authDomain: "pararrobos.firebaseapp.com",
    projectId: "pararrobos",
    storageBucket: "pararrobos.firebasestorage.app",
    messagingSenderId: "259878822867",
    appId: "1:259878822867:web:fab344ba91939270edc526"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Authentication and Firestore
export const auth = getAuth(app);
export const db = getFirestore(app);

export default app;
