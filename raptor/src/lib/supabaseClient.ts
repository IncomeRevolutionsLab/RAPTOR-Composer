import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://ulasrprjenbflylxjtcx.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzgwNTgyOTc4LCJleHAiOjIwOTU5NDI5Nzh9.aFZyqZInzu5Kfa4W1A1V8nx4PxBIjaWmqunhBrga-bE";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
