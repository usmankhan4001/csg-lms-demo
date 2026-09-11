module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxImportSource: 'nativewind' }],
      'nativewind/babel',
    ],
    plugins: [
      // Mirrors the `@/*` -> `src/*` path mapping in tsconfig.json. Metro
      // doesn't read tsconfig `paths` on its own, so the alias has to be
      // declared here too, or `@/...` imports resolve fine to TypeScript but
      // fail to bundle at runtime.
      [
        'module-resolver',
        {
          root: ['.'],
          alias: { '@': './src' },
          extensions: ['.ios.js', '.android.js', '.js', '.jsx', '.ts', '.tsx', '.json'],
        },
      ],
    ],
  };
};
