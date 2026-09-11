import React, { useEffect, useRef } from 'react';
import { Animated, View, useColorScheme, type DimensionValue } from 'react-native';
import { colors } from '@/theme/tokens';

/**
 * Loading-state placeholder (DESIGN-SYSTEM.md §4 state 2) — a shape matching
 * the final layout, never a full-screen spinner.
 *
 * Deliberately uses inline styles + the core `Animated` API rather than a
 * NativeWind `className`: NativeWind only intercepts the RN primitives it
 * registers via `cssInterop` (View/Text/Image/...), and this project hasn't
 * registered `Animated.View` — doing so for one component isn't worth the
 * extra indirection. Colours are pulled from `theme/tokens.ts`, the same
 * source of truth `tailwind.config.js` uses, so it stays in sync by
 * construction rather than by copy-paste discipline.
 */
export function Skeleton({
  height = 16,
  width = '100%' as DimensionValue,
  radius = 4,
}: {
  height?: number;
  width?: DimensionValue;
  radius?: number;
}) {
  const scheme = useColorScheme();
  const palette = scheme === 'dark' ? colors.dark : colors.light;
  const opacity = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 600, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return <Animated.View style={{ height, width, borderRadius: radius, backgroundColor: palette.line, opacity }} />;
}

export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <View style={{ gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={16} width={`${100 - i * 8}%` as DimensionValue} />
      ))}
    </View>
  );
}
