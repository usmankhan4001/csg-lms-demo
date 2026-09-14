import React, { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { KeyRound } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/AuthContext';

/**
 * Sign-in with real school credentials.
 *
 * Replaces the dev-only "paste a locally-minted JWT" screen: that token could
 * no longer authenticate anything (`dev_tokens.py` was deleted and the backend
 * now requires a real Learnhouse session), so every screen behind it 401'd.
 *
 * Credentials go to Learnhouse's own `/auth/login`, which is rate-limited and
 * locks an account after repeated failures — the errors surfaced below come
 * from the server and distinguish a wrong password from a lockout, a rate
 * limit, and the network being down, because those need different actions from
 * the user.
 */
export function LoginScreen() {
  const { login, expiredNotice } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setSubmitting(true);
    setError(null);
    const result = await login(email, password);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.error ?? 'Sign-in failed.');
    }
  };

  const disabled = submitting || !email.trim() || !password;

  return (
    <SafeAreaView className="flex-1 bg-canvas dark:bg-canvas-dark">
      <ScrollView
        contentContainerStyle={{ flexGrow: 1, padding: 24, justifyContent: 'center', gap: 20 }}
        keyboardShouldPersistTaps="handled"
      >
        <View className="items-center gap-2">
          <View className="size-14 items-center justify-center rounded-2xl bg-action">
            <Text className="text-lg font-bold tracking-tighter text-white">CSG</Text>
          </View>
          <Text className="text-xl font-semibold text-ink dark:text-ink-dark">CSG LMS</Text>
          <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">Sign in to your school account</Text>
        </View>

        {expiredNotice ? (
          <View className="rounded-md border border-line bg-surface p-3 dark:border-line-dark dark:bg-surface-dark">
            <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">{expiredNotice}</Text>
          </View>
        ) : null}

        <View className="gap-1.5">
          <Text className="text-sm font-medium text-ink dark:text-ink-dark">Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="you@school.edu"
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="username"
            accessibilityLabel="Email"
            className="min-h-12 rounded-md border border-line bg-surface px-3 py-3 text-sm text-ink dark:border-line-dark dark:bg-surface-dark dark:text-ink-dark"
          />
        </View>

        <View className="gap-1.5">
          <Text className="text-sm font-medium text-ink dark:text-ink-dark">Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
            textContentType="password"
            accessibilityLabel="Password"
            onSubmitEditing={disabled ? undefined : onSubmit}
            returnKeyType="go"
            className="min-h-12 rounded-md border border-line bg-surface px-3 py-3 text-sm text-ink dark:border-line-dark dark:bg-surface-dark dark:text-ink-dark"
          />
          {error ? <Text className="text-xs text-critical dark:text-critical-dark">{error}</Text> : null}
        </View>

        <Pressable
          onPress={onSubmit}
          disabled={disabled}
          accessibilityRole="button"
          accessibilityLabel="Sign in"
          accessibilityState={{ disabled, busy: submitting }}
          className="min-h-12 flex-row items-center justify-center gap-2 rounded-md bg-action px-4 py-3 active:opacity-80 disabled:opacity-60"
        >
          {submitting ? <ActivityIndicator color="white" /> : <KeyRound size={16} color="white" />}
          <Text className="text-sm font-semibold text-white">{submitting ? 'Signing in…' : 'Sign in'}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
