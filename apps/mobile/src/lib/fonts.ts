import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_600SemiBold,
} from "@expo-google-fonts/dm-sans";
import { SpaceGrotesk_500Medium, SpaceGrotesk_600SemiBold } from "@expo-google-fonts/space-grotesk";

/**
 * Familias de marca cargadas por `useFonts` en el root. La CLAVE de cada entrada
 * es el nombre con el que se referencian: NativeWind (tailwind.config
 * `fontFamily`) y RN (`fontFamily`). Space Grotesk = display (titulares de
 * marca); DM Sans = cuerpo. Los pesos se cargan como familias separadas porque
 * RN no compone `fontWeight` sobre fuentes custom.
 */
export const FONT_MAP = {
  "DMSans-Regular": DMSans_400Regular,
  "DMSans-Medium": DMSans_500Medium,
  "DMSans-SemiBold": DMSans_600SemiBold,
  "SpaceGrotesk-Medium": SpaceGrotesk_500Medium,
  "SpaceGrotesk-SemiBold": SpaceGrotesk_600SemiBold,
};
