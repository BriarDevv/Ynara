import { SEARCH_MIN_LENGTH, useMemorySearch } from "@ynara/core/features/memory";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MemoryTimelineSkeleton } from "./components/MemoryTimelineSkeleton";
import { SearchResultRow } from "./components/SearchResultRow";

/** Disparadores de búsqueda (matchean el dataset de demo del mock). */
const SUGGESTIONS = ["tesis", "brief de Õmi", "jerga técnica", "foco"] as const;

const DEBOUNCE_MS = 250;

/** Color del placeholder del input (RN no lo toma del className NativeWind). */
const PLACEHOLDER_COLOR = "rgba(36,44,63,0.45)";

/**
 * Pantalla **Búsqueda** (wireframes 18/19) — espejo de `BuscarView` de web. Input
 * con debounce que pega a `GET /v1/memory/search` (PROVISIONAL: corre contra el
 * mock MSW; al cablear el endpoint real no cambia) y resuelve los estados: vacío
 * (sugerencias), cargando (skeleton), resultados ("N resultados" + lista) y sin
 * resultados. Reusa el hook compartido `useMemorySearch` de `@ynara/core`.
 *
 * Tests pendientes de la infra de tests mobile (Jest + RNTL, PR aparte).
 */
export function BuscarScreen() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [debounced, setDebounced] = useState("");
  // `now` estable durante la vida de la vista: ancla las fechas relativas.
  const [now] = useState(() => new Date());

  // Debounce: la query efectiva sigue al input con un respiro, así no se dispara
  // un fetch por cada tecla.
  useEffect(() => {
    const id = setTimeout(() => setDebounced(input), DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [input]);

  const active = debounced.trim().length >= SEARCH_MIN_LENGTH;
  const search = useMemorySearch(debounced);

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top"]}>
      <ScrollView contentContainerClassName="gap-6 px-6 py-8" keyboardShouldPersistTaps="handled">
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Volver a Memoria"
          hitSlop={8}
          onPress={() => router.back()}
          className="self-start"
        >
          <Text className="text-button text-ink-soft">‹ Memoria</Text>
        </Pressable>

        <Text className="text-title font-semibold text-ink-deep">Buscar</Text>

        <View className="h-12 flex-row items-center gap-3 rounded-lg border border-border bg-bg-soft px-4">
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Buscá en tu memoria…"
            placeholderTextColor={PLACEHOLDER_COLOR}
            autoFocus
            returnKeyType="search"
            accessibilityLabel="Buscar en tu memoria"
            className="h-full flex-1 text-body text-ink"
          />
          {input.length > 0 ? (
            <Pressable
              onPress={() => setInput("")}
              accessibilityRole="button"
              accessibilityLabel="Limpiar búsqueda"
              hitSlop={8}
            >
              <Text className="text-body text-ink-soft">✕</Text>
            </Pressable>
          ) : null}
        </View>

        {!active ? (
          <View className="gap-3">
            <Text className="text-caption text-ink-soft">Probá buscar</Text>
            <View className="flex-row flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <Pressable
                  key={s}
                  accessibilityRole="button"
                  onPress={() => setInput(s)}
                  className="rounded-pill border border-border bg-bg px-3 py-1.5 active:bg-bg-soft"
                >
                  <Text className="text-body-sm text-ink">{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : search.isLoading ? (
          <MemoryTimelineSkeleton />
        ) : search.isError ? (
          <View className="gap-1 rounded-lg border border-border bg-bg p-4">
            <Text className="text-body text-ink">No pudimos buscar</Text>
            <Text className="text-body-sm text-ink-soft">
              Puede ser un problema de conexión. Probá de nuevo en un momento.
            </Text>
          </View>
        ) : search.data && search.data.total === 0 ? (
          <View className="gap-1 rounded-lg border border-border bg-bg p-4">
            <Text className="text-body text-ink">Nada para «{search.data.query}»</Text>
            <Text className="text-body-sm text-ink-soft">
              Probá con otras palabras, o revisá el timeline completo.
            </Text>
          </View>
        ) : search.data ? (
          <View className="gap-3">
            <Text className="text-caption text-ink-soft">
              {search.data.total} {search.data.total === 1 ? "resultado" : "resultados"}
            </Text>
            <View>
              {search.data.results.map((hit, index) => (
                <SearchResultRow
                  key={`${hit.layer}:${hit.ref}`}
                  hit={hit}
                  now={now}
                  first={index === 0}
                />
              ))}
            </View>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
