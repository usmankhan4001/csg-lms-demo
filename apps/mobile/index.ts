// Must be the first import in the app: react-native-gesture-handler installs
// its native event handlers globally, and importing it late (or not at the
// very top of the entry file) is a common source of gestures silently not
// working on Android. See https://reactnavigation.org/docs/gesture-handler.
import 'react-native-gesture-handler';

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App).
// It also ensures that whether you load the app in Expo Go or in a native
// build, the environment is set up appropriately.
registerRootComponent(App);
