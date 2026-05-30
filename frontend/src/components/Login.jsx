import React from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { API_BASE } from '../config';

export default function Login({ onLoginSuccess }) {
  // En production, tu obtiendras ce Client ID gratuitement sur la console Google Cloud
  const GOOGLE_CLIENT_ID = "TON_GOOGLE_CLIENT_ID.apps.googleusercontent.com";

  const handleSuccess = async (credentialResponse) => {
    const token = credentialResponse.credential;
    
    // Envoi du jeton Google au backend Python pour vérification et création de compte
    try {
      const response = await fetch(`${API_BASE}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
      });
      const data = await response.json();
      if (response.ok) {
        onLoginSuccess(data.user);
      }
    } catch (error) {
      console.error("Erreur de connexion Google:", error);
    }
  };

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-slate-100">
        <div className="bg-slate-900 p-8 rounded-2xl border border-slate-800 shadow-2xl text-center max-w-sm space-y-6">
          <div className="bg-emerald-500 text-slate-950 w-16 h-16 rounded-2xl font-black text-3xl flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/20">
            WC
          </div>
          <div>
            <h2 className="text-xl font-bold">Ligue Privée CDM 2026</h2>
            <p className="text-xs text-slate-400 mt-1">Connecte-toi pour gérer ton équipe et voir tes points</p>
          </div>
          
          <div className="flex justify-center pt-2">
            <GoogleLogin
              onSuccess={handleSuccess}
              onError={() => console.log('Échec de la connexion')}
              theme="filled_blue"
              shape="pill"
            />
          </div>
        </div>
      </div>
    </GoogleOAuthProvider>
  );
}
