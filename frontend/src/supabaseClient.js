import { createClient } from '@supabase/supabase-js';

// Les clés sont lues depuis les variables d'environnement Vite
// Créez un fichier .env à la racine du dossier frontend/ (voir .env.example)
const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL  || 'https://selkpaowxwjjfteadjvz.supabase.co';
const supabaseKey  = import.meta.env.VITE_SUPABASE_ANON_KEY
  || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlbGtwYW93eHdqamZ0ZWFkanZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NDI0NjksImV4cCI6MjA5NTIxODQ2OX0.c2_RCi7Qn9pvNzPcAG8Lcd1SMKBFzthBactVizFHJ9w';

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    autoRefreshToken:    true,
    persistSession:      true,
    detectSessionInUrl:  true,
  },
});