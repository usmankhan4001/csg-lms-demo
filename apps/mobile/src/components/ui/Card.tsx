import React from 'react';
import { View, type ViewProps } from 'react-native';

export function Card({ children, className, ...rest }: ViewProps & { className?: string }) {
  return (
    <View
      className={`rounded-lg border border-line bg-surface dark:border-line-dark dark:bg-surface-dark ${className ?? ''}`}
      {...rest}
    >
      {children}
    </View>
  );
}
