import { useSuggestions } from "@ynara/core/features/today";
import { Text, View } from "react-native";
import { SuggestionCard } from "@/components/ui/SuggestionCard";
import { cn } from "@/lib/cn";
import { SuggestionsSkeleton } from "./SuggestionsSkeleton";

/**
 * Sección **Ynara sugiere** (wireframe 06/07). Conecta a `GET /v1/suggestions`
 * (mock). Las sugerencias son secundarias respecto de las prioridades: si no hay
 * ninguna, la sección no se muestra; el error es una línea discreta con
 * reintento. Espejo de la sección de web. Separadores entre ítems a mano (RN no
 * tiene `divide-y`).
 */
export function SuggestionsSection() {
  const { data, isPending, isError, refetch, isFetching } = useSuggestions();

  if (isError) {
    return (
      <View className="gap-3">
        <Text className="text-caption text-ink-soft">Ynara sugiere</Text>
        <Text className="text-body-sm text-ink-soft">
          No pudimos traer las sugerencias.{" "}
          <Text
            onPress={() => refetch()}
            className={cn("text-ink underline", isFetching && "opacity-50")}
          >
            Reintentar
          </Text>
        </Text>
      </View>
    );
  }

  // Sin sugerencias → no mostramos la sección vacía (no prometemos contenido).
  if (!isPending && data.length === 0) return null;

  return (
    <View className="gap-3">
      <Text className="text-caption text-ink-soft">Ynara sugiere</Text>
      {isPending ? (
        <SuggestionsSkeleton />
      ) : (
        <View>
          {data.map((suggestion, index) => (
            <View key={suggestion.id}>
              {index > 0 ? <View className="h-px bg-border" /> : null}
              <SuggestionCard
                mode={suggestion.mode}
                title={suggestion.title}
                subtitle={suggestion.why}
              />
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
