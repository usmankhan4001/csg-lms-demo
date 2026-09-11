import React from 'react';
import { ScrollView, View, type RefreshControlProps } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

/**
 * Canvas-background page shell. Screens hosted under a stack navigator
 * already get a safe top edge from the native header, so the default only
 * pads the bottom (home indicator / gesture bar) — pass `edges` to override
 * for a header-less screen.
 */
export function Screen({
  children,
  scroll = true,
  edges = ['bottom', 'left', 'right'],
  refreshControl,
}: {
  children: React.ReactNode;
  scroll?: boolean;
  edges?: Edge[];
  refreshControl?: React.ReactElement<RefreshControlProps>;
}) {
  return (
    <SafeAreaView edges={edges} className="flex-1 bg-canvas dark:bg-canvas-dark">
      {scroll ? (
        <ScrollView
          contentContainerStyle={{ padding: 16, gap: 16 }}
          keyboardShouldPersistTaps="handled"
          refreshControl={refreshControl}
        >
          {children}
        </ScrollView>
      ) : (
        <View className="flex-1 p-4" style={{ gap: 16 }}>
          {children}
        </View>
      )}
    </SafeAreaView>
  );
}
