import { createClient } from '@supabase/supabase-js';

// URL de ton projet Supabase
const supabaseUrl = 'https://selkpaowxwjjfteadjvz.supabase.co';

// Ta clé publique (anon) que tu as partagée
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlbGtwYW93eHdqamZ0ZWFkanZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2NDI0NjksImV4cCI6MjA5NTIxODQ2OX0.c2_RCi7Qn9pvNzPcAG8Lcd1SMKBFzthBactVizFHJ9w';

export const supabase = createClient(supabaseUrl, supabaseKey);