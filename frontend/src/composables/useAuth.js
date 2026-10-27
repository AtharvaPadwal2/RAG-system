import { computed, readonly, ref } from "vue";
import { supabase } from "../lib/supabase";

const session = ref(null);
const loading = ref(true);
const authError = ref("");

const user = computed(() => session.value?.user ?? null);
const isLoggedIn = computed(() => Boolean(user.value));

let initialization = null;
let authVersion = 0;

function initializeAuth() {
  if (initialization) return initialization;

  // Register once for the entire app.
  supabase.auth.onAuthStateChange((_event, nextSession) => {
    authVersion += 1;
    session.value = nextSession;
    loading.value = false;
    authError.value = "";
  });

  const version = authVersion;

  initialization = (async () => {
    try {
      const { data, error } = await supabase.auth.getSession();

      // A newer auth event takes priority over this initial read.
      if (version !== authVersion) return;

      if (error) throw error;

      session.value = data.session;
    } catch {
      if (version === authVersion) {
        session.value = null;
        authError.value = "Could not restore your login session.";
      }
    } finally {
      loading.value = false;
    }
  })();

  return initialization;
}

async function signUp(email, password) {
  const { data, error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: {
      emailRedirectTo: window.location.origin,
    },
  });

  if (error) throw error;

  // With email confirmation enabled, session is normally null.
  return data;
}

async function signIn(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email: email.trim(),
    password,
  });

  if (error) throw error;

  return data;
}

async function signOut() {
  const { error } = await supabase.auth.signOut({
    scope: "local",
  });

  if (error) throw error;
}

export function useAuth() {
  void initializeAuth();

  return {
    user,
    isLoggedIn,
    loading: readonly(loading),
    authError: readonly(authError),
    signUp,
    signIn,
    signOut,
  };
}