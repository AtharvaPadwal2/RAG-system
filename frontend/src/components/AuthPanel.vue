<script setup>
import { computed, ref } from "vue";
import { useAuth } from "../composables/useAuth";

const emit = defineEmits(["close"]);

const {
  signIn,
  signUp,
} = useAuth();

const mode = ref("login");
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const busy = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const isSignup = computed(() => mode.value === "signup");

function changeMode(nextMode) {
  if (busy.value) return;

  mode.value = nextMode;
  password.value = "";
  confirmPassword.value = "";
  errorMessage.value = "";
  successMessage.value = "";
}

async function submit() {
  if (busy.value) return;

  errorMessage.value = "";
  successMessage.value = "";

  if (isSignup.value && password.value !== confirmPassword.value) {
    errorMessage.value = "Passwords do not match.";
    return;
  }

  busy.value = true;

  try {
    if (isSignup.value) {
      const data = await signUp(email.value, password.value);

      if (data.session) {
        emit("close");
      } else {
        successMessage.value =
          "Check your email for a confirmation link. If an account already exists, try logging in.";
      }
    } else {
      await signIn(email.value, password.value);
      emit("close");
    }
  } catch (error) {
    if (error.status === 429) {
      errorMessage.value =
          "Too many attempts. Please wait before trying again.";
    } else if (isSignup.value) {
      errorMessage.value =
          "Could not sign up. Check your details and password requirements, then try again.";
    } else {
      errorMessage.value =
          "Could not log in. Check your email, password, and email verification.";
    }
  } finally {
    // Do not keep passwords in form state after submitting.
    password.value = "";
    confirmPassword.value = "";
    busy.value = false;
  }
}
</script>

<template>
  <section class="auth-panel" aria-labelledby="auth-heading">
    <div class="auth-header">
      <h2 id="auth-heading">
        {{ isSignup ? "Create your account" : "Welcome back" }}
      </h2>

      <button
        type="button"
        class="close-button"
        :disabled="busy"
        aria-label="Close login form"
        @click="emit('close')"
      >
        ✕
      </button>
    </div>

    <p class="auth-description">
      Log in to your chess account. Game saving will be connected next.
    </p>

    <div class="auth-tabs" role="group" aria-label="Account action">
      <button
        type="button"
        :class="{ active: !isSignup }"
        :aria-pressed="!isSignup"
        :disabled="busy"
        @click="changeMode('login')"
      >
        Log in
      </button>

      <button
        type="button"
        :class="{ active: isSignup }"
        :aria-pressed="isSignup"
        :disabled="busy"
        @click="changeMode('signup')"
      >
        Sign up
      </button>
    </div>

    <form :aria-busy="busy" @submit.prevent="submit">
      <label for="auth-email">Email</label>

      <input
        id="auth-email"
        v-model="email"
        type="email"
        autocomplete="email"
        maxlength="254"
        placeholder="you@example.com"
        :disabled="busy"
        required
      />

      <label for="auth-password">Password</label>

      <input
        id="auth-password"
        v-model="password"
        type="password"
        :autocomplete="isSignup ? 'new-password' : 'current-password'"
        :minlength="isSignup ? 8 : undefined"
        :disabled="busy"
        required
      />

      <p v-if="isSignup" class="password-hint">
        Use at least 8 characters. Additional project password
        requirements may apply.
      </p>

      <template v-if="isSignup">
        <label for="auth-confirm-password">Confirm password</label>

        <input
          id="auth-confirm-password"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="8"
          :disabled="busy"
          required
        />
      </template>

      <p v-if="errorMessage" class="auth-error" role="alert">
        {{ errorMessage }}
      </p>

      <p v-if="successMessage" class="auth-success" role="status">
        {{ successMessage }}
      </p>

      <button class="submit-button" type="submit" :disabled="busy">
        {{
          busy
            ? "Please wait…"
            : isSignup
              ? "Create account"
              : "Log in"
        }}
      </button>
    </form>

    <button
      type="button"
      class="guest-button"
      :disabled="busy"
      @click="emit('close')"
    >
      Continue as guest
    </button>
  </section>
</template>

<style scoped>
.auth-panel {
  width: 100%;
  max-width: 440px;
  box-sizing: border-box;
  margin: 24px auto;
  padding: 24px;
  border: 1px solid #365740;
  border-radius: 16px;
  background: #14251a;
  color: #edf5e9;
}

.auth-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

h2 {
  margin: 0;
  font-size: 24px;
}

.auth-description,
.password-hint {
  color: #afc4a9;
  line-height: 1.6;
}

.password-hint {
  margin: 8px 0 0;
  font-size: 13px;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  margin: 20px 0;
}

button,
input {
  font: inherit;
}

button {
  padding: 10px 16px;
  border: 1px solid #48644a;
  border-radius: 8px;
  background: transparent;
  color: #edf5e9;
  cursor: pointer;
}

.auth-tabs button {
  flex: 1;
}

.auth-tabs button.active,
.submit-button {
  background: #a7d78c;
  color: #152111;
  border-color: #a7d78c;
  font-weight: 700;
}

.close-button {
  padding: 8px 12px;
}

label {
  display: block;
  margin: 16px 0 8px;
  font-weight: 600;
}

input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 12px;
  border: 1px solid #48644a;
  border-radius: 8px;
  background: #0d1911;
  color: #fff;
}

.submit-button,
.guest-button {
  width: 100%;
  margin-top: 20px;
}

.guest-button {
  margin-top: 12px;
}

.auth-error {
  color: #ffb4a9;
  line-height: 1.5;
}

.auth-success {
  color: #b5e49b;
  line-height: 1.5;
}

button:disabled,
input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button:focus-visible,
input:focus-visible {
  outline: 3px solid #c5efa9;
  outline-offset: 3px;
}
</style>