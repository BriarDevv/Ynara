import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Card, TextField } from "@/components/ui";

// Showcase de dev de los componentes base (espejo del /test-ds de la web).
// Sirve para QA visual de tokens + primitives. No es parte del producto.
export default function TestUi() {
  const [value, setValue] = useState("");

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas">
      <ScrollView contentContainerClassName="gap-6 p-6">
        <Text className="text-hero font-semibold text-ink">Componentes base</Text>

        <View className="gap-3">
          <Text className="text-caption text-ink-soft">Button</Text>
          <Button variant="primary">Continuar</Button>
          <Button variant="secondary">Volver</Button>
          <Button variant="ghost">Cancelar</Button>
          <Button variant="subtle">Probar sin cuenta</Button>
        </View>

        <View className="gap-3">
          <Text className="text-caption text-ink-soft">Card</Text>
          <Card>
            <Text className="text-body text-ink">
              Card por defecto — superficie blanca sobre el canvas marfil.
            </Text>
          </Card>
        </View>

        <View className="gap-3">
          <Text className="text-caption text-ink-soft">TextField</Text>
          <TextField
            label="¿Cómo te llamo?"
            placeholder="Tu nombre"
            value={value}
            onChangeText={setValue}
            hint="Lo uso solo cuando hablo con vos."
          />
          <TextField
            label="Email"
            placeholder="vos@ejemplo.com"
            error="Ese email no parece válido."
          />
        </View>

        <View className="gap-3">
          <Text className="text-caption text-ink-soft">Paleta de marca</Text>
          <View className="flex-row flex-wrap gap-2">
            <View className="h-12 w-12 rounded-md bg-azul" />
            <View className="h-12 w-12 rounded-md bg-indigo" />
            <View className="h-12 w-12 rounded-md bg-violaceo" />
            <View className="h-12 w-12 rounded-md bg-violeta" />
            <View className="h-12 w-12 rounded-md bg-celeste" />
            <View className="h-12 w-12 rounded-md bg-lavanda" />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
