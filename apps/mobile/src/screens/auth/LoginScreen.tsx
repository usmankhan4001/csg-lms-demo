import React, { useState } from 'react';
import { ActivityIndicator, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { KeyRound } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/AuthContext';

/**
 * Dev-only sign-in: paste an HS256 Keycloak-shaped token minted locally by
 * `apps/api/scripts/mint_dev_keycloak_token.py` (there is no real Keycloak
 * server deployed for this project — see that script's docstring and
 * `apps/web/lib/api/dev-token.ts` for the exact same flow on web, just
 * pasted into `localStorage` there vs. `expo-secure-store` here).
 *
 * There is no in-app "mint a token" button: the only HTTP route that mints
 * one (`POST /api/v1/dev/mint_keycloak_token`) requires an existing
 * superadmin *Learnhouse* session (a separate, native auth system) — which
 * a fresh mobile install never has. So, like the web dev harness, the
 * developer runs the CLI once on their machine and pastes the result here.
 */
export function LoginScreen() {
  const { loginWithToken } = useAuth();
  const [token, setToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setSubmitting(true);
    setError(null);
    const result = await loginWithToken(token);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.error ?? 'Sign-in failed.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-canvas dark:bg-canvas-dark">
      <ScrollView contentContainerStyle={{ flexGrow: 1, padding: 24, justifyContent: 'center', gap: 20 }} keyboardShouldPersistTaps="handled">
        <View className="items-center gap-2">
          <View className="size-14 items-center justify-center rounded-2xl bg-action">
            <Text className="text-lg font-bold tracking-tighter text-white">CSG</Text>
          </View>
          <Text className="text-xl font-semibold text-ink dark:text-ink-dark">CSG LMS</Text>
          <Text className="text-sm text-ink-muted dark:text-ink-muted-dark">Dev sign-in</Text>
        </View>

        <View className="gap-2 rounded-lg border border-line bg-surface p-4 dark:border-line-dark dark:bg-surface-dark">
          <Text className="text-xs font-semibold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
            On your dev machine
          </Text>
          <Text className="font-mono text-xs text-ink dark:text-ink-dark">
            cd apps/api{'\n'}uv run python scripts/mint_dev_keycloak_token.py --role TEACHER
          </Text>
          <Text className="text-xs text-ink-muted dark:text-ink-muted-dark">
            Copy the printed token and paste it below. Use --role STUDENT, PARENT, or STAFF for the
            other personas this app supports.
          </Text>
        </View>

        <View className="gap-1.5">
          <Text className="text-sm font-medium text-ink dark:text-ink-dark">Access token</Text>
          <TextInput
            value={token}
            onChangeText={setToken}
            placeholder="eyJhbGciOi..."
            placeholderTextColor="hsla(215, 28%, 17%, 0.4)"
            multiline
            autoCapitalize="none"
            autoCorrect={false}
            textContentType={Platform.OS === 'ios' ? 'oneTimeCode' : undefined}
            className="min-h-24 rounded-md border border-line bg-surface p-3 font-mono text-xs text-ink dark:border-line-dark dark:bg-surface-dark dark:text-ink-dark"
          />
          {error ? <Text className="text-xs text-critical dark:text-critical-dark">{error}</Text> : null}
        </View>

        <Pressable
          onPress={onSubmit}
          disabled={submitting}
          accessibilityRole="button"
          accessibilityLabel="Sign in"
          className="min-h-12 flex-row items-center justify-center gap-2 rounded-md bg-action px-4 py-3 active:opacity-80 disabled:opacity-60"
        >
          {submitting ? <ActivityIndicator color="white" /> : <KeyRound size={16} color="white" />}
          <Text className="text-sm font-semibold text-white">{submitting ? 'Signing in…' : 'Sign in'}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
